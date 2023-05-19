import pins
import time
import RPi.GPIO as GPIO
# from loggingdebug import log

class purgeModes():
    def __init__(self, state):
        """
        Class constructor - Initialise functionality for creating rules of purge
        :param : 
        :type : 
        """
        self.state = state
        self.logic = logicPins()
        self.logic.DEBUG.logger('debug', 'Purge constructor has run!')
        GPIO.output(self.logic.enBattery, 1)
        self.__idle()
        
    def __idle(self):
        """
        Internal method for setting an idle mode
        """
        print("idle")
        GPIO.output(self.logic.fillValve2, 0)
        GPIO.output(self.logic.ventValve, 0)
        GPIO.output(self.logic.vacValve, 0)
        GPIO.output(self.logic.enFan, 0)
        GPIO.output(self.logic.enStepMotor, 0)
        GPIO.output(self.logic.fillValve1, 0)
        GPIO.output(self.logic.enPump, 0)

    def __initiate(self):
        print("initiate")
        GPIO.output(self.logic.fillValve1, 1)
        GPIO.output(self.logic.fillValve2, 0)
        GPIO.output(self.logic.ventValve, 0)
        GPIO.output(self.logic.vacValve, 0)
        GPIO.output(self.logic.enPump, 0)
        GPIO.output(self.logic.enStepMotor, 0)
        GPIO.output(self.logic.enFan, 0)

    def __heliumFill(self):
        print("helium fill")
        GPIO.output(self.logic.fillValve1, 1)
        GPIO.output(self.logic.fillValve2, 1)
        GPIO.output(self.logic.ventValve, 0)
        GPIO.output(self.logic.vacValve, 0)
        GPIO.output(self.logic.enPump, 0)
        GPIO.output(self.logic.enStepMotor, 1)
        GPIO.output(self.logic.enFan, 0)

    def __heFillExit(self):
        print("exit helium fill")
        GPIO.output(self.logic.fillValve1, 0)
        GPIO.output(self.logic.fillValve2, 0)
        GPIO.output(self.logic.ventValve, 0)
        GPIO.output(self.logic.vacValve, 0)
        GPIO.output(self.logic.enPump, 0)
        GPIO.output(self.logic.enStepMotor, 0)
        GPIO.output(self.logic.enFan, 0)

    def __vent(self):
        print("vent")
        GPIO.output(self.logic.fillValve1, 0)
        GPIO.output(self.logic.fillValve2, 0)
        GPIO.output(self.logic.ventValve, 1)
        GPIO.output(self.logic.vacValve, 0)
        GPIO.output(self.logic.enPump, 0)
        GPIO.output(self.logic.enStepMotor, 0)
        GPIO.output(self.logic.enFan, 1)

    def __ventExit(self):
       print("exit vent")
       GPIO.output(self.logic.fillValve1, 0)
       GPIO.output(self.logic.fillValve2, 0)
       GPIO.output(self.logic.ventValve, 0)
       GPIO.output(self.logic.vacValve, 0)
       GPIO.output(self.logic.enPump, 0)
       GPIO.output(self.logic.enStepMotor, 0)
       GPIO.output(self.logic.enFan, 1)


    def __vac(self):
        print("Vacuum")
        GPIO.output(self.logic.fillValve1, 0)
        GPIO.output(self.logic.fillValve2, 0)
        GPIO.output(self.logic.ventValve, 0)
        GPIO.output(self.logic.vacValve, 1)
        GPIO.output(self.logic.enPump, 1)
        GPIO.output(self.logic.enStepMotor, 0)
        GPIO.output(self.logic.enFan, 1)


    def __ventFanStop(self):
        print("stoppping vent fan")
        GPIO.output(self.logic.enFan, 0)

    def ____vacExit(self):
        print("exiting vacuum")
        GPIO.output(self.logic.fillValve1, 0)
        GPIO.output(self.logic.fillValve2, 0)
        GPIO.output(self.logic.ventValve, 0)
        GPIO.output(self.logic.vacValve, 0)
        GPIO.output(self.logic.enPump, 0)
        GPIO.output(self.logic.enStepMotor, 0)
        GPIO.output(self.logic.enFan, 0)

class purge(self):
    
    def __init__():
        
    def runPurge(self):
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