#!/usr/bin/env python

"""
================================================

Requires modules from "List of dependencies.txt"
================================================
"""
import RPi.GPIO as GPIO
import pins
from loggingdebug import log
from Decorate import customDecorator
import os
from configparser import ConfigParser

from measurements import monitor
from dataclasses import dataclass
import time, sys
try:
    from notificationHandle import emailNotification as notify
except ImportError:
    try:
        import sys
        sys.path.append('.')
        from notificationHandle import emailNotification as notify
    except ImportError:
        raise ImportError(
            "Failed to import library from parent folder")

@dataclass(frozen = True)
class constantsNamespace():
        """
        Class for constants - the only purpose of this dataclass is to create values that cannot be 
        reassigned (constants). Python does not have the const keyword, to avoid errors of
        accidentally writing over constants - the method is to rather prevent it from occuring.
        A name of a value in caps is said to be a constant.
        NOTE: frozen keyword indicates a readonly (sort of)
        """
        # Constants
        MAXSUPPLYPRESSURE = 16
        MINSUPPLYPRESSURE = 4
        PROOFPRESSURE = 24

        MAXLOWGAUGE = 10
        MAXHIGHGAUGE = 34

        PREFILLPRESSURE = 16
        VENTPRESSURE = 0.2
        INITVACUUMPRESSURE = 1
        VACUUMPRESSURE = 0.05
        FILLPRESSURE = 4
        LASTFILLPRESSURE = 16
        SAFETOVACUUM = 0.5

        VACUUMCHANNEL = 1
        BATTERYVOLTCHANNEL = 2
        SUPPLYPRESSURECHANNEL = 3
        VENTPRESSURECHANNEL = 4

class timeOutError(pins.Error):
    """
    Class for timeout error exception.
    Take note of the caps "O"
    """
    def __init__(self, message='Error rasied though a timeout'):
        # Call the base class constructor with the parameters it needs
        super(timeOutError, self).__init__(message)

class faultErrorException(pins.Error):
    """
    Class for error exception
    """
    def __init__(self, message='Error rasied though a fault flag'):
        # Call the base class constructor with the parameters it needs
        super(faultErrorException, self).__init__(message)

class sensorErrorException(pins.Error):
    """
    Class for error exception
    """
    def __init__(self, message='Error rasied though sensor no signal'):
        # Call the base class constructor with the parameters it needs
        super(sensorErrorException, self).__init__(message)

class overPressureException(pins.Error):
    """
    Class for over pressure error exception
    """
    def __init__(self, message='Error rasied though a over pressure whilst active fill'):
        # Call the base class constructor with the parameters it needs
        super(overPressureException, self).__init__(message)

class resetException(pins.Error):
    """
    Class for over reset exception
    """
    def __init__(self, message='Exception rasied through reset'):
        # Call the base class constructor with the parameters it needs
        super(resetException, self).__init__(message)

class timeOutError(pins.Error):
    """
    Class for over reset exception
    """
    def __init__(self, message='Exception rasied through a process taking too long'):
        # Call the base class constructor with the parameters it needs
        super(timeOutError, self).__init__(message)

