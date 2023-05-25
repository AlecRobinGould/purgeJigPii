import RPi.GPIO as GPIO
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
        # super().__init__()
        GPIO.setmode(GPIO.BCM)

        # Constants... python does not like real constants - pls dont change this
        deBounce = 100   # time in milliseconds

        # Pin numbers
        self.fillValve2 = 23
        self.ventValve = 24
        self.vacValve = 25
        self.stat1Mon = 8
        nCycleButton = 7
        self.stat2Mon = 1
        self.enCharge = 20
        self.enFan = 21

        nStartButton = 4
        self.enStepMotor = 27
        self.fillValve1 = 22
        nStopButton = 5
        nResetButton = 6
        self.enBattery = 19
        self.enPump = 26

        # Input pins
        GPIO.setup(self.stat1Mon,GPIO.IN)
        GPIO.setup(self.stat2Mon,GPIO.IN)

        GPIO.setup(nStartButton,GPIO.IN)
        GPIO.setup(nStopButton,GPIO.IN)
        GPIO.setup(nResetButton,GPIO.IN)
        GPIO.setup(nCycleButton,GPIO.IN)

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

        GPIO.add_event_detect(nCycleButton, GPIO.FALLING, self._cycleCallback, deBounce)
        GPIO.add_event_detect(nStartButton, GPIO.FALLING, self._startCallback, deBounce)
        GPIO.add_event_detect(nStopButton, GPIO.FALLING, self._stopCallback, deBounce)
        GPIO.add_event_detect(nResetButton, GPIO.FALLING, self._resetCallback, deBounce)

        # Object for logging to a file
        # This gets inherited from log.py with log class
        # self.logger()
        # self.DEBUG = log.log()

    def setCallbacks(self):
        GPIO.add_event_detect(nCycleButton, GPIO.FALLING, self._cycleCallback, deBounce)
        GPIO.add_event_detect(nStartButton, GPIO.FALLING, self._startCallback, deBounce)
        GPIO.add_event_detect(nStopButton, GPIO.FALLING, self._stopCallback, deBounce)
        GPIO.add_event_detect(nResetButton, GPIO.FALLING, self._resetCallback, deBounce)

    def removeCallBacks(self):

        if self.startFlag:
            GPIO.remove_event_detect(nCycleButton)
            GPIO.remove_event_detect(nStartButton)
        if self.stopFlag:
            GPIO.remove_event_detect(nStopButton)
        if self.resetFlag:
            GPIO.remove_event_detect(nCycleButton)
            GPIO.remove_event_detect(nStartButton)
            GPIO.remove_event_detect(nStopButton)
            GPIO.remove_event_detect(nResetButton)

    def _cycleCallback(self, channel):
        # Increment the number of cycles to be performed
        self.cycleCount += 1

        # DEBUG = log.log()
        self.logger('debug', 'cycle count incremented to {}'.format(self.cycleCount))
        
    def _startCallback(self):
        if self.startFlag:
            self.startFlag = 0
        else:
            self.startFlag = 1

    def _stopCallback(self):

        if self.stopFlag:
            self.stopFlag = 0
        else:
            self.stopFlag = 1

    def _resetCallback(self):
        self.resetFlag = 1

    def batteryStateSet(self, batteryEnable = 1, chargeEnable = 1):

        GPIO.output(self.enBattery, batteryEnable )
        GPIO.output(self.enCharge, chargeEnable)


'''        
def main():
    
    # Main program function

    # test = logicPins('testing')
    # test.cycleCallback(7)
    count = 0
    
    print("program has started")
    test = purgeModes()
    GPIO.cleanup()
    print("Program has ended")
    count += 1

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(19,GPIO.OUT)

    GPIO.output(19, 1)

    


if __name__ == "__main__":
    main()
'''