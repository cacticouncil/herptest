from PySide2 import QtCore, QtWidgets, QtGui
import os, subprocess, json, shutil

class TestSuiteCreator(QtWidgets.QWidget):

    class TestCase(QtWidgets.QWidget):
        def __init__(self, name, testValue, matchType, startToken, endToken):
            super().__init__()
            self.layout = QtWidgets.QHBoxLayout()
            self.textBox = QtWidgets.QVBoxLayout()
            self.inputTitle = QtWidgets.QLabel("Enter input for test case (separate inputs with newline):")
            self.inputTitle.setFixedHeight(30)
            self.inputText = QtWidgets.QPlainTextEdit()
            self.textBox.addWidget(self.inputTitle)
            self.textBox.addWidget(self.inputText)
            self.layout.addLayout(self.textBox)
            self.setLayout(self.layout)
            self.name = name
            self.points = testValue
            self.matchType = matchType
            self.startToken = startToken
            self.endToken = endToken



    def __init__(self, defaultTestValue=10, defaultMatchType=0, defaultStartToken=0, defaultEndToken=0):
        super().__init__()

        self.defaultTestValue = defaultTestValue
        self.defaultMatchType = defaultMatchType
        self.defaultStartToken = defaultStartToken
        self.defaultEndToken = defaultEndToken
        self.savePath = None
        self.solutionFile = None

        self.containerLayout = QtWidgets.QVBoxLayout()
        self.containerLayout.setContentsMargins(0,0,0,0)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(5,5,5,5)
        self.createMenuBar()
        
        self.createTestCaseContainer()
        
        self.generateTestSuiteContainer()

        self.containerLayout.addLayout(self.layout)
        self.createBreadcrumb()
        self.setLayout(self.containerLayout)



    def createBreadcrumb(self):
        self.breadcrumbBar = QtWidgets.QStatusBar()
        self.breadcrumb = QtWidgets.QLabel()

        self.totalPoints = QtWidgets.QLabel()
        self.breadcrumbBar.addPermanentWidget(self.totalPoints)

        self.breadcrumbBar.setStyleSheet("background-color:#dddddd")
        self.breadcrumbBar.setSizeGripEnabled(False)
        self.breadcrumbBar.addWidget(self.breadcrumb)
        self.breadcrumbBar.setFixedHeight(20)
        self.breadcrumbBar.setContentsMargins(5,0,5,0)
        self.containerLayout.addWidget(self.breadcrumbBar)
        self.updateBreadcrumb()
        self.updateTotalPoints()



    def updateBreadcrumb(self):
        if not self.savePath:
            self.breadcrumb.setText("No test case file saved...")
        else:
            self.breadcrumb.setText("Active Test Suite: " + os.path.basename(self.savePath))



    def updateTotalPoints(self):
        #make sure that the current test case gets updated, will not call on Add Test Case widget
        if self.testCaseStack.count() != 1:
            self.testCaseStack.widget(self.testCaseStack.currentIndex()).points = self.testCasePoints.value()

        total = 0
        for index in range(0, self.testCaseStack.count()-1):
            total += self.testCaseStack.widget(index).points
        self.totalPoints.setText(str(total) + " Total Points | " + str(self.testCaseStack.count()-1) + " test cases")



    def updateMatchType(self, index):
        # match type converted to values used in tests.py on test suite code generation
        self.testCaseStack.widget(self.testCaseStack.currentIndex()).matchType = index
        self.checkEnableWidgets()
        


    def updateStartToken(self, token):
        self.testCaseStack.widget(self.testCaseStack.currentIndex()).startToken = token



    def updateEndToken(self, token):
        self.testCaseStack.widget(self.testCaseStack.currentIndex()).endToken = token



    def createMenuBar(self):
        self.menuBar = QtWidgets.QMenuBar()
        self.fileMenu = self.menuBar.addMenu("File")
        self.fileMenuNew = self.fileMenu.addAction("New Test Suite")
        self.fileMenuNew.triggered.connect(lambda: self.newTestSuite())
        self.fileMenuOpen = self.fileMenu.addAction("Open")
        self.fileMenuOpen.setShortcuts(QtGui.QKeySequence.Open)
        self.fileMenuOpen.triggered.connect(lambda: self.openTestSuite())
        self.fileMenuSave = self.fileMenu.addAction("Save")
        self.fileMenuSave.setShortcuts(QtGui.QKeySequence.Save)
        self.fileMenuSave.triggered.connect(lambda: self.saveTestSuite())
        self.fileMenuSaveAs = self.fileMenu.addAction("Save As")
        self.fileMenuSaveAs.setShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.SHIFT + QtCore.Qt.Key_S,))
        self.fileMenuSaveAs.triggered.connect(lambda: self.saveTestSuite(saveAs=True))

        self.testCaseMenu = self.menuBar.addMenu("Test Cases")
        self.testCaseAdd = self.testCaseMenu.addAction("Add Test Case")
        self.testCaseAdd.triggered.connect(lambda: self.addTestCase())
        self.testCaseRename = self.testCaseMenu.addAction("Rename Test Case")
        self.testCaseRename.triggered.connect(lambda: self.renameTestCase(self.testCaseStack.currentIndex()))
        self.testCaseDelete = self.testCaseMenu.addAction("Delete Test Case")
        self.testCaseDelete.triggered.connect(lambda: self.removeTestCase(self.testCaseStack.currentIndex()))
      
        self.layout.addWidget(self.menuBar)
        self.layout.setAlignment(self.menuBar, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)



    def createTestCaseContainer(self):
        self.testCaseStack =  QtWidgets.QStackedWidget()
        self.testCaseComboBox = QtWidgets.QComboBox()
        self.testCaseComboBox.setFixedWidth(200)
        self.testCaseComboBox.activated[int].connect(self.changeTestCase)
        self.testCaseComboBox.addItem("+ Add Test Case")
        self.nullTestCase = QtWidgets.QLabel('Click "Add Test Case" to get started!')
        self.testCaseStack.addWidget(self.nullTestCase)
        self.layout.setAlignment(self.nullTestCase, QtCore.Qt.AlignCenter)

        self.testCasePointsLabel = QtWidgets.QLabel("Points:")
        self.testCasePointsLabel.setFixedWidth(40)
        self.testCasePoints = QtWidgets.QSpinBox()
        self.testCasePoints.setValue(self.defaultTestValue)
        self.testCasePoints.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.testCasePoints.valueChanged.connect(self.updateTotalPoints)
        self.testCasePoints.setRange(0,999999)
        self.testCasePoints.setFixedWidth(50)
        self.testCasePoints.setDisabled(True)

        self.matchTypeLabel = QtWidgets.QLabel("Match type:")
        self.matchTypeLabel.setFixedWidth(75)
        self.matchTypeComboBox = QtWidgets.QComboBox()
        self.matchTypeComboBox.setFixedWidth(250)
        self.matchTypeComboBox.addItem("Exact Match")
        self.matchTypeComboBox.addItem("Result contains benchmark subset")
        self.matchTypeComboBox.addItem("Result contains benchmark superset")
        self.matchTypeComboBox.activated[int].connect(self.updateMatchType)
        self.matchTypeComboBox.setDisabled(True)

        self.startTokenLabel = QtWidgets.QLabel("Start token:")
        self.startTokenLabel.setFixedWidth(75)
        self.startToken = QtWidgets.QSpinBox()
        self.startToken.setValue(self.defaultStartToken)
        self.startToken.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.startToken.valueChanged.connect(self.updateStartToken)
        self.startToken.setRange(-99999, 99999)
        self.startToken.setFixedWidth(50)
        self.startToken.setDisabled(True)
        
        self.endTokenLabel = QtWidgets.QLabel("End token:")
        self.endTokenLabel.setFixedWidth(70)
        self.endToken = QtWidgets.QSpinBox()
        self.endToken.setValue(self.defaultEndToken)
        self.endToken.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.endToken.valueChanged.connect(self.updateEndToken)
        self.endToken.setRange(-99999, 99999)
        self.endToken.setFixedWidth(50)
        self.endToken.setDisabled(True)

        self.testCaseControls = QtWidgets.QHBoxLayout()
        self.testCaseControls.setContentsMargins(10,20,10,0)
        self.testCaseControls.addWidget(self.testCaseComboBox)
        self.testCaseControls.addSpacing(10)
        self.testCaseControls.addWidget(self.testCasePointsLabel)
        self.testCaseControls.addWidget(self.testCasePoints)
        self.testCaseControls.addSpacing(10)
        self.testCaseControls.addWidget(self.matchTypeLabel)
        self.testCaseControls.addWidget(self.matchTypeComboBox)
        self.testCaseControls.addSpacing(10)
        self.testCaseControls.addWidget(self.startTokenLabel)
        self.testCaseControls.addWidget(self.startToken)
        self.testCaseControls.addWidget(self.endTokenLabel)
        self.testCaseControls.addWidget(self.endToken)

        self.layout.addLayout(self.testCaseControls)

        self.layout.addWidget(self.testCaseStack)



    def generateTestSuiteContainer(self):
        self.generateTestSuiteButton = QtWidgets.QPushButton("Generate Test Suite")
        self.generateTestSuiteButton.setFixedWidth(200)
        self.generateTestSuiteButton.clicked.connect(self.solutionFilePicker)
        self.generateTestSuiteButton.setDisabled(True)
        self.layout.addWidget(self.generateTestSuiteButton)
        self.layout.setAlignment(self.generateTestSuiteButton, QtCore.Qt.AlignRight)
        

    
    def solutionFilePicker(self):
        newSolutionFile, _ = QtWidgets.QFileDialog.getOpenFileName(self, caption="Select Solution Code", filter="Python Files (*.py)")

        if newSolutionFile:
            testSuiteDir = QtWidgets.QFileDialog.getExistingDirectory(self, caption="Select Test Suite Save Path", options=QtWidgets.QFileDialog.ShowDirsOnly)
            if testSuiteDir:
                self.solutionFile = newSolutionFile
                os.chdir(testSuiteDir)
                self.writeTestSuiteJson()
                folderNameTuple = ("Build", "Projects", "Results", "Settings", "Source", "Build/Framework", "Build/Subject", "Source/Framework", "Source/Subject", "Projects/Empty", "Projects/Solution")
                for folderName in folderNameTuple:
                    try:
                        os.mkdir(os.path.join(os.getcwd(), folderName))
                    except OSError: #error may be raised if directory already exists
                        continue
                
                template_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_suite_templates")

                with open(os.path.join(template_folder, "tests_template.py"), 'r') as file:
                    projectTemplateLines = file.readlines()
                    testCases = {}
                    testCases[os.path.basename(self.solutionFile)] = []
                    for index in range(0, self.testCaseStack.count() - 1):
                        if self.testCaseStack.widget(index).matchType == 2:
                            currMatchType = -1
                        else:
                            currMatchType = self.testCaseStack.widget(index).matchType

                        testCase = (
                            self.testCaseStack.widget(index).inputText.toPlainText().strip().split("\n"),
                            self.testCaseStack.widget(index).name,
                            currMatchType, 
                            self.testCaseStack.widget(index).startToken,
                            self.testCaseStack.widget(index).endToken
                        )
                        testCases[os.path.basename(self.solutionFile)].append(testCase)
                    projectTemplateLines[21] = "test_cases = " + str(testCases)+ '\n'

                with open(os.path.join(os.getcwd(), "Settings", "tests.py"), 'w') as file:
                    file.writelines(projectTemplateLines)
                
                with open(os.path.join(template_folder, "project_template.py"), 'r') as file:
                    testsTemplateLines = file.readlines()

                    total = 0.0
                    for index in range(0, self.testCaseStack.count()-1):
                        total += self.testCaseStack.widget(index).points

                    projects = [(
                        os.path.basename(os.path.splitext(self.solutionFile)[0]),
                        os.path.basename(self.solutionFile),
                        total
                    )]

                    testsTemplateLines[22] = "projects = " + str(projects) + '\n'

                with open(os.path.join(os.getcwd(), "Settings", "project.py"), 'w') as file:
                    file.writelines(testsTemplateLines)
                    
                shutil.copy(os.path.join(template_folder, "config_template.py"), os.path.join(os.getcwd(), "config.py"))
                shutil.copy(self.solutionFile, os.path.join(os.getcwd(), "Source/Framework"))
                shutil.copy(self.solutionFile, os.path.join(os.getcwd(), "Build/Framework"))
                shutil.copy(self.solutionFile, os.path.join(os.getcwd(), "Projects/Solution"))
                with open(os.path.join(os.getcwd(), "Source", "Subject", os.path.basename(self.solutionFile)), 'w') as file:
                    file.write("pass")
                with open(os.path.join(os.getcwd(), "Build", "Subject", os.path.basename(self.solutionFile)), 'w') as file:
                    file.write("pass")
                with open(os.path.join(os.getcwd(), "Projects", "Empty", os.path.basename(self.solutionFile)), 'w') as file:
                    file.write("pass")

                self.updateBreadcrumb()



    def writeTestSuiteJson(self):
        data = {}
        #test suite solution file only written when generating test suite (not saving)
        if self.solutionFile:
            data['solution_file'] = self.solutionFile
        data['test_cases'] = []
        for index in range(0, self.testCaseStack.count()-1):
            testCase = {}
            testCase['test_case_title'] = self.testCaseStack.widget(index).name
            testCase['input_list'] = self.testCaseStack.widget(index).inputText.toPlainText().strip().split("\n")
            testCase['points'] = self.testCaseStack.widget(index).points
            if self.testCaseStack.widget(index).matchType == 2:
                testCase['match_type'] = -1
            else:
                testCase['match_type'] = self.testCaseStack.widget(index).matchType
            testCase['start_token'] = self.testCaseStack.widget(index).startToken
            testCase['end_token'] = self.testCaseStack.widget(index).endToken
            data['test_cases'].append(testCase)
        #if a save path has not already been designated (user has not previously saved test suite), save path defaults to cwd
        if not self.savePath:
            newFileName = os.path.basename(os.path.splitext(self.solutionFile)[0]) + "_test_cases.json"
            self.savePath = os.path.join(os.getcwd(), newFileName)
        with open(self.savePath, 'w') as outfile: 
            json.dump(data, outfile)



    def checkEnableWidgets(self):
        if(self.testCaseStack.count() > 1):
            self.generateTestSuiteButton.setEnabled(True)
            self.testCasePoints.setEnabled(True)
            self.matchTypeComboBox.setEnabled(True)
            currMatchType = self.testCaseStack.widget(self.testCaseStack.currentIndex()).matchType
            if(currMatchType == 1 or currMatchType == 2):
                self.startToken.setEnabled(True)
                self.endToken.setEnabled(True)
            else:
                self.startToken.setDisabled(True)
                self.endToken.setDisabled(True)
        else:
            self.generateTestSuiteButton.setDisabled(True)
            self.testCasePoints.setDisabled(True)
            self.matchTypeComboBox.setDisabled(True)
        


    def changeTestCase(self, index):
        if index == self.testCaseComboBox.count()-1:
            self.addTestCase()
        else:
            self.testCaseComboBox.setCurrentIndex(index)
            self.testCaseStack.setCurrentIndex(index)
            self.testCasePoints.setValue(self.testCaseStack.widget(index).points)
            self.matchTypeComboBox.setCurrentIndex(self.testCaseStack.widget(index).matchType)
            self.startToken.setValue(self.testCaseStack.widget(index).startToken)
            self.endToken.setValue(self.testCaseStack.widget(index).endToken)
            self.checkEnableWidgets()



    def addTestCase(self):
        testCaseTitle, ok = QtWidgets.QInputDialog().getText(self, "Test Case Name", "Enter test case name:", QtWidgets.QLineEdit.Normal) 
        if ok and testCaseTitle:
            self.testCaseStack.insertWidget(self.testCaseStack.count()-1, self.TestCase(testCaseTitle, self.defaultTestValue, self.defaultMatchType, self.defaultStartToken, self.defaultEndToken))
            self.testCaseComboBox.insertItem(self.testCaseComboBox.count()-1, testCaseTitle)
            self.changeTestCase(self.testCaseStack.count()-2)
            self.updateTotalPoints()
            self.checkEnableWidgets()
        else:
            #if user cancels, test case switches to last test case
            if self.testCaseStack.count() > 1:
                self.changeTestCase(self.testCaseStack.count()-2)
            self.checkEnableWidgets()
                


    def removeTestCase(self, index):
        # prevents deleting Add Test Case item
        if self.testCaseComboBox.count() == 1:
            return

        buttonClicked = QtWidgets.QMessageBox.warning(self, "Delete Test Case", "Are you sure you want to delete this test case?", QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Cancel)
        
        if buttonClicked == QtWidgets.QMessageBox.Ok:

            target = self.testCaseStack.widget(index)
            self.testCaseStack.removeWidget(target)
            self.testCaseComboBox.removeItem(index)
            self.updateTotalPoints()

            if self.testCaseComboBox.count() > 1:
                if self.testCaseComboBox.currentIndex() == self.testCaseComboBox.count()-1:
                    self.changeTestCase(self.testCaseComboBox.currentIndex()-1)

                if self.testCaseStack.count() == 2:
                    #we just deleted the penultimate real test case, make sure that the remaining one is selected
                    self.changeTestCase(0)
            self.checkEnableWidgets()



    def renameTestCase(self, index):
        if self.testCaseStack.currentIndex() == self.testCaseStack.count() - 1:
            return

        dialog, ok = QtWidgets.QInputDialog().getText(self, "Rename Test Case", "Enter new name:", QtWidgets.QLineEdit.Normal) 

        if ok and dialog:
            self.testCaseComboBox.setItemText(index, dialog)
            self.testCaseStack.widget(index).name = dialog



    def newTestSuite(self):
        if self.testCaseComboBox.count() == 1:
            return

        buttonClicked = QtWidgets.QMessageBox.warning(self, "Delete Test Case", "Do you want to save your changes?", QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Save)
        if buttonClicked == QtWidgets.QMessageBox.Cancel:
            return
        elif buttonClicked ==  QtWidgets.QMessageBox.Save:
            if(self.saveTestSuite() == -1):
                return
            while self.testCaseComboBox.count() > 1:
                target = self.testCaseStack.widget(0)
                self.testCaseStack.removeWidget(target)
                self.testCaseComboBox.removeItem(0)
        else:  
            while self.testCaseComboBox.count() > 1:
                target = self.testCaseStack.widget(0)
                self.testCaseStack.removeWidget(target)
                self.testCaseComboBox.removeItem(0)
            
        self.savePath = None
        self.checkEnableWidgets()
        self.updateTotalPoints()
        self.updateBreadcrumb()



    def openTestSuite(self):
        testCasesPath, _ = QtWidgets.QFileDialog.getOpenFileName(self, caption="Select Test Cases File", filter="JSON Files (*.json)")
        if testCasesPath:
            #remove currently displayed test cases 
            while self.testCaseComboBox.count() > 1:
                target = self.testCaseStack.widget(0)
                self.testCaseStack.removeWidget(target)
                self.testCaseComboBox.removeItem(0)
            with open(testCasesPath, "r") as readFile:
                data = json.load(readFile)
                self.savePath = testCasesPath
                if "solution_file" in data:
                    self.solutionFile = data["solution_file"]
                testCases = data["test_cases"]
                for testCase in testCases:
                    testCaseTitle = testCase['test_case_title']
                    inputList = testCase['input_list']
                    points = testCase['points']
                    if testCase['match_type'] == -1:
                        matchType = 2
                    else:
                        matchType = testCase['match_type']
                    startToken = testCase['start_token']
                    endToken = testCase['end_token']
                    self.testCaseStack.insertWidget(self.testCaseStack.count()-1, self.TestCase(testCaseTitle, points, matchType, startToken, endToken))
                    self.testCaseStack.widget(self.testCaseStack.count()-2).inputText.setPlainText("\n".join(inputList))
                    self.testCaseComboBox.insertItem(self.testCaseComboBox.count()-1, testCaseTitle)
            self.changeTestCase(0)
            self.checkEnableWidgets()
            self.updateTotalPoints()
            self.updateBreadcrumb()



    def saveTestSuite(self, saveAs=False):
        if(self.testCaseStack.count() == 1):
            return
        #if user clicks saveAs or if the user has not saved before
        if not self.savePath or saveAs:
            newSavePath, _ = QtWidgets.QFileDialog.getSaveFileName(self, caption="Select Test Cases Save Path", filter="JSON Files (*.json)")
            if newSavePath:
                if not newSavePath.endswith(".json"):
                    newSavePath = newSavePath + ".json"
                self.savePath = newSavePath
                self.writeTestSuiteJson()
                self.updateBreadcrumb()
        else:
            self.writeTestSuiteJson()
