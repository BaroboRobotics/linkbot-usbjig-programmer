#!/usr/bin/env python3

__version__ = "0.1.1"

import sys
from PyQt4 import QtCore, QtGui
try:
    from linkbot_usbjig_programmer.mainwindow import Ui_MainWindow
except:
    from mainwindow import Ui_MainWindow
import functools
import linkbot3 as linkbot
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
    hexfiles = []
    for f in firmware_files:
        firmware_basename = os.path.splitext(
            resource_filename(__name__, os.path.join('hexfiles', f)))[0]
        hexfiles += [firmware_basename]

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
        self.ui.checkBox_autoFlash.stateChanged.connect(self.processCheckBox)
        self.ui.progressBar.setValue(0)
        self.progressTimer = QtCore.QTimer(self)
        self.progressTimer.timeout.connect(self.updateProgress)
        self.progressTimerSilent = QtCore.QTimer(self)
        self.progressTimerSilent.timeout.connect(
                functools.partial(
                    self.updateProgress, silent=True
                    )
                )

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

    def processCheckBox(self, enabled):
        if enabled:
            self.disableButtons()
            # Start the listening thread
            self.listenThread = AutoProgramThread(self)
            self.listenThread.is_alive = True
            self.listenThread.start()
        else:
            self.listenThread.is_alive = False
            self.listenThread.wait()
            self.enableButtons()

    def startProgramming(self, silent=False): 
        serialPort = self.ui.comport_comboBox.currentText()
        firmwareFile = self.ui.firmwareversion_comboBox.currentText()+'.hex'
        print('Programming file: ', firmwareFile)
        try:
            if firmwareFile.find('32u2') > 0:
                self.programmer = stk.ATmega32U2Programmer(serialPort)
            else:
                self.programmer = stk.ATmegaXXU4Programmer(serialPort)
        except:
            if not silent:
                QtGui.QMessageBox.warning(self, "Programming Exception",
                  'Unable to connect to programmer at com port '+ serialPort + 
                  '. ' + str(e))
                traceback.print_exc()
                return
            else:
                raise
        
        try:
            if not silent:
                self.programmer.programAllAsync( hexfiles=[firmwareFile])
                self.progressTimer.start(500)
            else:
                self.programmer.programAll( hexfiles=[firmwareFile])
        except Exception as e:
            if not silent:
                QtGui.QMessageBox.warning(self, "Programming Exception",
                    'Unable to connect to programmer at com port '+ serialPort + 
                    '. ' + str(e))
                traceback.print_exc()
                return
            else:
                raise
    
    def updateProgress(self, silent=False):
        # Multiply progress by 200 because we will not be doing verification
        if silent:
            try:
                progress = self.programmer.getProgress()*100
                print(progress)
                if progress > 100:
                    progress = 100
                self.ui.progressBar.setValue(progress)
            except:
                pass
        else:
            if not self.programmer.isProgramming():
                if self.programmer.getLastException() is not None:
                    QtGui.QMessageBox.warning(self, "Programming Exception",
                        str(self.programmer.getLastException()))
                else:
                    self.ui.progressBar.setValue(100)

                self.progressTimer.stop()
                self.enableButtons()

    def cycleDongleThread(self):
        daemon = linkbot.Daemon()
        while self.isRunning:
            daemon.cycle(2)
            time.sleep(1)

    def closeEvent(self, *args, **kwargs):
        self.isRunning = False

class AutoProgramThread(QtCore.QThread):
    IDLE = 0
    DONE_PROGRAMMING = 1

    def __init__(self, parent):
        super().__init__(parent)
        self._main_window = parent
        self.is_alive= True
        self.state = self.IDLE
        self._main_window.progressTimerSilent.start(250)

    def run(self):
        while self.is_alive:
            if self.state == self.IDLE:
                self.idle()
            elif self.state == self.DONE_PROGRAMMING:
                self.done_programming()

    def idle(self):
        try:
            self._main_window.startProgramming(silent=True)
            self.state = self.DONE_PROGRAMMING
            print('Done programming.')
        except Exception as e:
            print('Caught exception: ', str(e), 'Trying again...')
            time.sleep(1)

    def done_programming(self):
        time.sleep(3)
        try:
            print('Trying sign-on...')
            self._main_window.programmer.sign_on()
            self._main_window.programmer.check_signature()
            time.sleep(1)
            print('Success.')
        except Exception as e:
            print('Check sig failed:', e)
            self.state = self.IDLE


def main():
    app = QtGui.QApplication(sys.argv)
    myapp = StartQT4()
    myapp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
