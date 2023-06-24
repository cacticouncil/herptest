import virtualbox
import virtualbox.events
import virtualbox.library

import os
import time
from pathlib import Path
from datetime import datetime
import paramiko
import paramiko.ssh_exception
import socket
import subprocess
import sys

if sys.platform == "win32":
    # Can only build VMware on Windows CMD (not Linux or WSL)
    from vix import VixHost, VixError, VixJob

MAX_RETRIES  = 10
VM_SLEEP_TIME = 10
ADB = "adb"

# Log information
BUILD_LOG = "build.log"
RUN_LOG = "run.log"
ERR_LOG = ".err"
RESULT_LOG = "result.log"
STAGING_LOG = "staging.log"

class VmWrapper:
    def __init__(self, settings):
        # Currently only supports VMWare and VirtualBox
        if settings.type == "VMWare" or settings.type == "VirtualBox":
            self._type = settings.type
        else:
            # TODO - make this more robust
            print("Unsupported VM type!")
            return
        
        # Setup other settings
        self._name = settings.name
        self._snapshot = settings.snapshot
        self._ip = settings.ip
        self._port = settings.port
        self._user = settings.user
        self._passwd = settings.passwd
        self._boot_time = settings.boot_time
        self._staging_files = settings.staging_files
        self._payload_files = settings.payload_files
        self._result_files = settings.result_files
        self._staging_dir = settings.staging_dir
        self._payload_dir = settings.payload_dir
        self._result_dir = settings.result_dir
        self._build_cmd = settings.build_cmd
        self._stage_cmd = settings.stage_cmd
        self._remote_proj_dir = settings.remote_proj_dir
        self._remote_staging_dir = settings.remote_staging_dir
        self._remote_payload_dir = settings.remote_payload_dir
        self._remote_result_dir = settings.remote_result_dir

    # Method to start the VM software, only needs to be done once
    def start_vm(self):
        if self._type == "VMWare":
            # Load VMWare
            print("Starting VM session at " + str(datetime.now()) + "...")
            self.host = VixHost()

            # Using the VM directory, identify the valid VMs and add them to a dictionary {name: file}
            vm_dir = str(Path.home() / "Documents" / "Virtual Machines")
            files = [(root, file) for root, _, flist in os.walk(vm_dir) for file in flist if file.endswith(".vmx")]
            vm_dict = {file.rsplit('.', 1)[0]: os.path.join(root, file) for root, file in files}
            self._vm_file = vm_dict[self._name]
        # else self._type == "VirtualBox":
        #     self.vm = 
    
    # Method to boot up the VM
    def boot_vm(self):
        self.vm = self.host.open_vm(self._vm_file)

        if self._snapshot != None:
            snapshot = self.vm.snapshot_get_named(self._snapshot)
            self.vm.snapshot_revert(snapshot=snapshot)

        self.vm.power_on()
        time.sleep(self._boot_time)

    # Method to send the necessary files over to reptilian, make the project, then reboot
    def make_vm(self, submission):
        if submission[0] == '.':
            # Split off . if it exists
            submission = submission[1:]
        if submission[0] == '\\':
            # Split off \ if it exists
            submission = submission[1:]

        # Current project directory
        submission_dir = os.path.join(self._payload_dir, submission)

        target = os.path.basename(submission)

        # Boot the VM
        self.boot_vm()

        # Connect to the remote server
        print("Connecting via SSH...")
        ssh = self.loop_for_shell()
        if not ssh:
            print("Error setting up SSH connection! Exiting...");
            self.dirty_shutdown()
            return

        # Run the staging phase.
        print("Setting the stage for the payload...")
        self.run_staging(ssh, target)

        # Run the build phase.
        print("Beginning build cycle...")
        self.run_build(ssh, target, submission_dir)
        
        print("Rebooting post build...")
        ssh.exec_command(self._remote_staging_dir + "/" + 'reboot.sh', timeout=120000)
        time.sleep(self._boot_time)
        ssh.close()

        # Return the location of the staging and build error logs to populate the errors into error.log
        return (self._result_dir + STAGING_LOG + ERR_LOG, self._result_dir + BUILD_LOG + ERR_LOG)

    # Method to run tests, then shut down the VM once completed
    def run_tests(self, submission):
        # Run the test phase.
        print("Beginning test cycle...")

        target = os.path.basename(submission)

        ssh = self.loop_for_shell()
        if not ssh:
            print("Error setting up SSH connection! Exiting...");
            self.dirty_shutdown()
            return

        # Limit to 2 min test
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(self._remote_staging_dir + "/" + 'run.sh', timeout=120000)
        time.sleep(2)
        gen_errors = ssh_stderr.readlines()
        print("Tests complete. Fetching results.")
        sftp = ssh.open_sftp()
        for filename in self._result_files:
            print("Getting " + filename + "...")
            try:
                sftp.get(self._remote_result_dir + "/" + filename, self._result_dir + "/" + target + "/" + filename)
            except:
                print("Error: could not grab " + filename + " for target " + target + ". Skipping.")

        sftp.close()
        self.write_to_file(gen_errors, self._result_dir + "/" + target + "/" + RUN_LOG + ERR_LOG)

        ssh.close()

        # Shut down the VM for this target
        print("Shutting down VM...")
        self.dirty_shutdown()

        run_log = self._result_dir + "/" + target + "/" + RUN_LOG
        # Return the file location of the run.log file
        return run_log
    
    def loop_for_shell(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connected = False
        failures = 0

        while not(connected) and failures < MAX_RETRIES:
            try:
                ssh.connect(self._ip, username=self._user, password=self._passwd, port=self._port)
                connected = True
            except (socket.timeout, paramiko.ssh_exception.SSHException) as err:
                print("Error connecting. Retrying...")
                failures = failures + 1

        if not(connected):
            print("Could not connect to guest: retries exceeded.")
            return None
        return ssh
    
    def dirty_shutdown(self):
        self.vm.power_off(from_guest=False)
        time.sleep(5)
    
    def graceful_shutdown(self):
        # Make sure we are connected with ADB
        # TODO - ADB is broken, investigate
        subprocess.call([ ADB, "connect", self._name ])
        # Send the shutdown signal via ADB and wait for the machine to finish
        subprocess.call([ ADB, "shell", "su -c 'svc power shutdown'" ])
        time.sleep(VM_SLEEP_TIME)
        self.vm.power_off(from_guest=True)
    
    def write_to_file(self, lines, filename):
        with open(filename, 'w+') as file:
            for line in lines:
                file.write(line + "\n")
            file.close()
    
    def run_staging(self, ssh, target):
        # Make sure the directory is there for staging.
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("mkdir " + self._remote_staging_dir)
        build_errors = ssh_stderr.readlines()

        # Push files via SFTP.
        sftp = ssh.open_sftp()

        for filename in self._staging_files:
            if not os.path.isfile(self._staging_dir + "/" + filename):
                print("Error - file " + filename + " does not exist in staging area. Skipping.")
                continue

            print("Pushing " + filename + "...")
            try:
                sftp.put(self._staging_dir + "/" + filename, self._remote_staging_dir + "/" + filename)
            except:
                print("Error: could not upload " + filename + ".")
                self.dirty_shutdown()

        sftp.close()

        # Run the staging script.
        print("Running staging script...");
        time.sleep(2)

        # Make the script executable
        build_errors.extend(ssh_stderr.readlines())
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("chmod +x " + self._remote_staging_dir + "/" + self._stage_cmd)
        time.sleep(2)

        # Run the staging script
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(self._remote_staging_dir + "/" + self._stage_cmd)
        build_errors.extend(ssh_stderr.readlines())
        self.write_to_file(build_errors, self._result_dir + "/" + target + "/" + STAGING_LOG + ERR_LOG)
        
    def run_build(self, ssh, target, target_dir):
        # Push files via SFTP.
        sftp = ssh.open_sftp()

        for filename in self._payload_files:
            if not os.path.isfile(target_dir + "/" + filename):
                print("Error - file " + filename + " does not exist in payload area for target " + target + ". Skipping.")
                continue

            print("Pushing " + filename + "...")
            try:
                sftp.put(target_dir + "/" + filename, self._remote_payload_dir + "/" + filename)
            except:
                print("Error: could not upload " + filename + ".")

        # Run the build script; power down when completed.
        print("Executing build....")
        # Limit to 20 min build
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("chmod +x " + self._remote_staging_dir + "/" + self._build_cmd)
        time.sleep(2)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(self._remote_staging_dir + "/" + self._build_cmd, timeout=1200000)
        time.sleep(2)
        build_errors = ssh_stderr.readlines()

        print("Build complete. Fetching logs.")
        sftp.get(self._remote_result_dir + "/" + BUILD_LOG, self._result_dir + "/" + target + "/" + BUILD_LOG)
        sftp.close()
        self.write_to_file(build_errors, self._result_dir + "/" + target + "/" + BUILD_LOG + ERR_LOG)
