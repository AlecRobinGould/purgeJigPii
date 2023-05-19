import RPi.GPIO as GPIO
from loggingdebug import log

class logicPins():

    def __init__(self):

        """
        Class constructor - Initialise the GPIO as input or outputs
        and edge detects.
        :param state: state of the purge at start of this constructor
        call (memory function, may not start from scratch)
        :type state: string, not optional
        """
        GPIO.setmode(GPIO.BCM)

        # Constants
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
        self.startFlag
        self.stopFlag
        self.resetFlag

        GPIO.add_event_detect(nCycleButton, GPIO.FALLING, self._cycleCallback, deBounce)
        GPIO.add_event_detect(nStartButton, GPIO.FALLING, self._startCallback, deBounce)
        GPIO.add_event_detect(nStopButton, GPIO.FALLING, self._stopCallback, deBounce)
        GPIO.add_event_detect(nResetButton, GPIO.FALLING, self._resetCallback, deBounce)

        # Object for logging to a file
        self.DEBUG = log.log()
       

    def _cycleCallback(self, channel):
        # Increment the number of cycles to be performed
        self.cycleCount += 1

        # DEBUG = log.log()
        self.DEBUG.logger('debug', 'cycle count incremented to {}'.format(self.cycleCount))
        
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

    def statusMonitor(self):
        stat1MonValue = GPIO.input(self.stat1Mon)
        stat2MonValue = GPIO.input(self.stat2Mon)

        if stat1MonValue:
            if stat2MonValue:
                self.DEBUG.logger('debug', 'Battery is charged')
                return 'Charged'
            else:
                self.DEBUG.logger('debug', 'Battery is charging')
                return 'Charging'
        else:
            if stat2MonValue:
                self.DEBUG.logger('warning', 'Over-voltage or over-temperature fault')
                return 'Fault'
            else:
                self.DEBUG.logger('error', 'Over-current or charge timeout fault')
                return 'Major fault'
    
    def batteryStateSet():
        GPIO.output(self.enBattery, 1 )

         
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