import pins
import time, sys
import RPi.GPIO as GPIO
from measurements import monitor
from loggingdebug import log

# inherit ability to control and monitor pins, and logging
class purgeModes(monitor.measure, pins.logicPins, log.log):
    def __init__(self,noOfCycles = 4, state = 'idle'):
        """
        Class constructor - Initialise functionality for creating rules of purge
        :param noOfCycles: 
        :type int:
        :param state: 
        :type string: 
        """
        super().__init__()
        # This gets inherited from log.py with log class
        self.logger('debug', 'Purge constructor has run!')
        GPIO.output(self.enBattery, 1)
        self.__idle()

        # Variables
        self.noOfCycles = noOfCycles
        self.state = state

        # Flags
        self.prefilledFlag = True
        self.lastCycleCount = False
        self.errorFlag = False

        # Constants
        self.maxSupplyPressure = 16
        self.minSupplyPressure = 4
        self.proofPressure = 24

        self.ventPressure = 0.2
        self.vacuumPressure = 0.05
        self.fillPressure = 4
        self.lastFillPressure = 16

        self.vacuumChannel = 1
        self.batteryVoltChanel = 2
        self.supplyPressureChannel = 3
        self.ventPressureChannel = 4

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
        """
        Internal method for opening supply pressure valve
        """
        print("initiate")
        GPIO.output(self.fillValve1, 1)
        GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 0)

    def __heFill(self):
        """
        Internal method for setting an fill mode
        """
        print("helium fill")
        GPIO.output(self.fillValve1, 1)
        GPIO.output(self.fillValve2, 1)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 1)
        GPIO.output(self.enFan, 0)

    def __heFillExit(self):
        """
        Internal method for exiting hefill
        """
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
        GPIO.output(self.enPump, 1)
        time.sleep(2)   # This is for delaying the time of the vacuum valve opening
                        # Allowing the vaccum pump time to create a vacuum, reducing chances of contamination
        GPIO.output(self.vacValve, 1)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 1)


    def __ventFanStop(self):
        print("stoppping vent fan")
        GPIO.output(self.enFan, 0)

    def __vacExit(self):
        print("exiting vacuum")
        GPIO.output(self.fillValve1, 0)
        GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        time.sleep(1)   # This closes the valve before the vacuum pump turns off
                        # reducing the chance of contamination
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 0)
    
    def stateMachine(self):
        self.__initiate()
        supplyPressure = self.pressureConversion(self.readVoltage(self.supplyPressureChannel), "0-34bar")
        if (supplyPressure >= self.proofPressure)\
        or (supplyPressure < self.minSupplyPressure):
            self.errorFlag = True
            self.logger('error', 'The supply pressure is out of bounds. Exiting program')
            GPIO.cleanup()
            sys.exit()

        if self.prefilledFlag:
            while (self.cycleCount < self.noOfCycles) and (self.errorFlag is False):
                self.__idle()
                time.sleep(1)

                while self.pressureConversion(self.readVoltage(self.ventPressureChannel), "0-10bar") >= self.ventPressure:
                    self.__vent()
                self.__ventExit()

                while self.vacuumConversion(self.readVoltage(self.vacuumChannel)) >= self.vacuumPressure:
                    self.__vac()
                self.__vacExit()

                while self.pressureConversion(self.readVoltage(self.ventPressureChannel), "0-10bar") >= self.fillPressure:
                    self.__heFill()
                self.__heFillExit()


        else:
            while (self.cycleCount < self.noOfCycles) and (self.errorFlag is False):
                self.__idle()
                time.sleep(1)

                while self.pressureConversion(self.readVoltage(self.ventPressureChannel), "0-10bar") >= self.fillPressure:
                    self.__heFill()
                self.__heFillExit()

                while self.pressureConversion(self.readVoltage(self.ventPressureChannel), "0-10bar") >= self.ventPressure:
                    self.__vent()
                self.__ventExit()

                while self.vacuumConversion(self.readVoltage(self.vacuumChannel)) >= self.vacuumPressure:
                    self.__vac()
                self.__vacExit()



class purge(purgeModes):
    def __init__(self, noOfCycles):
        # Get state if it was saved and pass it to parent
        super().__init__(noOfCycles)
        
    def runPurge(self):
        while not self.errorFlag:
            self.stateMachine()
        # Check battery
        
        # Check sensors

        

def main():
    '''
    Main program function
    '''
    

if __name__ == "__main__":
    main()