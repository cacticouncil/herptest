import os

class MossEnvWrapper:
    def __init__(self):
        pass



    # modularized input function for env wrapper if needed for implemenation
    def input_func(self):
        self.input_checker = input()
        try:
            self.input_checker = str(self.input_checker)
        except:
            raise ValueError("Key of incorrect type.")
        return self.input_checker



    # Populates the keys into moss.env permanently
    def populate_env(self):
        with open('moss.env', 'w') as f:
            print("Enter Moss Token (USERID): ")
            self.moss_token = "USERID="+str(self.input_func()+"\n")
            f.write(self.moss_token),print("Moss token stored.")



    # Brings moss key into virtual env during runtime
    def read_env(self):
        with open('moss.env','r') as c:
            for line in c.readlines():
                try:
                    self.key,self.value = line.split('=')
                    os.putenv(self.key, self.value)
                except ValueError:
                    pass



    # Clear the contents of the canvas.env
    def clear_env(self):
        open('moss.env', 'w').close()
