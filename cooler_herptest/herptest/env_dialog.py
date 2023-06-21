from PySide2 import QtCore, QtWidgets, QtGui
import os
import env_wrapper


class EnvDialog:
    #creates a self.layout that can be "stolen" by another widget to allow UI replacement without widget replacement
    def __init__(self, exit_call):
        self.generateEnvLoadScreen()
        self.exit_call = exit_call

    def generateEnvLoadScreen(self):
        self.layout = QtWidgets.QVBoxLayout()
        self.entryGroup = QtWidgets.QGridLayout()
        self.envLabel = QtWidgets.QLabel("canvas.env not found! Enter API token below:")
        self.envLabel.setFixedHeight(30)
        self.envEntry = QtWidgets.QLineEdit()

        self.envSubmit = QtWidgets.QPushButton("Populate canvas.env")
        self.envSubmit.setFixedWidth(170)
        self.envSubmit.clicked.connect(self.handleEnvLoad)

        self.errorText = QtWidgets.QLabel()
        self.errorText.setFixedHeight(30)

        self.entryGroup.addWidget(self.envLabel, 0,0)
        self.entryGroup.addWidget(self.envEntry, 1,0)
        self.entryGroup.addWidget(self.envSubmit, 1,1)
        self.entryGroup.addWidget(self.errorText, 0,1)

        self.layout.setContentsMargins(10,10,10,10)
        self.layout.addLayout(self.entryGroup)


    def handleEnvLoad(self):
        token = self.envEntry.text() 
        if len(token) == 64+5 and token[4] == "~":
            #haha nice
            ew = env_wrapper.EnvWrapper()
            ew.set_env(token, "TOKEN")
            self.exit_call()
        else:
            self.errorText.setText("Invalid/empty token")
            self.errorText.setStyleSheet("color: red")
            
