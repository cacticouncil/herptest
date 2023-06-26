from PySide2 import QtCore, QtWidgets, QtGui
import os, subprocess, csv, math
import numpy as np


class ResultsTableModel(QtCore.QAbstractTableModel):
    #used as the model for the contents of summary.csv
    def __init__(self, data=None):
        QtCore.QAbstractTableModel.__init__(self)
        self.loadData(data)

    def loadData(self, data):
        if len(data) > 1:
            self.headers = data[0]
            self.dataDict = data[1:]
        else:
            self.headers = ["No Data"]
            self.dataDict = []

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.dataDict)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return self.headers[section]
        else:
            return "{}".format(section)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        column = index.column()
        row = index.row()

        if role == QtCore.Qt.DisplayRole:
            return self.dataDict[row][column]

        elif role == QtCore.Qt.BackgroundRole:
            return QtGui.QColor(QtCore.Qt.white)
        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignRight

        return None

class StatsModel(QtCore.QAbstractTableModel):
    #used as a model for the contents of individual student result.csv
    def __init__(self, data=None):
        QtCore.QAbstractTableModel.__init__(self)
        self.calculateStats(data)
        self.headers = ["Test Statistics", ""]

    def calculateStats(self, data):
        self.dataDict = []
        if len(data) > 1:
            scores = [float(entry[2]) for entry in data[1:]]    
            self.dataDict.append(["Mean score", np.mean(scores)])
            self.dataDict.append(["Highest score", np.max(scores)])
            self.dataDict.append(["Lowest score", np.min(scores)])
            self.dataDict.append(["Median", np.median(scores)])
            self.dataDict.append(["Q1", np.percentile(scores, 25)])
            self.dataDict.append(["Q2", np.percentile(scores, 50)])
            self.dataDict.append(["Q3", np.percentile(scores, 75)])
            self.dataDict.append(["Standard Deviation", np.std(scores)])
            for item in self.dataDict:
                item[1] = "{:.2f}".format(item[1])
        else:
            self.dataDict.append(["No Data", ""])

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.dataDict)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 2

    def headerData(self, section, orientation, role):
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return self.headers[section]
        else:
            return ""

    def data(self, index, role=QtCore.Qt.DisplayRole):
        column = index.column()
        row = index.row()

        if role == QtCore.Qt.DisplayRole:
            return self.dataDict[row][column]

        elif role == QtCore.Qt.BackgroundRole:
            return QtGui.QColor(QtCore.Qt.white)
        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignRight

        return None

