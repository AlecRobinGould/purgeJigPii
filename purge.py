#!/usr/bin/env python

"""
================================================

Requires modules from "List of dependencies.txt"
================================================
"""
import RPi.GPIO as GPIO
import pins
from loggingdebug import log
from measurements import monitor
from dataclasses import dataclass
import time, sys

@dataclass(frozen=True)
class constantsNamespace():
        """
        Class for constants - the only purpose of this dataclass is to create values that cannot be 
        reassigned (constants). Python does not have the const keyword, to avoid errors of
        accidentally writing over constants - the method is rather prevent it from occuring.
        A name of a value in caps is said to be a constant.
        """
        # Constants
        MAXSUPPLYPRESSURE = 16
        MINSUPPLYPRESSURE = 4
        PROOFPRESSURE = 24

        MAXLOWGAUGE = 10
        MAXHIGHGAUGE = 34

        PREFILLPRESSURE = 16
        VENTPRESSURE = 0.2
        VACUUMPRESSURE = 0.05
        FILLPRESSURE = 4
        LASTFILLPRESSURE = 16

        VACUUMCHANNEL = 1
        BATTERYVOLTCHANNEL = 2
        SUPPLYPRESSURECHANNEL = 3
        VENTPRESSURECHANNEL = 4

class faultErrorException(pins.Error):
    """
    Class for error exception
    """
    def __init__(self, message='Error rasied though a fault flag'):
        # Call the base class constructor with the parameters it needs
        super(faultErrorException, self).__init__(message)

class overPressureException(pins.Error):
    """
    Class for over pressure error exception
    """
    def __init__(self, message='Error rasied though a over pressure whilst active fill'):
        # Call the base class constructor with the parameters it needs
        super(overPressureException, self).__init__(message)

