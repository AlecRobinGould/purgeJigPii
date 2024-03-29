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
    # from Display import displayLCD
    from Display import oldToNewInterface
except ImportError:
#     print("Failed to import pins from python system path")
#     try:
    import sys
    sys.path.append('.')
    # from Display import displayLCD
    from Display import oldToNewInterface
#     except ImportError:
#         raise ImportError(
#             "Failed to import library from parent folder")

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class emergencyStopException(Error):
    """
    Class for stop of program error exception
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

    def __init__(self, sharedBoolFlags, i2cLock, shared):

        """
        Class constructor - Initialise the GPIO as input or outputs
        and edge detects.
        :param state: state of the purge at start of this constructor
        call (memory function, may not start from scratch)
        :type state: string, not optional
        """
        # super().__init__()
        GPIO.setmode(GPIO.BCM)
        # self.disp = displayLCD.lcd()
        self.disp = oldToNewInterface.lcd()

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
        self.shared = shared

        # Flags
        self.startFlag = False
        self.stopFlag = False
        self.resetFlag = False
        self.errorFlag = False
        self.overPressureFlag = False
        # self.i2cBusLock = i2cLock
        self.doublePressFix = False
        
        self.sharedBoolFlags = sharedBoolFlags
        self.i2cBusLock = i2cLock
        # SharedBoolFlags[0] is startFlag
        # SharedBoolFlags[1] is stopFlag
        # SharedBoolFlags[2] is resetFlag
        # SharedBoolFlags[3] is errorFlag
        # sharedBoolFlags[4] is shutdownFlag
        # sharedBoolFlags[5] is overPressureFlag

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
    def __idleBeep(self):
        GPIO.output(self.enBuzzer, 0)

    def __idle(self):
        """
        Internal method for setting an idle mode
        """
        # print("idle")
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
        maxnum = 5
        minnum = 1
        with self.shared.get_lock():
            if self.shared[4] >= maxnum:
                self.shared[4] = minnum
            else:
                self.shared[4] += 1
            
        with self.shared.get_lock():
            self.pinDebug.logger('debug', 'cycle count incremented/decremented to: %d'%self.shared[4])

        # time.sleep(0.2)
        # maxnum = 99
        # if GPIO.input(self.nCycleButton):
        #     with self.shared.get_lock():
        #         if self.shared[4] >= maxnum:
        #             self.shared[4] = maxnum
        #         else:
        #             if self.doublePressFix:
        #                 self.doublePressFix = False
        #             else:
        #                 self.shared[4] += 1
            
        #     time.sleep(0.8)
        #     speedInc = 0
        #     while GPIO.input(self.nCycleButton) == 0:
        #         self.doublePressFix = True
        #         with self.shared.get_lock():
        #             if self.shared[4] >= maxnum:
        #                 self.shared[4] = maxnum
        #             else:
        #                 if GPIO.input(self.nCycleButton) == 0:
        #                     self.shared[4] += 1

        #         if speedInc <= 0.3:
        #             time.sleep(0.5 - speedInc)
        #         elif speedInc > 0.3 and speedInc < 0.5:
        #             time.sleep(0.15)
        #         else:
        #             time.sleep(0.1)
        #         speedInc += 0.1 

        #     with self.shared.get_lock():
        #         self.pinDebug.logger('debug', 'cycle count incremented to: %d'%self.shared[4])
                                       
        # else:
        #     with self.shared.get_lock():
        #         if self.shared[4] > 1:
        #             self.shared[4] -= 1
        #         else:
        #             self.shared[4] = 1
        #             # self.pinDebug.logger('debug', 'cycle count cannot be decremented further than: %d'%self.shared[4])
        #     time.sleep(0.7)
        #     speedDec = 0
        #     while GPIO.input(self.nCycleButton) == 0:
        #         with self.shared.get_lock():
        #             if self.shared[4] > 1:
        #                 self.shared[4] -= 1
        #             else:
        #                 self.shared[4] = 1

        #         if speedDec <= 0.3:
        #             time.sleep(0.5 - speedDec)
        #         elif speedDec > 0.3 and speedDec < 0.5:
        #             time.sleep(0.15)
        #         else:
        #             time.sleep(0.1)
        #         speedDec += 0.1
        #                 # self.pinDebug.logger('debug', 'cycle count cannot be decremented further than: %d'%self.shared[4])
        #     with self.shared.get_lock():
        #         self.pinDebug.logger('debug', 'cycle count decremented to: %d'%self.shared[4])
        
    def __startCallback(self, channel):
        """Internal method for starting purge"""
        with self.sharedBoolFlags.get_lock():
            self.errorFlag = self.sharedBoolFlags[3]
        if self.errorFlag:
            self.pinDebug.logger('error', 'Start button was pressed during active error')
        else:
            self.__startRemoveCallbacks()
            # with self.sharedBoolFlags.get_lock():
            #     if self.sharedBoolFlags[0]:
            #         self.sharedBoolFlags[0] = 0
            #     else:
            #         self.sharedBoolFlags[0] = 1
            #         self.sharedBoolFlags[1]= 0

            
            if self.startFlag:
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[0] = False
                self.startFlag = False
            else:
                with self.sharedBoolFlags.get_lock():
                   self.sharedBoolFlags[0] = True
                   self.sharedBoolFlags[1] = False
                self.startFlag = True
                self.stopFlag= False
                    # time.sleep(1)
        # with self.sharedBoolFlags.get_lock():            # self.removeCallBacks()
        #     self.pinDebug.logger('debug', 'Start button pressed, Startflag = %d'%self.sharedBoolFlags[0])
        self.pinDebug.logger('debug', 'Start button pressed, Startflag = %d'%self.startFlag)
        return 

    def __stopCallback(self, channel):
        with self.sharedBoolFlags.get_lock():
                self.startFlag = self.sharedBoolFlags[0]
                self.errorFlag = self.sharedBoolFlags[3]
                self.sharedBoolFlags[4] = False
        if self.startFlag:                 
            if self.errorFlag:
                if self.stopFlag:
                    self.stopFlag = False
                    self.sharedBoolFlags[1] = False
                else:
                    self.stopFlag = True
                    self.sharedBoolFlags[1] = True
                self.__idleBeep()
            else:
                self.__stopRemoveCallbacks()
                self.__idle()

            # with self.sharedBoolFlags.get_lock():
            #     self.pinDebug.logger('debug', 'Stop button pressed, Stopflag = %d'%self.sharedBoolFlags[1])
            #     if self.sharedBoolFlags[1]:
            #         self.sharedBoolFlags[1] = 0
            #     else:
            #         self.sharedBoolFlags[1] = 1
            #         self.sharedBoolFlags[0] = 0

            
                self.pinDebug.logger('debug', 'Stop button pressed, Stopflag = %d'%self.stopFlag)
                if self.stopFlag:
                    self.stopFlag = False
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[1] = False
                else:
                    self.stopFlag = True
                    self.startFlag = False
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[0] = False
                        self.sharedBoolFlags[1] = True
                    # time.sleep(0.3)
                    
                raise emergencyStopException()
        else:
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[4] = False
            if self.errorFlag:
                self.__idleBeep()
            else:
                # Ignore
                pass
            time.sleep(2)
            if GPIO.input(self.nStopButton) == 0:
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[4] = True

        
    def __resetCallback(self, channel):
        try:
            with self.sharedBoolFlags.get_lock():
                self.overPressureFlag = self.sharedBoolFlags[5]
            # print("reset pressed with shared obtain")
        except:
            self.overPressureFlag = self.sharedBoolFlags[5]
            # print("reset pressed without shared obtain")
        if self.overPressureFlag:
            # print("reset pressed, ovp flag true")
            pass
        else:
            # print("reset pressed, ovp flag false")
            self.__resetRemoveCallbacks()
            self.__idle()
            # with self.sharedBoolFlags.get_lock():
            #     self.sharedBoolFlags[2] = True
            #     self.sharedBoolFlags[1] = True
            self.resetFlag = True
            # self.stopFlag = True
            with self.sharedBoolFlags.get_lock():
                    # self.sharedBoolFlags[1] = True
                    self.sharedBoolFlags[2] = True
            # time.sleep(0.3)
            # self.display.backlight(0)

            # with self.sharedBoolFlags.get_lock():
            #     self.pinDebug.logger('debug', 'Reset button pressed, Resetflag = %d'%self.sharedBoolFlags[2])
            self.pinDebug.logger('debug', 'Reset button pressed, Resetflag = %d'%self.resetFlag)
    
            # time.sleep(1)
            # time.sleep(0.5)
            # if GPIO.input(self.nResetButton):
            #     self.__idle()
            #     # os.execl(sys.executable, sys.executable, *sys.argv)
            # else:
                
            #     # os.system("sudo reboot now -h")

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