# inherit ability to control and monitor pins, logging, and notifcations
# This is the superclass!
class purgeModes(monitor.measure, pins.logicPins, notify.emailNotification, log.log):
    def __init__(self, cycleCount = 4, state = 'idle'):
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
        self.timeoutFlag = False
        
        basePath = os.path.dirname(os.path.abspath(__file__))

        timeoutPath = basePath + "/Decorate/timeOuts.ini"
        print(timeoutPath)
        # get the config
        if os.path.exists(timeoutPath):
            self.timecfg = ConfigParser()
            self.timecfg.read(timeoutPath)
            self.venttimeout = self.timecfg.get("timeout", "venttimeout")
            self.initialvactimeout = self.timecfg.get("timeout", "initialvactimeout")
            self.vacuumtimeout = self.timecfg.get("timeout", "vacuumtimeout")
            self.filltimeout = self.timecfg.get("timeout", "filltimeout")
        else:
            # print("Config not found! Exiting!")
            # sys.exit(1)
            self.logger('error', 'Timeout config file not found')

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
        # GPIO.output(self.fillValve1, 1)
        GPIO.output(self.fillValve1, 0)
        # GPIO.output(self.fillValve2, 0)
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
        # GPIO.output(self.fillValve2, 1)
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
        # GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 0)

    def __vent(self):
        print("vent")
        GPIO.output(self.fillValve1, 0)
        # GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 1)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 1)

    def __ventExit(self):
       print("exit vent")
       GPIO.output(self.fillValve1, 0)
    #    GPIO.output(self.fillValve2, 0)
       GPIO.output(self.ventValve, 0)
       GPIO.output(self.vacValve, 0)
       GPIO.output(self.enPump, 0)
       GPIO.output(self.enStepMotor, 0)
       GPIO.output(self.enFan, 1)
    
    def __vacInit(self):
        print("Vacuum initialisation")
        GPIO.output(self.fillValve1, 0)
        # GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.enPump, 1)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 1)


    def __vac(self):
        print("Vacuum")
        GPIO.output(self.fillValve1, 0)
        # GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.enPump, 1)
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
        # GPIO.output(self.fillValve2, 0)
        GPIO.output(self.ventValve, 0)
        GPIO.output(self.vacValve, 0)
        time.sleep(1)   # This closes the valve before the vacuum pump turns off
                        # reducing the chance of contamination
        GPIO.output(self.enPump, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enFan, 0)

    def __preFillCheck(self, inputPressure, comparison):

        # self.__preFillCheckValves()
        supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
        ventPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
        self.display.lcd_clear()
        if comparison == 'higher':

            if (ventPressure >= self.constant.MAXLOWGAUGE): # and supplyPressure >= self.constant.PREFILLPRESSURE:
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
                    if self.stopFlag:
                        self.logger('debug', 'Emergency stop flag. Exiting')
                        raise pins.emergencyStopException()

                self.__heFillExit()
        else:
            if (ventPressure >= self.constant.MAXLOWGAUGE): # and supplyPressure >= inputPressure:
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
                    if self.stopFlag:
                        self.logger('debug', 'Emergency stop flag. Exiting')
                        raise pins.emergencyStopException()

                self.__heFillExit()
        self.__idle()

    def __safetyCheck(self):
        pass
    
    # Take note that this is not a set of char being passes into
    # this decorator. It is an attribute of purgeModes class.
    # See __init__ for self.venttimeout

    @customDecorator.customDecorators.exitAfter('venttimeout')
    def __ventProcess(self):
        try:
            # Venting process
            ventPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            if (ventPressure < 0) and self.stopFlag == 0 and self.resetFlag == 0:
                # Insert error here
                self.__vent()
                self.display.lcd_display_string("Venting vacuum...", 2)
            elif (ventPressure >= self.constant.VENTPRESSURE) and self.stopFlag == 0 and self.resetFlag == 0:
                self.__vent()
                self.display.lcd_display_string("Venting Process...", 2)
            while ventPressure >= self.constant.VENTPRESSURE or ventPressure < -0.5:
                ventPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                self.display.lcd_display_string("Press2: {} bar ".format(round(ventPressure,2)), 3)
                if self.stopFlag:
                    self.logger('debug', 'Emergency stop flag. Exiting from vent.')
                    raise pins.emergencyStopException()
        except KeyboardInterrupt:
            print("IN VENT INIT KEYBOARD INTERUPT")
            self.stopFlag = True
            self.timeoutFlag = True
            self.__ventExit()
        finally:
            if self.timeoutFlag:
                self.__idle()
                self.logger('error', 'Vent timeout errror!')
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 8:",1)
                self.display.lcd_display_string("Vent timeout",2)
                self.display.lcd_display_string("Press Reset",4)
                raise timeOutError()
            else:
                self.__ventExit()
                self.display.lcd_display_string("                    ", 2)
                self.display.lcd_display_string("                    ", 3)
                
    @customDecorator.customDecorators.exitAfter('initialvactimeout')
    def __initVacProcess(self):
        try:
            self.display.lcd_display_string("Initisalising vac...", 2)
            self.display.lcd_display_string("Vac: ",3)
            self.__vacInit()
            vacuumPressure = self.vacuumConversion(self.readVoltage(self.constant.VACUUMCHANNEL))
            while vacuumPressure >= self.constant.INITVACUUMPRESSURE:
                vacuumPressure = self.vacuumConversion(self.readVoltage(self.constant.VACUUMCHANNEL))
                self.display.lcd_display_string("{:.2e}".format(vacuumPressure),3,5)
                if self.stopFlag:
                    self.logger('debug', 'Emergency stop flag. Exiting from initial vacuum.')
                    raise pins.emergencyStopException()
        except KeyboardInterrupt:
            print("IN VAC INIT KEYBOARD INTERUPT")
            self.timeoutFlag = True
            self.stopFlag = True
            self.__vacExit()
        finally:
            if self.timeoutFlag:
                self.__idle()
                self.logger('error', 'Initialising vacuum timeout errror!')
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 5:",1)
                self.display.lcd_display_string("Initial vac timeout",2)
                self.display.lcd_display_string("Press Reset",4)
                raise timeOutError()
            else:
                self.__vacExit()
                self.display.lcd_display_string("                    ", 2)
                self.display.lcd_display_string("                    ", 3)
            
    @customDecorator.customDecorators.exitAfter('vacuumtimeout')
    def __vacProcess(self):
        try:
            # Vacuum process
            fillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            if (fillPressure >= self.constant.SAFETOVACUUM) and self.stopFlag == 0 and self.resetFlag == 0:
