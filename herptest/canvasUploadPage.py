from PySide2 import QtCore, QtWidgets, QtGui
import os, subprocess
import numpy as np
from herptest import canvas_interface

class CanvasUploadPage(canvas_interface.AbstractCanvasInterface):

    def __init__(self):
        super().__init__()

        self.fileReady = False

    def createControls(self):
        #this method gets called during the parent class's createUI method and injects the necessary controls
        self.uploadContainer = QtWidgets.QGridLayout()
        self.csvLabel = QtWidgets.QLabel("Select CSV to Upload")
        self.csvLabel.setMaximumHeight(50)
        self.csvPathField = QtWidgets.QLineEdit()
        self.csvSelect = QtWidgets.QPushButton("Browse")
        self.csvSelect.setFixedWidth(100)
        self.csvSelect.clicked.connect(self.uploadFilePicker)

        self.modeLabel = QtWidgets.QLabel("Upload CSV as:")
        self.modeLayout = QtWidgets.QVBoxLayout()
        self.modeSelectGroup = QtWidgets.QButtonGroup()
        self.modeSelectGroup.setExclusive(True)
        self.modeSelectRubric = QtWidgets.QCheckBox("Structured Rubric")
        self.modeSelectTests = QtWidgets.QCheckBox("Test Suite Results")
        self.modeSelectGroup.addButton(self.modeSelectRubric)
        self.modeSelectGroup.addButton(self.modeSelectTests)
        self.modeLayout.addWidget(self.modeSelectRubric)
        self.modeLayout.addWidget(self.modeSelectTests)
        self.modeLayout.setContentsMargins(10,10,10,10)

        self.uploadButton = QtWidgets.QPushButton("Upload")
        self.uploadButton.setFixedWidth(100)
        self.uploadButton.setFixedHeight(50)
        self.uploadButton.clicked.connect(self.handleUpload)
        self.uploadButton.setEnabled(False)

        self.lateLabel = QtWidgets.QLabel("Specify late policy as days/points deducted single-spaced list")
        self.lateLabel.setMaximumHeight(20)
        self.lateField = QtWidgets.QLineEdit()


        self.uploadContainer.addWidget(self.csvLabel,0,0)
        self.uploadContainer.addWidget(self.csvPathField,1,0)
        self.uploadContainer.setAlignment(self.csvPathField, QtCore.Qt.AlignTop)
        self.uploadContainer.addWidget(self.csvSelect,1,1)
        self.uploadContainer.setAlignment(self.csvSelect, QtCore.Qt.AlignTop)
        self.uploadContainer.addWidget(self.modeLabel,0,2)
        self.uploadContainer.addLayout(self.modeLayout,1,2)
        self.uploadContainer.setAlignment(self.modeLayout, QtCore.Qt.AlignTop)
        self.uploadContainer.addWidget(self.uploadButton,1,3)
        self.uploadContainer.addWidget(self.lateLabel,1,0)
        self.uploadContainer.addWidget(self.lateField,1,0)
        self.uploadContainer.setAlignment(self.lateLabel, QtCore.Qt.AlignVCenter)
        self.uploadContainer.setAlignment(self.lateField, QtCore.Qt.AlignBottom)

        #self.layout is the reference to the layout manager that WE control, not the .layout() that returns the layout
        #   manager tracked by QT
        self.layout.setAlignment(self.uploadContainer, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.layout.addLayout(self.uploadContainer)

    def onSelect(self):
        #called in the handleSelect method of the parent, we need to invoke approveUpload()
        self.approveUpload()

    def approveUpload(self):
        if self.fileReady and self.assignmentReady:
            self.uploadButton.setEnabled(True)
        else:
            self.uploadButton.setEnabled(False)

    def uploadFilePicker(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dialog.setWindowTitle("Select File to Upload")
        dialog.setNameFilter("CSV (*.csv)")

        if dialog.exec_():
            self.uploadPath = dialog.selectedFiles()[0]
            self.csvPathField.setText(self.uploadPath)
            self.fileReady = True
        self.approveUpload()
   
    def handleUpload(self):
        #can we do this in a worker thread? maybe
        #this method uses the canvasWrapper and canvasUtil attributes of the parent class
        if self.modeSelectTests.checkState() == QtCore.Qt.Checked:
            #test results mode, call matty's code
            #print("test suite mode!")
            self.late_policy = list(map(float, self.lateField.text.split()))
            self.canvasWrapper.push_grades(self.currentCourse, self.currentAssignment, self.uploadPath, self.late_policy)
        elif self.modeSelectRubric.checkState() == QtCore.Qt.Checked:
            #rubric mode, call tyler's code
            #print("rubric mode!")
            
            self.canvasUtil.process_and_upload_file(self.currentCourseId, self.currentAssignment, self.uploadPath)
        else:
            #neither was selected, create a warning dialog and do nothing
            dialog = QtWidgets.QMessageBox()
            dialog.setText('Select either "Structured Rubric" or "Test Suite Results " mode in order to upload.')
            dialog.setWindowTitle('Select an Upload Mode!')
            dialog.exec_()
        #print("upload {}".format(self.uploadPath))
