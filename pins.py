#!/usr/bin/env python

"""
================================================

Requires RPi to be installed
================================================
"""
import RPi.GPIO as GPIO
import os
import time
from loggingdebug import log

class logicPins(log.log):

    def __init__(self):

        """
        Class constructor - Initialise the GPIO as input or outputs
        and edge detects.
        :param state: state of the purge at start of this constructor
        call (memory function, may not start from scratch)
        :type state: string, not optional
        """
        super().__init__()
        GPIO.setmode(GPIO.BCM)

        # Constants... python does not like real constants (im not creating constants.py) - pls dont change this
        self.deBounce = 100   # time in milliseconds
        # Pin numbers
        self.fillValve2 = 23
        self.ventValve = 24
        self.vacValve = 25
        self.stat1Mon = 8
        self.nCycleButton = 7
        self.stat2Mon = 1
        self.enCharge = 20
        self.enFan = 21

        self.nStartButton = 4
        self.enStepMotor = 27
        self.fillValve1 = 22
        self.nStopButton = 5
        self.nResetButton = 6
        self.enBattery = 19
        self.enPump = 26

        # Input pins
        GPIO.setup(self.stat1Mon,GPIO.IN)
        GPIO.setup(self.stat2Mon,GPIO.IN)

        GPIO.setup(self.nStartButton,GPIO.IN)
        GPIO.setup(self.nStopButton,GPIO.IN)
        GPIO.setup(self.nResetButton,GPIO.IN)
        GPIO.setup(self.nCycleButton,GPIO.IN)

        # Output pins
        GPIO.setup(self.fillValve2,GPIO.OUT)
        GPIO.setup(self.ventValve,GPIO.OUT)
        GPIO.setup(self.vacValve,GPIO.OUT)
        GPIO.setup(self.enCharge,GPIO.OUT)
        GPIO.setup(self.enFan,GPIO.OUT)

        GPIO.setup(self.enStepMotor,GPIO.OUT)
        GPIO.setup(self.fillValve1,GPIO.OUT)
        GPIO.setup(self.enBattery,GPIO.OUT)
        GPIO.setup(self.enPump,GPIO.OUT)

        # Variables
        self.cycleCount = 0

        # Flags
        self.startFlag = 0
        self.stopFlag = 0
        self.resetFlag = 0

        GPIO.add_event_detect(self.nCycleButton, GPIO.FALLING, self.__cycleCallback, self.deBounce)
        GPIO.add_event_detect(self.nStartButton, GPIO.FALLING, self.__startCallback, self.deBounce)
        GPIO.add_event_detect(self.nStopButton, GPIO.FALLING, self.__stopCallback, self.deBounce)
        GPIO.add_event_detect(self.nResetButton, GPIO.FALLING, self.__resetCallback, self.deBounce)

        # Object for logging to a file
        # This gets inherited from log.py with log class
        # self.logger()
        # self.DEBUG = log.log()

    def setCallbacks(self):
        """Method for detecting button presses"""
        # Consider a method for each
        GPIO.add_event_detect(self.nCycleButton, GPIO.FALLING, self.__cycleCallback, self.deBounce)
        GPIO.add_event_detect(self.nStartButton, GPIO.FALLING, self.__startCallback, self.deBounce)
        GPIO.add_event_detect(self.nStopButton, GPIO.FALLING, self.__stopCallback, self.deBounce)
        GPIO.add_event_detect(self.nResetButton, GPIO.FALLING, self.__resetCallback, self.deBounce)

    def removeCallBacks(self):
        """Method for removing button presses"""
        if self.startFlag:
            GPIO.remove_event_detect(self.nCycleButton)
            GPIO.remove_event_detect(self.nStartButton)
        if self.stopFlag:
            GPIO.remove_event_detect(self.nStopButton)
        if self.resetFlag:
            GPIO.remove_event_detect(self.nCycleButton)
            GPIO.remove_event_detect(self.nStartButton)
            GPIO.remove_event_detect(self.nStopButton)
            GPIO.remove_event_detect(self.nResetButton)

    def __cycleCallback(self, channel):
        """Internal method for incrementing a button press counter"""
        # Increment the number of cycles to be performed
        self.cycleCount += 1
        print(self.cycleCount)

        # DEBUG = log.log()
        self.logger('debug', 'cycle count incremented to {}'.format(self.cycleCount))
        
    def __startCallback(self, channel):
        """Internal method for starting purge"""
        print("start button pressed")
        if self.startFlag:
            self.startFlag = 0
        else:
            self.startFlag = 1
            self.removeCallBacks()       

    def __stopCallback(self, channel):
        print("stop button pressed")

        if self.stopFlag:
            self.stopFlag = 0
        else:
            self.stopFlag = 1
            self.removeCallBacks()
        
    def __resetCallback(self, channel):
        print("reset pressed")
        self.resetFlag = 1
        self.removeCallBacks()
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



def main():
    
    # Main program function

    # test = logicPins('testing')
    # test.cycleCallback(7)
    count = 0
    
    print("program has started")
    test = logicPins()
    count += 1

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(19,GPIO.OUT)
    GPIO.setup(test.enStepMotor,GPIO.OUT)

    GPIO.output(19, 1)
    GPIO.output(test.enStepMotor,1)

    try:
        while True:
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nExited measurements through keyboard interupt")
        GPIO.cleanup()


if __name__ == "__main__":
    main()