# Remember to change the error class to a suitable vacuum name and also display what needs to be displayed
                raise overPressureException()
            else:
                self.display.lcd_display_string("Vacuum Process...   ", 2)
                self.display.lcd_display_string("Vac: ",3)
                self.__vac()
            time.sleep(1)
            vacuumPressure = self.vacuumConversion(self.readVoltage(self.constant.VACUUMCHANNEL))
            if (vacuumPressure >= self.constant.INITVACUUMPRESSURE) and self.stopFlag == 0 and self.resetFlag == 0:
                while vacuumPressure >= self.constant.VACUUMPRESSURE:
                    vacuumPressure = self.vacuumConversion(self.readVoltage(self.constant.VACUUMCHANNEL))
                    self.display.lcd_display_string("{:.2e}".format(vacuumPressure),3,5)
                    if self.stopFlag:
                        self.logger('debug', 'Emergency stop flag. Exiting from vacuum.')
                        raise pins.emergencyStopException()
            else:
# Remember to change the error class to a suitable vacuum name and also display what needs to be displayed
                raise overPressureException()

        except KeyboardInterrupt:
            self.timeoutFlag = True
            self.__vacExit()
        finally:
            if self.timeoutFlag:
                self.__idle()
                self.logger('error', 'Vacuum timeout errror!')
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 21:",1)
                self.display.lcd_display_string("Vacuum timeout",2)
                self.display.lcd_display_string("Press Reset",4)
                raise timeOutError()
            else:
                self.__vacExit()
                self.display.lcd_display_string("                    ", 2)
                self.display.lcd_display_string("                    ", 3)
    

    @customDecorator.customDecorators.exitAfter('filltimeout')
    def __fillProcess(self):
        # Check if supply pressure is safe to apply
        try:
            self.__initiate()
            supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            fillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            if (supplyPressure >= self.constant.PROOFPRESSURE) or\
            (supplyPressure < self.constant.MINSUPPLYPRESSURE):
                self.errorFlag = True
                self.logger('error', 'The supply pressure is out of bounds.')
                time.sleep(1)
                self.display.lcd_clear()
                self.display.lcd_display_string("Error!!!",1)
                self.display.lcd_display_string("Supply pressure out",2)
                self.display.lcd_display_string("of bounds",3)
                time.sleep(5)
                raise overPressureException()
            else:
                self.logger('debug',"The supply pressure is within bounds")

            # Check whether it is the last cycle, if it is, fill to 16 bar rather
            if self.lastCycleFlag:
                # Helium fill process
                if (supplyPressure >= self.constant.LASTFILLPRESSURE and supplyPressure < self.constant.PROOFPRESSURE) and self.stopFlag == 0:
                    self.logger('debug',"The supply pressure is greater than 16bar for last fill")
                    self.__heFill()
                    self.display.lcd_display_string("Last Fill Process...", 2)
                    self.display.lcd_display_string("Press1:", self.constant.SUPPLYPRESSURECHANNEL)
                    self.display.lcd_display_string("Press2:", self.constant.VENTPRESSURECHANNEL)

                    while (supplyPressure <= self.constant.LASTFILLPRESSURE) or\
                    (fillPressure <= self.constant.MAXLOWGAUGE):
                        supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        fillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                        self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                        self.display.lcd_display_string("{} bar ".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.__idle()
                            raise overPressureException()
                        elif self.stopFlag:
                            self.logger('debug', 'Emergency stop flag. Exiting')
                            raise pins.emergencyStopException()
                else:
                    self.logger('debug',"The supply pressure is less than 16bar for last fill")
                    self.__initiate()
                    time.sleep(1)
                    highestPossiblePressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    self.__heFill()
                    self.display.lcd_display_string("Last Fill Process...", 2)
                    self.display.lcd_display_string("Press1:", self.constant.SUPPLYPRESSURECHANNEL)
                    self.display.lcd_display_string("Press2:", self.constant.VENTPRESSURECHANNEL)

                    while (supplyPressure <= highestPossiblePressure) or\
                    (fillPressure <= self.constant.MAXLOWGAUGE) and self.stopFlag == 0:
                        supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        fillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                        self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                        self.display.lcd_display_string("{} bar ".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.__idle()
                            raise faultErrorException()
                        elif self.stopFlag:
                            self.logger('debug', 'Emergency stop flag. Exiting')
                            raise pins.emergencyStopException()         
            else:
                # Helium fill process
                self.logger('debug', 'Not the last fill cycle')
                if fillPressure <= self.constant.FILLPRESSURE and self.stopFlag == 0:
                    self.__heFill()
                    self.display.lcd_display_string("Fill Process...", 2)
                    self.display.lcd_display_string("Press1: {} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL)
                    self.display.lcd_display_string("Press2: {} bar ".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL)
                while fillPressure <= self.constant.FILLPRESSURE:
                    supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    fillPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                    self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                    self.display.lcd_display_string("{} bar ".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                    if supplyPressure >= self.constant.PROOFPRESSURE:
                        self.__idle()
                        raise overPressureException()
                    elif self.stopFlag:
                        self.logger('debug', 'Emergency stop flag. Exiting')
                        raise pins.emergencyStopException()
        except KeyboardInterrupt:
            self.timeoutFlag = True
            self.__heFillExit()
        finally:
            if self.timeoutFlag:
                self.__idle()
                self.logger('error', 'Fill timeout errror!')
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 7:",1)
                self.display.lcd_display_string("Fill timeout",2)
                self.display.lcd_display_string("Press Reset",4)
                raise timeOutError()
            else:
                # MAKE SURE TO ADD A CHECK FOR WHEN LOW GAUGE == HIGH GAUGE
                self.__heFillExit()
                self.display.lcd_display_string("                    ", 2)
                self.display.lcd_display_string("                    ", 3)
                self.display.lcd_display_string("                    ", 4)


        
    
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
            
            
            self.__ventProcess()

            self.__initVacProcess()

            self.__vacProcess()
    
            self.__fillProcess()

            # Increment cycle count
            self.noOfCycles += 1
           
    
    def stateChecks(self):
        self.__initiate()

        self.display.lcd_display_string("No of cycles:", 1)
        self.display.lcd_display_string("Press start", 2)
        self.display.lcd_display_string("Press1:", 3)
        self.display.lcd_display_string("Press2:", 4)

        supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
        ventPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")

        while (self.startFlag == 0 and self.resetFlag == 0) and (self.stopFlag == 0) :
            self.display.lcd_display_string("%d  "%self.cycleCount, 1, 14)
            supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            ventPressure = self.pressureConversion(self.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            self.display.lcd_display_string("{} ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 8)
            self.display.lcd_display_string("{} ".format(round(ventPressure,2)), self.constant.VENTPRESSURECHANNEL, 8)

        self.display.lcd_clear()
        
        # This is here to catch the code from running away on a thread by itself and continuing dangerously
        while self.resetFlag == 1 or self.stopFlag == 1:
            # print("Halted")
            time.sleep(0.2)
        
        if (supplyPressure >= self.constant.PROOFPRESSURE) or (supplyPressure < self.constant.MAXSUPPLYPRESSURE) or (ventPressure < -2):

            if supplyPressure < -8 and ventPressure < -2:
                self.errorFlag = True
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 2 & 4:",1)
                self.display.lcd_display_string("Sensor 1 and 2 not",2)
                self.display.lcd_display_string("found",3)
                self.display.lcd_display_string("Press Reset",4)
                raise sensorErrorException()

            elif supplyPressure < -8 and ventPressure > -2:
                self.errorFlag = True
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 2:",1)
                self.display.lcd_display_string("Sensor 1 not found",2)
                self.display.lcd_display_string("Press Reset",4)
                raise sensorErrorException()
            elif supplyPressure > -8 and ventPressure < -2:
                self.errorFlag = True
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 4:",1)
                self.display.lcd_display_string("Sensor 2 not found",2)
                self.display.lcd_display_string("Press Reset",4)
                raise sensorErrorException()
            else:
                self.errorFlag = True
                self.logger('error', 'The supply pressure is out of bounds. Allowing user to fix it')
                time.sleep(1)
                self.display.lcd_clear()
                self.display.lcd_display_string("Error!!!",1)
                self.display.lcd_display_string("Supply pressure out",2)
                self.display.lcd_display_string("of bounds",3)
                time.sleep(5)
                self.display.lcd_clear()
                if (supplyPressure >= self.constant.PROOFPRESSURE):
                    self.display.lcd_display_string("Supply P too high...", 1)
                else:
                    self.display.lcd_display_string("Supply P too low...", 1)

                self.display.lcd_display_string("Please fix!", 4)
                self.display.lcd_display_string("Press1:", 2)

                while (supplyPressure >= self.constant.PROOFPRESSURE) or (supplyPressure <= self.constant.MAXSUPPLYPRESSURE):
                    supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), 2, 8)
                
                time.sleep(1)
                supplyPressure = self.pressureConversion(self.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                if (supplyPressure >= self.constant.PROOFPRESSURE) or (supplyPressure <= self.constant.MAXSUPPLYPRESSURE):
                    self.logger('error', 'The supply pressure is out of bounds. User failed to fix it')
                    self.errorFlag = True
                    return False
                else:
                    self.errorFlag = False
                    self.logger('warning', 'The supply pressure was out of bounds. User succeeded to fix it')
                    return True
                    """
                    if (supplyPressure > self.constant.MAXSUPPLYPRESSURE) and (supplyPressure < self.constant.PROOFPRESSURE):
                        self.__preFillCheck(supplyPressure, 'higher')
                    else:
                        self.__preFillCheck(supplyPressure, 'lower')
                    return True
                    """

        elif (supplyPressure > self.constant.MAXSUPPLYPRESSURE) and\
        (supplyPressure < self.constant.PROOFPRESSURE):
            self.errorFlag = False
            self.logger('warning', "The supply pressure is SAFELY high. Program will continue")
            # self.__preFillCheck(supplyPressure, 'higher')
            return True
        else:
            self.errorFlag = False
            self.logger('debug', 'The supply pressure was set SAFELY low. Program will continue+')
            # self.__preFillCheck(supplyPressure, 'lower')
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
            self.sendMailAttachment(
                subject = "Purgejig bot has a good message for you!",
                bodyText = "Dear Purgejig user,\n\nThe purge you initiated has successfully completed.\n\nKind regards,\nPurgejig bot")
            self.display.lcd_display_string("Purge has completed.",1)
            self.display.lcd_display_string("Please restart to",2)
            self.display.lcd_display_string("proceed further.",3)

            while GPIO.input(self.nResetButton):
                time.sleep(0.3)
            return True
    # stateChecks should only return false if some major stuff-up happens
        else:
            self.__idle()
            raise faultErrorException() 

class purge(object):
    def __init__(self, noOfCycles, state):
        # Get number of cycles and pass it to parent. Other option is to press cycle
        # button to increment before the purge process begins
        self.runrun = purgeModes(noOfCycles, state)
        
    def runPurge(self):
        """
        Two seperate threads should run here. One involving battery health (low prio) and the other should handle purging (high prio)

        """
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
            test = purge(4,'idle')
            test.runPurge()
            print("program has ended")
        except (overPressureException, pins.emergencyStopException, timeOutError, sensorErrorException) as e:
            print(e)
            # test.runrun.__idle()
            while GPIO.input(test.runrun.nResetButton):
                time.sleep(0.3)
                # test.runrun.__idle()
                # print("waiting for reset press")
            print("reset button pressed")
            # GPIO.cleanup()
            time.sleep(1)
            # self.removeCallBacks()

    except (KeyboardInterrupt, faultErrorException) as e:
        print(e)
        print("\nExited measurements through keyboard interupt")
        test.runrun.display.lcd_clear()
        
        test.runrun.display.lcd_display_string("Error! Program",1)
        test.runrun.display.lcd_display_string("exited externally.",2)
        test.runrun.display.lcd_display_string("Perform a full power",3)
        test.runrun.display.lcd_display_string("cycle to continue.",4)
        time.sleep(1)
        GPIO.cleanup()
        time.sleep(1)
    finally:
        pass

if __name__ == "__main__":
    main()