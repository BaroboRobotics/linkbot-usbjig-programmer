#!/usr/bin/env python3

__version__ = "0.0.4"

import sys
from PyQt4 import QtCore, QtGui
try:
    from linkbot_usbjig_programmer.mainwindow import Ui_MainWindow
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

from pkg_resources import resource_filename, resource_listdir

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
    fallback_hex_file = ''
    fallback_eeprom_file = ''
    firmware_files = resource_listdir(__name__, 'hexfiles')
    firmware_files.sort()
    firmware_basename = os.path.splitext(
        resource_filename(__name__, os.path.join('hexfiles', firmware_files[0])))[0]
    fallback_hex_file = firmware_basename + '.hex'
    hexfiles = [firmware_basename]

    return hexfiles

class StartQT4(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.isRunning = True
        self.setWindowTitle('Linkbot Jig USB-Board Programmer')

        # Populate the firmware hex files combobox
        for f in sorted(findHexFiles()):
            self.ui.firmwareversion_comboBox.addItem(f)

        for p in sorted(_getSerialPorts()):
            self.ui.comport_comboBox.addItem(p)

        self.ui.flash_pushButton.clicked.connect(self.startProgramming)
        self.ui.progressBar.setValue(0)
        self.progressTimer = QtCore.QTimer(self)
        self.progressTimer.timeout.connect(self.updateProgress)

        self.thread = threading.Thread(target=self.cycleDongleThread)
        self.thread.start()

    def robotIdChanged(self, text):
        if len(text) == 4:
            self.enableTestButtons()
        else:
            self.disableTestButtons()

    def disableButtons(self):
        self.ui.flash_pushButton.setEnabled(False)

    def enableButtons(self):
        self.ui.flash_pushButton.setEnabled(True)

    def startProgramming(self): 
        serialPort = self.ui.comport_comboBox.currentText()
        firmwareFile = self.ui.firmwareversion_comboBox.currentText()+'.hex'
        print('Programming file: ', firmwareFile)
        try:
          self.programmer = stk.ATmega16U4Programmer(serialPort)
        except Exception as e:
          QtGui.QMessageBox.warning(self, "Programming Exception",
            'Unable to connect to programmer at com port '+ serialPort + 
            '. ' + str(e))
          traceback.print_exc()
          return
        
        try:
            self.programmer.programAllAsync( hexfiles=[firmwareFile])
            self.progressTimer.start(500)
        except Exception as e:
          QtGui.QMessageBox.warning(self, "Programming Exception",
            'Unable to connect to programmer at com port '+ serialPort + 
            '. ' + str(e))
          traceback.print_exc()
          return
    
    def updateProgress(self):
        # Multiply progress by 200 because we will not be doing verification
        self.ui.progressBar.setValue(self.programmer.getProgress()*100)
        if not self.programmer.isProgramming():
            if self.programmer.getLastException() is not None:
                QtGui.QMessageBox.warning(self, "Programming Exception",
                    str(self.programmer.getLastException()))
            else:
                self.ui.progressBar.setValue(100)

            self.progressTimer.stop()
            self.enableButtons()

    def cycleDongleThread(self):
        while self.isRunning:
            linkbot._linkbot.cycleDongle(2)
            time.sleep(1)

    def closeEvent(self, *args, **kwargs):
        self.isRunning = False

def main():
    app = QtGui.QApplication(sys.argv)
    myapp = StartQT4()
    myapp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
