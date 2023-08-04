#!/usr/bin/env python

"""
================================================

Requires RPi to be installed
================================================
"""
import RPi.GPIO as GPIO
import os, sys
import time
from loggingdebug import log
try: 
    from Display import displayLCD
except ImportError:
#     print("Failed to import pins from python system path")
#     try:
    import sys
    sys.path.append('.')
    from Display import displayLCD
#     except ImportError:
#         raise ImportError(
#             "Failed to import library from parent folder")

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class emergencyStopException(Exception):
    """
    Class for error exception
    """
    def __init__(self, message='Exit raised though a stop flag'):
        # Call the base class constructor with the parameters it needs
        super(emergencyStopException, self).__init__(message)

class resetException(Error):
    """
    Class for over reset exception
    """
    def __init__(self, message='Exception rasied through reset'):
        # Call the base class constructor with the parameters it needs
        super(resetException, self).__init__(message)

class logicPins(object):

    def __init__(self):

        """
        Class constructor - Initialise the GPIO as input or outputs
        and edge detects.
        :param state: state of the purge at start of this constructor
        call (memory function, may not start from scratch)
        :type state: string, not optional
        """
        # super().__init__()
        GPIO.setmode(GPIO.BCM)
        self.disp = displayLCD.lcd()

        # Constants... python does not like real constants (im not creating constants.py) - pls dont change this
        self.deBounce = 100   # time in milliseconds
        # Pin numbers
        self.fillValve = 23
        self.ventValve1 = 24
        self.vacValve = 25
        self.stat1Mon = 8
        self.nCycleButton = 7
        self.stat2Mon = 1
        self.enCharge = 20
        self.enBuzzer = 21

        self.nStartButton = 4
        self.enStepMotor = 27
        self.ventValve2 = 22
        self.nStopButton = 5
        self.nResetButton = 6
        self.enBattery = 19
        self.enPump = 26

        # Sets "GPIO in use" warning off
        GPIO.setwarnings(False)

        # Input pins
        GPIO.setup(self.stat1Mon,GPIO.IN)
        GPIO.setup(self.stat2Mon,GPIO.IN)

        GPIO.setup(self.nStartButton,GPIO.IN)
        GPIO.setup(self.nStopButton,GPIO.IN)
        GPIO.setup(self.nResetButton,GPIO.IN)
        GPIO.setup(self.nCycleButton,GPIO.IN)

        # time.sleep(1.5)
        # Output pins
        GPIO.setup(self.fillValve,GPIO.OUT)
        GPIO.setup(self.ventValve1,GPIO.OUT)
        GPIO.setup(self.vacValve,GPIO.OUT)
        GPIO.setup(self.enCharge,GPIO.OUT)
        GPIO.setup(self.enBuzzer,GPIO.OUT)

        GPIO.setup(self.enStepMotor,GPIO.OUT)
        GPIO.setup(self.ventValve2,GPIO.OUT)
        GPIO.setup(self.enBattery,GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.enPump,GPIO.OUT)

        # Variables
        self.cycleCount = 0

        # Flags
        self.startFlag = 0
        self.stopFlag = 0
        self.resetFlag = False
        self.errorFlag = False

        # self.setCallbacks()
        # NOTE: These are created in a seperate threads and the callbacks should be treated as such
        GPIO.add_event_detect(self.nCycleButton, GPIO.FALLING, self.__cycleCallback, self.deBounce)
        GPIO.add_event_detect(self.nStartButton, GPIO.FALLING, self.__startCallback, self.deBounce)
        GPIO.add_event_detect(self.nStopButton, GPIO.FALLING, self.__stopCallback, self.deBounce)
        GPIO.add_event_detect(self.nResetButton, GPIO.FALLING, self.__resetCallback, self.deBounce)

        """Create instance of the lcd class. WIll later be inherited where it needs to be"""
        # self.display = displayLCD.lcd()
        self.pinDebug = log.log()

        self.pinDebug.logger("debug", "logicPins constructor has run")

    def setCallbacks(self):
        """Method for detecting button presses"""
        # Consider a method for each
        GPIO.add_event_detect(self.nCycleButton, GPIO.FALLING, self.__cycleCallback, self.deBounce)
        GPIO.add_event_detect(self.nStartButton, GPIO.FALLING, self.__startCallback, self.deBounce)
        GPIO.add_event_detect(self.nStopButton, GPIO.FALLING, self.__stopCallback, self.deBounce)
        GPIO.add_event_detect(self.nResetButton, GPIO.FALLING, self.__resetCallback, self.deBounce)            

    def __startRemoveCallbacks(self):
        GPIO.remove_event_detect(self.nCycleButton)
        GPIO.remove_event_detect(self.nStartButton)
        self.pinDebug.logger('debug', 'cycle and start button detect off')
    def startAddCallbacks(self):
        GPIO.add_event_detect(self.nCycleButton, GPIO.FALLING, self.__cycleCallback, self.deBounce)
        GPIO.add_event_detect(self.nStartButton, GPIO.FALLING, self.__startCallback, self.deBounce)
        self.pinDebug.logger('debug', 'cycle and start button detect on again')
    def __stopRemoveCallbacks(self):
        GPIO.remove_event_detect(self.nCycleButton)
        GPIO.remove_event_detect(self.nStartButton)
        GPIO.remove_event_detect(self.nStopButton)
        self.pinDebug.logger('debug', 'stop button detect off')
    def __stopAddCallbacks(self):
        GPIO.add_event_detect(self.nStopButton, GPIO.FALLING, self.__stopCallback, self.deBounce)
        self.pinDebug.logger('debug', 'stop button detect on again')
    def __resetRemoveCallbacks(self):
        GPIO.remove_event_detect(self.nCycleButton)
        GPIO.remove_event_detect(self.nStartButton)
        GPIO.remove_event_detect(self.nStopButton)
        GPIO.remove_event_detect(self.nResetButton)
        self.pinDebug.logger('debug', 'cycle, start, stop, and reset button detect off')
    def __resetAddCallbacks(self):
        GPIO.remove_event_detect(self.nCycleButton)
        GPIO.remove_event_detect(self.nStartButton)
        GPIO.remove_event_detect(self.nStopButton)
        GPIO.remove_event_detect(self.nResetButton)
        self.pinDebug.logger('debug', 'All button detects added again')

    def __idle(self):
        """
        Internal method for setting an idle mode
        """
        print("idle")
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.ventValve1, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enBuzzer, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.enPump, 0)

    def setIdle(self):
        # This is a hack...
        self.__idle()

    def __cycleCallback(self, channel):
        """Internal method for incrementing a button press counter"""
        # Increment the number of cycles to be performed
        time.sleep(0.2)
        if GPIO.input(self.nCycleButton):
            self.cycleCount += 1
            self.pinDebug.logger('debug', 'cycle count incremented to: %d'%self.cycleCount)
        else:
            if self.cycleCount >= 1:
                self.cycleCount -= 1
                self.pinDebug.logger('debug', 'cycle count decremented to: %d'%self.cycleCount)
            else:
                self.pinDebug.logger('debug', 'cycle count cannot be decremented further than: %d'%self.cycleCount)
            
        
    def __startCallback(self, channel):
        """Internal method for starting purge"""
        
        if self.errorFlag:
            self.pinDebug.logger('error', 'Start button was pressed during active error')
        else:
            self.__startRemoveCallbacks()
            if self.startFlag:
                self.startFlag = 0
            else:
                self.startFlag = 1
                self.stopFlag = 0
                # time.sleep(1)
                # self.removeCallBacks()
        self.pinDebug.logger('debug', 'Start button pressed, Startflag = %d'%self.startFlag)
        return 

    def __stopCallback(self, channel):
        self.__stopRemoveCallbacks()
        self.__idle()
        self.pinDebug.logger('debug', 'Stop button pressed, Stopflag = %d'%self.stopFlag)
        if self.stopFlag:
            self.stopFlag = 0
        else:
            self.stopFlag = 1
            self.startFlag = 0
            time.sleep(0.3)
            self.disp.lcd_clear()
            self.disp.lcd_display_string("E-stop pressed", 1)
            self.disp.lcd_display_string("Press reset to", 2)
            self.disp.lcd_display_string("Continue...", 3)
        raise emergencyStopException()
        # return True
        
    def __resetCallback(self, channel):
        self.__resetRemoveCallbacks()
        self.__idle()
        self.resetFlag = True
        self.stopFlag = 1
        time.sleep(0.3)
        self.disp.lcd_display_string("Reset pressed ", 1)
        self.disp.lcd_display_string("                    ", 2)
        self.disp.lcd_display_string("                    ", 3)
        self.disp.lcd_display_string("                    ", 4)
        # self.display.backlight(0)
        self.pinDebug.logger('debug', 'Reset button pressed, Resetflag = %d'%self.resetFlag)
        # time.sleep(1)
        # time.sleep(0.5)
        if GPIO.input(self.nResetButton):
            # self.display.lcd_display_string("Resetting", 1)
            # self.display.lcd_display_string("programme", 2)
            # time.sleep(0.5)
            # raise resetException()
            # GPIO.cleanup()
            self.__idle()
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            
            time.sleep(2)
            self.disp.lcd_clear()
            self.disp.lcd_display_string("Restarting device,", 1)
            self.disp.lcd_display_string("Please be patient.", 2)
            os.system("sudo reboot now -h")

    def batteryStateSet(self, batteryEnable = 1, chargeEnable = 1):
        """
        Method for enabling or disabling the ability to charge the battery and consume battery power
        It is crutial that the battery enable pin is high. Loadshedding will likely corrupt data.
        param : batteryEnable: signal used to enable or disable battery power. High mean enable battery
        type : batteryEnable: int
        param: chargeEnable: signal used to enable or disable charging. Low means battery can charge
        type : chargeEnable: int
        """
        GPIO.output(self.enBattery, batteryEnable )
        GPIO.output(self.enCharge, chargeEnable)

"""
def main():
    
    # Main program function

    # test = logicPins('testing')
    # test.cycleCallback(7)
    count = 0
    
    print("program has started")
    test = logicPins()
    count += 1

    # self.fillValve = 23
    # self.ventValve1 = 24
    # self.vacValve = 25
    # self.enBuzzer = 21
    # self.enStepMotor = 27
    # self.ventValve2 = 22
    # self.enPump = 26

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(19,GPIO.OUT)
    GPIO.output(19, 1)


    GPIO.setup(test.enBuzzer,GPIO.OUT)
    GPIO.output(test.enBuzzer,0)

    try:
        while True:
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nExited measurements through keyboard interupt")
        GPIO.cleanup()


if __name__ == "__main__":
    main()
"""