# inherit ability to control and monitor pins, and logging
class purgeModes(monitor.measure, pins.logicPins, log.log):
    def __init__(self,cycleCount = 4, state = 'idle'):
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
        GPIO.setmode(GPIO.BCM)
        GPIO.output(self.enBattery, 1)
        self.__idle()

        # Variables
        self.cycleCount = cycleCount
        self.noOfCycles = 0
        self.state = state

        # Flags
        self.preFilledFlag = True
        self.lastCycleFlag = False
        

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
        # Allow time for pressure to equalise
        time.sleep(1)
    
    def __preFillCheckValves(self):
        """
        Internal method for opening supply pressure valve
        """
        print("initiate")
        GPIO.output(self.fillValve1, 0)
        time.sleep(0.5)
        GPIO.output(self.fillValve2, 1)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 0)
        # Allow time for pressure to equalise
        time.sleep(1)

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
        time.sleep(5)   # This is for delaying the time of the vacuum valve opening
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

    def __preFillCheck(self, inputPressure, comparison):

        self.__preFillCheckValves()
        supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
        ventPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
        self.display.lcd_clear()
        if comparison == 'higher':

            if (ventPressure >= self.constant.MAXLOWGAUGE) and supplyPressure >= self.constant.PREFILLPRESSURE:
                self.preFilledFlag = True
                self.logger('debug','The component was prefilled')
            else:
                self.preFilledFlag = False
                self.logger('debug','The component was not prefilled (higher)')
                preFillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                safetyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                if (safetyPressure > self.constant.MINSUPPLYPRESSURE) and (safetyPressure < self.constant.PROOFPRESSURE):
                    self.__heFill()
                    self.display.lcd_display_string("Prefilling State", 1)
                while (preFillPressure <= self.constant.MAXLOWGAUGE or (safetyPressure - 0.1) <= self.constant.PREFILLPRESSURE) and \
                (self.startFlag and self.stopFlag == 0 and self.resetFlag == 0):
                    safetyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    preFillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                    self.display.lcd_display_string("Press1: {} bar ".format(round(safetyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL)
                    self.display.lcd_display_string("Press2: {} bar ".format(round(preFillPressure,2)), self.constant.VENTPRESSURECHANNEL)
                    if safetyPressure >= self.constant.PROOFPRESSURE:
                        self.__idle()
                        raise overPressureException()

                self.__heFillExit()
        else:
            if (ventPressure >= self.constant.MAXLOWGAUGE) and supplyPressure >= inputPressure:
                self.preFilledFlag = True
                self.logger('debug','The component was prefilled')
            else:
                self.preFilledFlag = False
                self.logger('debug','The component was not prefilled (lower)')
                preFillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                safetyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                if (safetyPressure > self.constant.MINSUPPLYPRESSURE) and (safetyPressure < self.constant.PROOFPRESSURE):
                    self.__heFill()
                    self.display.lcd_display_string("Prefilling State", 1)
                while (preFillPressure <= self.constant.MAXLOWGAUGE or (safetyPressure - 0.1) <= inputPressure) and \
                (self.startFlag and self.stopFlag == 0 and self.resetFlag == 0):
                    safetyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    preFillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                    self.display.lcd_display_string("Press1: {} bar ".format(round(safetyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL)
                    self.display.lcd_display_string("Press2: {} bar ".format(round(preFillPressure,2)), self.constant.VENTPRESSURECHANNEL)
                    if safetyPressure >= self.constant.PROOFPRESSURE:
                        self.__idle()
                        raise overPressureException()

                self.__heFillExit()
        self.__idle()

    def __safetyCheck(self):
        pass
    
    def __stateMachine(self):
        """Add in provision to check for stopFlag and resetFlag"""
        self.display.lcd_clear()
        # Operate only untill the desired number of cycles are complete
        while (self.noOfCycles < self.cycleCount) and (self.errorFlag is False):
            self.__idle()
            # time.sleep(1)
            # Check if it is the last cycle to be run
            if (self.noOfCycles) == (self.cycleCount - 1):
                self.logger('debug','Last cycle flag set True')
                self.lastCycleFlag = True              

            self.display.lcd_display_string("Cycle %d of %d"%((self.noOfCycles+1), self.cycleCount), 1)

            # Venting process
            ventPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            if ventPressure  >= self.constant.VENTPRESSURE:
                self.__vent()
                self.display.lcd_display_string("Venting Process...", 2)
            while ventPressure  >= self.constant.VENTPRESSURE:
                ventPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                self.display.lcd_display_string("Press2: {} bar ".format(round(ventPressure,2)), 3)
                if self.stopFlag:
                    raise pins.emergencyStopException()
                
            self.__ventExit()
            self.display.lcd_display_string("                    ", 2)
            self.display.lcd_display_string("                    ", 3)

            # Vacuum process
            vacuumPressure = self.vacuumConversion(self.readVoltage(self.constant.VACUUMCHANNEL))
            if vacuumPressure >= self.constant.VACUUMPRESSURE:
                self.display.lcd_display_string("Vacuum Process...", 2)
                self.__vac()
                
            while vacuumPressure >= self.constant.VACUUMPRESSURE:
                vacuumPressure = self.vacuumConversion(self.readVoltage(self.constant.VACUUMCHANNEL))
                self.display.lcd_display_string("Vac: {:.2e}".format(vacuumPressure),3)
                
            self.__vacExit()
            self.display.lcd_display_string("                    ", 2)
            self.display.lcd_display_string("                    ", 3)
    
            # Check if supply pressure is safe to apply
            self.__initiate()
            supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            fillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")

            if (supplyPressure >= self.constant.PROOFPRESSURE) or\
            (supplyPressure < self.constant.MINSUPPLYPRESSURE):
                self.errorFlag = True
                self.logger('error', 'The supply pressure is out of bounds. Allowing user to fix it')
                time.sleep(1)
                self.display.lcd_clear()
                self.display.lcd_display_string("Error!!!",1)
                self.display.lcd_display_string("Supply pressure out",2)
                self.display.lcd_display_string("of bounds",3)
                time.sleep(5)
                self.display.lcd_clear()
                self.display.lcd_display_string("Supply P too high...", 1)
                while (supplyPressure >= self.constant.PROOFPRESSURE) or\
                (supplyPressure < self.constant.MINSUPPLYPRESSURE):
                    supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    self.display.lcd_display_string("Press1: {} bar ".format(round(supplyPressure,2)), 2)
                self.errorFlag = False

                self.display.lcd_clear()
            else:
                self.logger('debug',"The supply pressure is within bounds")

            # Check whether it is the last cycle, if it is, fill to 16 bar rather
            if self.lastCycleFlag:
                # Helium fill process
                if (supplyPressure >= self.constant.LASTFILLPRESSURE and supplyPressure < self.constant.PROOFPRESSURE):
                    self.logger('debug',"The supply pressure is greater than 16bar for last fill")
                    self.__heFill()
                    self.display.lcd_display_string("Last Fill Process...", 2)

                    while (supplyPressure <= self.constant.LASTFILLPRESSURE) or\
                    (fillPressure <= self.constant.MAXLOWGAUGE):
                        supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        fillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                        self.display.lcd_display_string("Press1: {} bar ".format(round(supplyPressure,2)), 3)
                        self.display.lcd_display_string("Press2: {} bar ".format(round(fillPressure,2)), 4)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.__idle()
                            raise overPressureException()
                else:
                    self.logger('debug',"The supply pressure is less than 16bar for last fill")
                    self.__initiate()
                    time.sleep(1)
                    highestPossiblePressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    self.__heFill()
                    self.display.lcd_display_string("Last Fill Process...", 2)

                    while (supplyPressure <= highestPossiblePressure) or\
                    (fillPressure <= self.constant.MAXLOWGAUGE):
                        supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        fillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                        self.display.lcd_display_string("Press1: {} bar ".format(round(supplyPressure,2)), 3)
                        self.display.lcd_display_string("Press2: {} bar ".format(round(fillPressure,2)), 4)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.__idle()
                            raise faultErrorException()           
            else:
                # Helium fill process
                self.logger('debug', 'Not the last fill cycle')
                if fillPressure\
                <= self.constant.FILLPRESSURE:
                    self.__heFill()
                    self.display.lcd_display_string("Fill Process...", 2)
                while fillPressure\
                <= self.constant.FILLPRESSURE:
                    supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    fillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                    self.display.lcd_display_string("Press1: {} bar ".format(round(supplyPressure,2)), 3)
                    self.display.lcd_display_string("Press2: {} bar ".format(round(fillPressure,2)), 4)
                    if supplyPressure >= self.constant.PROOFPRESSURE:
                        self.__idle()
                        raise overPressureException()
# MAKE SURE TO ADD A CHECK FOR WHEN LOW GAUGE == HIGH GAUGE
            self.__heFillExit()
            self.display.lcd_display_string("                    ", 2)
            self.display.lcd_display_string("                    ", 3)
            self.display.lcd_display_string("                    ", 4)

            # Increment cycle count
            self.noOfCycles += 1
           
    
    def stateChecks(self):
        self.__initiate()
        self.display.lcd_display_string("Press start", 2)
        supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")

        while (self.startFlag == 0 and self.resetFlag == 0) and (self.stopFlag == 0) :
            self.display.lcd_display_string("No of cycles: %d"%self.cycleCount, 1)
            supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            ventPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            self.display.lcd_display_string("Press1: {} ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL)
            self.display.lcd_display_string("Press2: {} ".format(round(ventPressure,2)), self.constant.VENTPRESSURECHANNEL)

        self.display.lcd_clear()
        
        # This is here to catch the code from running away on a thread by itself and continuing dangerously
        while self.resetFlag == 1 or self.stopFlag == 1:
            print("Halted")
            time.sleep(1)
        
        if (supplyPressure >= self.constant.PROOFPRESSURE) or\
        (supplyPressure < self.constant.MINSUPPLYPRESSURE):
            self.errorFlag = True
            self.logger('error', 'The supply pressure is out of bounds. Allowing user to fix it')
            time.sleep(1)
            self.display.lcd_clear()
            self.display.lcd_display_string("Error!!!",1)
            self.display.lcd_display_string("Supply pressure out",2)
            self.display.lcd_display_string("of bounds",3)
            time.sleep(5)
            self.display.lcd_clear()
            self.display.lcd_display_string("Supply P too high...", 1)
            while (supplyPressure >= self.constant.PROOFPRESSURE) or\
            (supplyPressure < self.constant.MINSUPPLYPRESSURE):
                supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                self.display.lcd_display_string("Press1: {} bar ".format(round(supplyPressure,2)), 2)

            if (supplyPressure >= self.constant.PROOFPRESSURE) or\
            (supplyPressure < self.constant.MINSUPPLYPRESSURE):
                self.logger('error', 'The supply pressure is out of bounds. User failed to fix it')
                self.errorFlag = True
                return False
            else:
                self.errorFlag = False
                self.logger('warning', 'The supply pressure was out of bounds. User succeeded to fix it')
                return True


        elif (supplyPressure > self.constant.MAXSUPPLYPRESSURE) and\
        (supplyPressure < self.constant.PROOFPRESSURE):
            self.errorFlag = False
            self.logger('warning', "The supply pressure is SAFELY high. Program will continue")
            self.__preFillCheck(supplyPressure, 'higher')
            return True
        else:
            self.errorFlag = False
            self.logger('debug', 'The supply pressure was set SAFELY low. Program will continue+')
            self.__preFillCheck(supplyPressure, 'lower')
            return True

    def machineRun(self):
        """
        Method used to check if the sensors report viable values
        for the device to operate safely and as expected
        """
        if self.stateChecks():
            self.logger('debug','Initial state checks pass')
            self.__stateMachine()
            self.startFlag = 0
            self.display.lcd_clear()
            self.display.lcd_display_string("Purge has completed.",1)
            self.display.lcd_display_string("Please restart to",2)
            self.display.lcd_display_string("proceed further.",3)
            while GPIO.input(self.nResetButton):
                time.sleep(0.3)
            return True
        else:
            self.__idle()
            raise faultErrorException() 

class purge(object):
    def __init__(self, noOfCycles, state):
        # Get number of cycles and pass it to parent. Other option is to press cycle
        # button to increment before the purge process begins
        self.runrun = purgeModes(noOfCycles, state)
        
    def runPurge(self):
            
        # Check battery
        
        # Check sensors
        while self.runrun.machineRun():
            pass
        sys.exit()

        
# This is the usage method. Take note of the error handling
def main():
    '''
    Main program function
    '''
    try:
        try:
            test = purge(1,'idle')
            test.runPurge()
            print("program has ended")
        except (overPressureException, pins.emergencyStopException) as e:
            print(e)
            # test.runrun.__idle()
            while GPIO.input(test.runrun.nResetButton):
                time.sleep(0.3)
                # test.runrun.__idle()
                # print("waiting for reset press")
            print("reset button pressed")
            GPIO.cleanup()
            time.sleep(1)
            # self.removeCallBacks()

    except (KeyboardInterrupt, faultErrorException) as e:
        print(e)
        print("\nExited measurements through keyboard interupt")
        time.sleep(1)
        GPIO.cleanup()
        time.sleep(1)

if __name__ == "__main__":
    main()