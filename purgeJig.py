import pins
import time
import RPi.GPIO as GPIO
from loggingdebug import log

# inherit ability to control and monitor pins, and logging
class purgeModes(pins.logicPins, log.log):
    def __init__(self, state):
        """
        Class constructor - Initialise functionality for creating rules of purge
        :param : 
        :type : 
        """
        super().__init__()
        self.state = state
         # This gets inherited from log.py with log class
        self.logger('debug', 'Purge constructor has run!')
        GPIO.output(self.enBattery, 1)
        self.__idle()
        self.prefilledFlag = 0
        self.lastCycleCount = 0      

    def __idle(self):
        """
        Internal method for setting an idle mode
        """
        print("idle")
        GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enFan, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.fillValve1, 0)
        GPIO.output(self.enPump, 0)

    def __initiate(self):
        print("initiate")
        GPIO.output(self.fillValve1, 1)
        GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 0)

    def __heliumFill(self):
        print("helium fill")
        GPIO.output(self.fillValve1, 1)
        GPIO.output(self.fillValve2, 1)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 1)
        GPIO.output(self.enFan, 0)

    def __heFillExit(self):
        print("exit helium fill")
        GPIO.output(self.fillValve1, 0)
        GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 0)

    def __vent(self):
        print("vent")
        GPIO.output(self.fillValve1, 0)
        GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 1)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 1)

    def __ventExit(self):
       print("exit vent")
       GPIO.output(self.fillValve1, 0)
       GPIO.output(self.fillValve2, 0)
       GPIO.output(self.ventValve, 0)
       GPIO.output(self.vacValve, 0)
       GPIO.output(self.enPump, 0)
       GPIO.output(self.enStepMotor, 0)
       GPIO.output(self.enFan, 1)


    def __vac(self):
        print("Vacuum")
        GPIO.output(self.fillValve1, 0)
        GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 1)
        GPIO.output(self.enPump, 1)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 1)


    def __ventFanStop(self):
        print("stoppping vent fan")
        GPIO.output(self.enFan, 0)

    def ____vacExit(self):
        print("exiting vacuum")
        GPIO.output(self.fillValve1, 0)
        GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 0)

class purge():

    def __init__():
        pass
    def runPurge(self):
        pass
        # Check battery
        
        # Check sensors

        

def main():
    '''
    Main program function
    '''
    test = pins.logicPins('testing')

    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()