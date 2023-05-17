import RPi.GPIO as GPIO
import time
from loggingdebug import log

class logicPins():

    def __init__(self, state):

        """
        Class constructor - Initialise the GPIO as input or outputs
        and edge detects.
        :param state: state of the purge at start of this constructor
        call (memory function, may not start from scratch)
        :type state: string, not optional
        """

        self.state = state

        GPIO.setmode(GPIO.BCM)

        # Constants
        deBounce = 100   # time in milliseconds

        # Pin numbers
        fillValve2 = 23
        vacValve = 25
        stat1Mon = 8
        nCycleButton = 7
        stat2Mon = 1
        enCharge = 20
        enFan = 21

        nStartButton = 4
        enStepMotor = 27
        fillValve1 = 22
        nStopButton = 5
        nResetButton = 6
        enBattery = 19
        enPump = 26

        # Input pins
        GPIO.setup(stat1Mon,GPIO.IN)
        GPIO.setup(stat2Mon,GPIO.IN)

        GPIO.setup(nStartButton,GPIO.IN)
        GPIO.setup(nStopButton,GPIO.IN)
        GPIO.setup(nResetButton,GPIO.IN)
        GPIO.setup(nCycleButton,GPIO.IN)

        # Output pins
        GPIO.setup(fillValve2,GPIO.OUT)
        GPIO.setup(vacValve,GPIO.OUT)

        GPIO.setup(enCharge,GPIO.OUT)
        GPIO.setup(enFan,GPIO.OUT)
        GPIO.setup(enStepMotor,GPIO.OUT)
        GPIO.setup(fillValve1,GPIO.OUT)
        GPIO.setup(enBattery,GPIO.OUT)
        GPIO.setup(enPump,GPIO.OUT)

        # Variables
        self.cycleCount = 0

        GPIO.add_event_detect(nCycleButton, GPIO.FALLING, self.cycleCallback, deBounce)
        GPIO.add_event_detect(nStartButton, GPIO.FALLING, self.startCallback, deBounce)
        GPIO.add_event_detect(nStopButton, GPIO.FALLING, self.stopCallback, deBounce)
        GPIO.add_event_detect(nResetButton, GPIO.FALLING, self.resetCallback, deBounce)

        # Object for logging to a file
        # self.log = log()
       

    def cycleCallback(self, channel):

        self.cycleCount += 1
        message = 'cycle count incremented to {}'.format(self.cycleCount)

        DEBUG = log.log()
        DEBUG.logger('debug', message)
        
    def startCallback(self):
        startflag = 1

    def stopCallback(self):
        stopflag = 1

    def resetCallback(self):
        resetflag = 1

    def statusMonitor():
        stat1MonValue = GPIO.input(stat1Mon)
        stat2MonValue = GPIO.input(stat2Mon)
    
    def batteryState():
        GPIO.output(enBattery, 1 )


class purgeModes():
    def __init__(self):
        """
        Class constructor - Initialise functionality for creating rules of purge
        :param : 
        :type : 
        """
        
'''
def main():
    
    # Main program function
   
    test = logicPins('testing')
    test.cycleCallback(7)

if __name__ == "__main__":
    main()
'''