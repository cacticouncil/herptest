import sys, os
import time, random, pathlib
from PySide2 import QtCore, QtWidgets, QtGui
import homePage, testSuiteCreator, resultsPage, canvasUploadPage, autopullElmaPage, vmPage



def initEnviron():
    os.environ["LIBGL_ALWAYS_INDIRECT"] = "1" #necessary to avoid openGL errors with accessing Windows openGL from WSL
    os.environ["XDG_RUNTIME_DIR"] = "/tmp/peng-runtime" #used by qt for cache
def initWindow():

    window = QtWidgets.QMainWindow()
    
    tabContainer =  QtWidgets.QTabWidget()

    #create all the tabs for the gui, save a reference to them, and add them to the tab creator
    tabContainer.addTab(homePage.HomePage(), "Run HerpTest")
    homePageInst = tabContainer.widget(0)
    tabContainer.addTab(testSuiteCreator.TestSuiteCreator(), "Create Test Suite")
    testSuiteCreatorInst = tabContainer.widget(1)
    tabContainer.addTab(resultsPage.ResultsPage(), "Test Results")
    resultsPageInst = tabContainer.widget(2)
    tabContainer.addTab(canvasUploadPage.CanvasUploadPage(), "Canvas Uploader")
    canvasUploaderInst = tabContainer.widget(3)
    tabContainer.addTab(autopullElmaPage.AutopullElmaPage(), "Auto-Pull && ELMA")
    elmaInst = tabContainer.widget(4)
    tabContainer.addTab(vmPage.VmPage(), "VM Config")
    vmPageInst = tabContainer.widget(5)


    #give the home page the funcion to call when the SHOW RESULTS button is clicked
    #pass the function to set the results page as active to the results page so data can load first
    homePageInst.setResultsFunction(resultsPageInst.loadResults, (tabContainer.setCurrentWidget, resultsPageInst))


    #add temporary tabs here (for testing)
    tabList = []
    for t in tabList:
        tabContainer.addTab(QtWidgets.QLabel("    " + t + " - Coming soon!"), t)

    window.setCentralWidget(tabContainer)
    window.setWindowTitle("HerpTest")
    window.resize(800, 800)
    
    createStatusBar(window)
    return window

def createSplash():
    loadingTips = ["Loading..."]

    splashLoc = str(pathlib.Path(__file__).parent.absolute()) + "/herpSplash.png"
    splash = QtWidgets.QSplashScreen(pixmap = QtGui.QPixmap(splashLoc))
    splash.showMessage('<h2> Tip: ' + random.choice(loadingTips) + "</h2>", QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom, QtGui.QColor(20,20,20))
    return splash

def createStatusBar(window):
    #creates the global status bar at the bottom of the ui
    status = QtWidgets.QStatusBar()
    statusMessage = QtWidgets.QLabel("HerpTest - GUI (herp-gui)")
    status.addWidget(statusMessage)
    status.setStyleSheet("background-color: #83d3f7")
    window.setStatusBar(status)

def main():
    initEnviron()
    app = QtWidgets.QApplication([])

    #handle the no-splash option 
    if len(sys.argv) > 1 and sys.argv[1] == "--no-splash":
        window = initWindow()
        window.show()
    else:
        start = time.time()
        splash = createSplash()
        splash.show()
        window = initWindow()
        end = time.time()
        if (end-start) < 2:
            time.sleep(2-(end-start))#give the user a change to see screen if they have a monstrously fast computer
        window.show()
        splash.finish(window)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()