#!/usr/bin/env python3

__version__ = "0.0.1"

import sys
from PyQt4 import QtCore, QtGui
try:
    from linkbot_jig_programmer.mainwindow import Ui_MainWindow
except:
    from mainwindow import Ui_MainWindow
import linkbot
import time
import glob
import threading
import os
import subprocess
import serial
import pystk500v2 as stk
import random
import traceback
import asyncio

from pkg_resources import resource_filename, resource_listdir
fallback_hex_file = ''
fallback_eeprom_file = ''
firmware_files = resource_listdir(__name__, 'hexfiles')
firmware_files.sort()
firmware_basename = os.path.splitext(
    resource_filename(__name__, os.path.join('hexfiles', firmware_files[0])))[0]
fallback_hex_file = firmware_basename + '.hex'

bootloader_file = resource_filename(__name__, 
    os.path.join('bootloader', 'ATmegaBOOT_168_mega128rfa1_8MHz.hex'))

def _getSerialPorts():
  if os.name == 'nt':
    available = []
    for i in range(256):
      try:
        s = serial.Serial(i)
        available.append('\\\\.\\COM'+str(i+1))
        s.close()
      except Serial.SerialException:
        pass
    return available
  else:
    from serial.tools import list_ports
    return [port[0] for port in list_ports.comports()]

def findHexFiles():
    ''' Returns a list of hex file base names absolute paths with no extensions.
    '''
    hexfiles = [firmware_basename]
    try:
        files = glob.glob(
            os.environ['HOME'] + 
            '/.local/share/Barobo/LinkbotLabs/firmware/*.hex')
        files = map( lambda x: os.path.splitext(x)[0], files)
        # For each file, make sure the eeprom file also exists
        for f in files:
            if os.path.isfile(f + '.eeprom'):
                hexfiles += [f]

        files = glob.glob(
            os.environ['HOME'] + 
            '/usr/share/Barobo/LinkbotLabs/firmware/*.hex')
        files = map( lambda x: os.path.splitext(x)[0], files)
        # For each file, make sure the eeprom file also exists
        for f in files:
            if os.path.isfile(f + '.eeprom'):
                hexfiles += [f]
    except:
        pass

    return hexfiles

class StartQT4(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.isRunning = True
        self.setWindowTitle('Linkbot Jig Main-Board Programmer')

        # Populate the firmware hex files combobox
        for f in sorted(findHexFiles()):
            self.ui.firmwareversion_comboBox.addItem(f)

        for p in sorted(_getSerialPorts()):
            self.ui.comport_comboBox.addItem(p)

        self.disableTestButtons()
        self.ui.robotid_lineEdit.textChanged.connect(self.robotIdChanged)
        self.ui.flash_pushButton.clicked.connect(self.startProgramming)
        self.ui.test_pushButton.clicked.connect(self.runTest)
        self.ui.progressBar.setValue(0)
        self.progressTimer = QtCore.QTimer(self)
        self.progressTimer.timeout.connect(self.updateProgress)

    def robotIdChanged(self, text):
        if len(text) == 4:
            self.enableTestButtons()
        else:
            self.disableTestButtons()

    def disableTestButtons(self):
        self.ui.test_pushButton.setEnabled(False)
        self.ui.flashtest_pushButton.setEnabled(False)

    def enableTestButtons(self):
        self.ui.test_pushButton.setEnabled(True)
        self.ui.flashtest_pushButton.setEnabled(True)

    def disableButtons(self):
        self.disableTestButtons()
        self.ui.flash_pushButton.setEnabled(False)

    def enableButtons(self):
        self.enableTestButtons()
        self.ui.flash_pushButton.setEnabled(True)

    def startProgramming(self): 
        serialPort = self.ui.comport_comboBox.currentText()
        firmwareFile = self.ui.firmwareversion_comboBox.currentText()+'.hex'
        try:
          self.programmer = stk.ATmega128rfa1Programmer(serialPort)
        except Exception as e:
          QtGui.QMessageBox.warning(self, "Programming Exception",
            'Unable to connect to programmer at com port '+ serialPort + 
            '. ' + str(e))
          traceback.print_exc()
          return
        
        # Generate a random ID for the new board
        self.serialID = "{:04d}".format(random.randint(1000, 9999))
        try:
            self.disableButtons()
            self.programmer.programAllAsync( serialID=self.serialID,
                                             hexfiles=[firmwareFile, bootloader_file],
                                             verify=False
                                           )
            self.progressTimer.start(500)
        except Exception as e:
          QtGui.QMessageBox.warning(self, "Programming Exception",
            'Unable to connect to programmer at com port '+ serialPort + 
            '. ' + str(e))
          traceback.print_exc()
          return
    
    def runTest(self):
        self.disableButtons()
        testThread = RobotTestThread(self)
        testThread.setTestRobotId(self.ui.robotid_lineEdit.text())
        testThread.threadFinished.connect(self.testFinished)
        testThread.start()

    def testFinished(self):
        self.enableButtons()

    def updateProgress(self):
        self.ui.progressBar.setValue(self.programmer.getProgress()*100)
        if not self.programmer.isProgramming():
            self.enableButtons()
            self.progressTimer.stop()

class RobotTestThread(QtCore.QThread):
    threadFinished = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        QtCore.QThread.__init__(self, *args, **kwargs)

    def setTestRobotId(self, id):
        self.testBotId = id

    def run(self):
        # Power the motors forward and backward
        l = linkbot.Linkbot()
        if l.getFormFactor() != 3:
            l.setMotorPowers(255, 255, 255)
            time.sleep(2)
            l.setMotorPowers(-255, -255, -255)
            time.sleep(2)
            (x,y,z) = l.getAccelerometerData()
            if abs(x) < 0.1 and abs(y) < 0.1 and (abs(z)-1) < 0.1:
                pass
            else:
                QtGui.QMessageBox.warning(self, "Accelerometer anomaly detected.")
        try:
            testbot = linkbot.Linkbot(self.testBotId)
            print(testbot.getJointAngles())
            del testbot
        except:
            QtGui.QMessageBox.warning(self, 
                "Error communicating with remote robot")
        self.threadFinished.emit()

def main():
    app = QtGui.QApplication(sys.argv)
    myapp = StartQT4()
    myapp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