class ResultsPage(QtWidgets.QWidget):
    #a flexible interface page to view the summary.csv and linked student results in one view with stats
    def __init__(self):
        super().__init__()

        
        #create the page with no data to start, this gets regenerated when new data comes in
        data = []
        
        #create the top left results table
        self.resultsContainer = QtWidgets.QHBoxLayout()

        self.model = ResultsTableModel(data)
        self.tableView = QtWidgets.QTableView()
        self.tableView.setModel(self.model)

        self.horizontalHeader = self.tableView.horizontalHeader()
        self.verticalHeader = self.tableView.verticalHeader()
        self.horizontalHeader.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.verticalHeader.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.horizontalHeader.setStretchLastSection(False)

        self.tableView.clicked[QtCore.QModelIndex].connect(self.handleSelection)

        #and create the top right detailed student results table
        self.detailsModel = ResultsTableModel(data)
        self.detailsView = QtWidgets.QTableView()
        self.detailsView.setModel(self.detailsModel)

        self.detailsHorizontalHeader = self.tableView.horizontalHeader()
        self.detailsVerticalHeader = self.tableView.verticalHeader()
        self.detailsHorizontalHeader.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.detailsVerticalHeader.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.detailsHorizontalHeader.setStretchLastSection(False)

        self.resultsContainer.addWidget(self.tableView)
        self.resultsContainer.addWidget(self.detailsView)

        #this holds the stats table, as well as the status message and loading options
        self.statsContainer = QtWidgets.QHBoxLayout()
        self.statsModel = StatsModel(data)
        self.statsView = QtWidgets.QTableView()
        self.statsView.setModel(self.statsModel)

        self.statsHeader = self.statsView.horizontalHeader()
        self.statsHeader.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.statsHeader.setStretchLastSection(False)

        self.controls = QtWidgets.QWidget()
        self.controlsContainer = QtWidgets.QGridLayout()
        self.controls.setMinimumWidth(300)

        #we create a browse and load option for flexibility; an empty load requests triggers browse anyway
        self.dataSourceLabel = QtWidgets.QLabel("Select Test Results: (summary.csv)")
        self.dataSource = QtWidgets.QLineEdit()
        self.dataSource.setText("...")
        self.dataSourceSelect = QtWidgets.QPushButton("Browse")
        self.dataSourceSelect.clicked.connect(self.dataSourceFilePicker)
        self.dataSourceSelect.setFixedWidth(100)
        self.dataSourceLoad = QtWidgets.QPushButton("Load")
        self.dataSourceLoad.clicked.connect(self.handleLoad)
        self.dataSourceLoad.setFixedWidth(100)

        self.currentStatus = QtWidgets.QLabel("")
        self.controlsContainer.addWidget(self.currentStatus, 0,0,1,2)
        self.controlsContainer.addWidget(QtWidgets.QLabel(), 1,0, 2,2)
        self.controlsContainer.addWidget(self.dataSourceLabel, 2,0, 1,2) #rowspan 1 and column span 2
        self.controlsContainer.addWidget(self.dataSource, 3,0, 1,2) #rowspan 1 and column span 2
        self.controlsContainer.addWidget(self.dataSourceSelect, 4,0)
        self.controlsContainer.addWidget(self.dataSourceLoad, 4,1)
        self.controlsContainer.addWidget(QtWidgets.QLabel(), 5,0, 2,2)

        self.controls.setLayout(self.controlsContainer)
        self.statsContainer.addWidget(self.statsView)
        self.statsContainer.addWidget(self.controls)

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.resultsContainer)
        self.layout.addLayout(self.statsContainer)

        
        self.setLayout(self.layout)
    

    def dataSourceFilePicker(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dialog.setWindowTitle("Select Test Results File:")
        dialog.setNameFilter("CSV (*.csv)")

        if dialog.exec_():
            self.dataSource.setText(dialog.selectedFiles()[0])

    def handleLoad(self):
        if self.dataSource.text() == "...":
            self.dataSourceFilePicker()
        self.loadResults(self.dataSource.text())

    def loadResults(self, resultsPath, raiseFunc= lambda x: None, raiseArgs= None):
        self.dataSource.setText(resultsPath)#useful if this is called externally
        self.dataSourcePath = resultsPath #used when calculating the directory location of detailed results
        data = []
        with open(resultsPath, newline='') as resultsFile:
            fileReader = csv.reader(resultsFile, delimiter=',')
            firstRow = True
            for row in fileReader:
                if firstRow:
                    firstRow = False
                    data.append(row + ["Show Details"])
                else:
                    data.append(row + ['->'])


        #create the new data model and plug it into the view, resize
        self.model = ResultsTableModel(data)
        self.tableView.setModel(self.model)
        for i in range(0,self.model.columnCount()):
            self.tableView.resizeColumnToContents(i)

        #calculate the stats and create the model, plug it into the view, resize
        self.statsModel = StatsModel(data)
        self.statsView.setModel(self.statsModel)
        for i in range(0,self.statsModel.columnCount()):
            self.statsView.resizeColumnToContents(i)

        raiseFunc(raiseArgs)

    def showDetails(self, studentName, studentLMS):
        #this gets triggered to replace the detailed student results page
        data = []
        resultsDirectory = self.dataSourcePath.rsplit("/", 1)[0]#removes "summary.csv" from path
        studentDirName = studentName
        if studentLMS != "NONE":
            #students can have an LMS or NONE, don't append _NONE to blanks
            studentDirName += f"_{studentLMS}"
        studentFilePath = resultsDirectory + f"/{studentDirName}/result.csv"
        with open(studentFilePath, newline='') as resultsFile:
            fileReader = csv.reader(resultsFile, delimiter=',')
            rowsToSkip = 5
            numTestCases = -1
            data.append(["", "", "", ""])
            for row in fileReader:
                if rowsToSkip == 3:
                    data.append(["Test-Set: " + row[0].rsplit(" ", 1)[1], "", "", ""])
                if rowsToSkip == 2:
                    #this row contains the number of tests, use this to separate the stats
                    numTestCases = int(row[0].rsplit(":", 1)[1][:-1])
                if rowsToSkip > 0:
                    rowsToSkip -= 1
                    continue

                if numTestCases < 0:
                    #no more test cases, read the footer information
                    if len(row) > 0:
                        if "Test-Set" in row[0]:
                            data.append(["Test-Set: " + row[0].rsplit(" ", 1)[1], "", "", ""])
                            rowsToSkip = 2
                        else:
                            text = row[0].rsplit(":", 1)[0]
                            num = row[0].rsplit(":", 1)[1]
                            data.append([text, num, "", ""])
                    else:
                        data.append(["", "", "", ""])
                else:
                    #keep processing
                    data.append(row)
                    numTestCases -= 1

        
        self.detailsModel = ResultsTableModel(data)
        self.detailsView.setModel(self.detailsModel)
        for i in range(0,self.detailsModel.columnCount()):
            self.detailsView.resizeColumnToContents(i)
        self.currentStatus.setText(f"Showing Details for {studentDirName}")

    def handleSelection(self, index):
        #detects when we should change the details view
        data = self.model.data(index)
        if data.find("->") != -1:
            name = self.model.data(self.model.createIndex(index.row(), 0))
            lms = self.model.data(self.model.createIndex(index.row(), 1))
            self.showDetails(name, lms)
