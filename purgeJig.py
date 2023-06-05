#!/usr/bin/env python

"""
================================================

Requires modules from "List of dependencies.txt"
================================================
"""
import pins
import time, sys
import RPi.GPIO as GPIO
from measurements import monitor
from loggingdebug import log
from dataclasses import dataclass

@dataclass(frozen=True)
class constantsNamespace():
        """
        Class for constants - the only purpose of this dataclass is to create values that cannot be 
        reassigned (constants). Python does not have the const keyword, to avoid errors of
        accidentally writing over constants - the method is rather prevent it from occuring.
        A name of a value in caps is said to be a constant
        """

        # Constants
        MAXSUPPLYPRESSURE = 16
        MINSUPPLYPRESSURE = 4
        PROOFPRESSURE = 24

        VENTPRESSURE = 0.2
        VACUUMPRESSURE = 0.05
        FILLPRESSURE = 4
        LASTFILLPRESSURE = 16

        VACUUMCHANNEL = 1
        BATTERYVOLTCHANNEL = 2
        SUPPLYPRESSURECHANNEL = 3
        VENTPRESSURECHANNEL = 4

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
        # constants dataclass where all values that shan't be changed reside 
        self.constant = constantsNamespace()
        # This gets inherited from log.py with log class
        self.logger('debug', 'Purge constructor has run!')
        GPIO.output(self.enBattery, 1)
        self.__idle()

        # Variables
        self.noOfCycles = noOfCycles
        self.state = state

        # Flags
        self.preFilledFlag = True
        self.lastCycleFlag = False
        self.errorFlag = False

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

# Lets see if this is neccessary
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

    def __preFillCheck(self):
        if self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar") >= self.constant.MINSUPPLYPRESSURE:
            self.preFilledFlag = True
        else:
            self.preFilledFlag = False
    
    def __stateMachine(self):
        if not self.preFilledFlag:
            while self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar") >= self.constant.FILLPRESSURE:
                self.__heFill()
            self.__heFillExit()
        else:
            while (self.cycleCount < self.noOfCycles) and (self.errorFlag is False):
                self.__idle()
                time.sleep(1)

                while self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar") >= self.constant.VENTPRESSURE:
                    self.__vent()
                self.__ventExit()

                while self.vacuumConversion(self.readVoltage(self.constant.VACUUMCHANNEL)) >= self.constant.VACUUMPRESSURE:
                    self.__vac()
                self.__vacExit()
                
                if self.lastCycleFlag:
                    while self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")\
                    <= self.constant.LASTFILLPRESSURE and\
                    (self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")) >= self.constant.FILLPRESSURE:
                        self.__heFill()
                    
                else:
                    while self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")\
                    <= self.constant.FILLPRESSURE:
                        self.__heFill()
                self.__heFillExit()
                self.cycleCount += 1

                if (self.cycleCount - 1) == (self.noOfCycles):
                    self.lastCycleFlag = True              
    
    def stateChecks(self):
        self.__initiate()
        supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
        if (supplyPressure >= self.constant.PROOFPRESSURE) or\
        (supplyPressure < self.constant.MINSUPPLYPRESSURE):
            self.errorFlag = True
            self.logger('error', 'The supply pressure is out of bounds. Exiting program')
            GPIO.cleanup()
            return False            
        elif (supplyPressure > self.constant.MAXSUPPLYPRESSURE) and\
        (supplyPressure < self.constant.PROOFPRESSURE):
            self.errorFlag = False
            self.logger('warning', "The supply pressure is safely too high. Program will continue")
            self.__preFillCheck()
            return True
        else:
            self.errorFlag = False
            self.logger('debug', 'The supply pressure was set correctly')
            self.__preFillCheck()
            return True

    def machineRun(self):
        """
        Method used to check if the sensors report viable values
        for the device to operate safely and as expected
        """
        if self.stateChecks():
            self.__stateMachine()
        else:
            sys.exit()

class purge(object):
    def __init__(self, noOfCycles, state):
        # Get number of cycles and pass it to parent. Other option is to press cycle
        # button to increment before the purge process begins
        self.runrun = purgeModes(noOfCycles, state)
        
    def runPurge(self):
        if not self.runrun.stateChecks():
            self.runrun.machineRun()
        # Check battery
        
        # Check sensors

        

def main():
    '''
    Main program function
    '''
    

if __name__ == "__main__":
    main()