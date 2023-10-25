#!/usr/bin/env python

"""
================================================

Requires modules from "List of dependencies.txt"
================================================
"""
import RPi.GPIO as GPIO
import os
from configparser import ConfigParser
from dataclasses import dataclass
import time, sys
from ctypes import c_wchar_p, c_char_p, c_char

# Concurrency
from multiprocessing import Process, current_process, RLock, Lock, BoundedSemaphore, Queue, Array, Value
import subprocess
import threading
import pins
from loggingdebug import log
# from Display import displayLCD
from Display import oldToNewInterface
from Decorate import customDecorator
from measurements import monitor, checkHealth
from Multicore import multiCore, safetyCheck, lowSupplyCheck, batMon, userinput
# from Testing import inputTest as userinput

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

        MAXLOWGAUGE = 10
        MAXHIGHGAUGE = 34

        BATLOW = 50
        # These are the values returned (roughly) for broken gauge
        SUPPLYBROKEN = -8
        VENTBROKEN = -2
        VACUUMBROKEN = -1
        # Set pressure values
        MAXSUPPLYPRESSURE = 16
        MINSUPPLYPRESSURE = 4
        PROOFPRESSURE = 24
        EMERGENCYVENTPRESSURE = 22
        
        PREFILLPRESSURE = 16
        VENTPRESSURE = 0.2
        INITVACUUMPRESSURE = 1
        # Set this to 0.05 (5E-2 mbar)
        # VACUUMPRESSURE = 0.1
        VACUUMPRESSURE = 0.05
        FILLPRESSURE = 4
        LASTFILLPRESSURE = 16
        SAFETOVACUUM = 0.5
        # ADC channels
        VACUUMCHANNEL = 1
        BATTERYVOLTCHANNEL = 2
        SUPPLYPRESSURECHANNEL = 3
        VENTPRESSURECHANNEL = 4

class timeOutError(pins.Error):
    """
    Class for timeout error exception.
    Take note of the caps "O"
    """
    def __init__(self, message='Error rasied though a timeout.'):
        # Call the base class constructor with the parameters it needs
        super(timeOutError, self).__init__(message)

class faultErrorException(pins.Error):
    """
    Class for error exception
    """
    def __init__(self, message='Error rasied though a fault flag.'):
        # Call the base class constructor with the parameters it needs
        super(faultErrorException, self).__init__(message)

class sensorErrorException(pins.Error):
    """
    Class for sensor error exception
    """
    def __init__(self, message='Error rasied though sensor no signal.'):
        # Call the base class constructor with the parameters it needs
        super(sensorErrorException, self).__init__(message)

class overPressureException(pins.Error):
    """
    Class for over pressure error exception
    """
    def __init__(self, message='Error rasied though a over pressure whilst active fill.'):
        # Call the base class constructor with the parameters it needs
        super(overPressureException, self).__init__(message)

class vacuumException(pins.Error):
    """
    Class for vacuum pressure error exception
    """
    def __init__(self, message='Error rasied though a vacuum load not detected.'):
        # Call the base class constructor with the parameters it needs
        super(vacuumException, self).__init__(message)

class resetException(pins.Error):
    """
    Class for over reset exception
    """
    def __init__(self, message='Exception rasied through reset.'):
        # Call the base class constructor with the parameters it needs
        super(resetException, self).__init__(message)
        
class batteryError(pins.Error):
    """
    Class for battery or related circuity misbehaving
    """
    def __init__(self, message='Exception rasied through a faulty charging/battery related issue.'):
        # Call the base class constructor with the parameters it needs
        super(batteryError, self).__init__(message)

class shutdownException(pins.Error):
    """
    Class for battery draining in idle
    """
    def __init__(self, message='Exception rasied through a device left in idle whilst battery drains.'):
        # Call the base class constructor with the parameters it needs
        super(shutdownException, self).__init__(message)

# class timeOutError(pins.Error):
#     """
#     Class for over reset exception
#     """
#     def __init__(self, message='Exception rasied through a process taking too long.'):
#         # Call the base class constructor with the parameters it needs
#         super(timeOutError, self).__init__(message)



# inherit ability to control and monitor pins, logging, and notifcations
# This is the superclass!
"""Inheriting because... lazy. Composition over inheritance!!! Might fix this in future"""
class purgeModes(pins.logicPins):
    def __init__(self, measure, lock, sharedBools, sharedValues, state):
        """
        Class constructor - Initialise functionality for creating rules of purge
        :param noOfCycles: 
        :type int:
        :param state: 
        :type string: 
        """
        self.i2cLock = lock
        super().__init__(sharedBools, lock, sharedValues)
        # constants dataclass where all values that shan't be changed reside

        self.constant = constantsNamespace()
        self.measure = measure
            # Place to store sensor values - potentially...
        self.sharedValues = sharedValues
        # self.i2cLock = lock
        # self.display = displayLCD.lcd()
        self.display = oldToNewInterface.lcd()
        self.mail = notify.emailNotification()
        self.purgeLog = log.log()
        # self.decorate = customDecorator.customDecorators(self.purgeLog)
        # self = self.measure.pin

        # This gets inherited from pins
        self.purgeLog.logger('debug', 'Purge constructor has run!')
        GPIO.setmode(GPIO.BCM)
        GPIO.output(self.enBattery, 1)
        self.__idle()

        # Variables
        # self.cycleCount = cycleCount
        self.noOfCycles = 0
        self.state = state

        # Flags
        self.preFilledFlag = True
        self.lastCycleFlag = False
        self.timeoutFlag = False
        self.vacexception = False
        self.overPressureFlag = False
        # self..resetFlag = False
        
        basePath = os.path.dirname(os.path.abspath(__file__))

        timeoutPath = basePath + "/Decorate/timeOuts.ini"
        self.purgeLog.logger('debug',"Timeout config file path: {}".format(timeoutPath))
        # get the config for timeouts
        if os.path.exists(timeoutPath):
            self.timecfg = ConfigParser()
            self.timecfg.read(timeoutPath)
            self.venttimeout = self.timecfg.get("timeout", "venttimeout")
            self.initialvactimeout = self.timecfg.get("timeout", "initialvactimeout")
            self.vacuumtimeout = self.timecfg.get("timeout", "vacuumtimeout")
            self.filltimeout = self.timecfg.get("timeout", "filltimeout")
            self.dPdtTime = self.timecfg.get("timeout", "dPdtTime")
            self.acceptabledPdt = self.timecfg.get("timeout", "acceptabledPdt")
            self.chargetimeout = self.timecfg.get("timeout","chargetimeout")
        else:
            # print("Config not found! Exiting!")
            # sys.exit(1)
            self.purgeLog.logger('error', 'Timeout config file not found')
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 20",1, 6)
                self.display.lcd_display_string("Timeout",2, 6)
                self.display.lcd_display_string("Config file failed!",3)
                self.display.lcd_display_string("Check cfg file.",4, 2)
            
            self.__beepOn()
            time.sleep(10)
            self.__beepOff()
            

        
        # self.parallelProcessQueue()
        """Dont think we need this anymore"""
        self.p = Process(target=self.__fixableError)

    def checkMains(self):
        batteryVoltageCharge = 0
        batteryVoltageNoCharge = 0
        if self.i2cLock.acquire(timeout=0.005):
            sampleavg = 15
            self.i2cLock.release()
        else:
            sampleavg = 4
        # This disables charging to the device
        self.batteryStateSet(batteryEnable = 1, chargeEnable=1)

        for i in range(sampleavg):
            
            if self.i2cLock.acquire(timeout=0.005):
                batteryVoltageNoCharge += self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL)
                self.i2cLock.release()
            else:
                batteryVoltageNoCharge += self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL)
        batteryVoltageNoCharge = batteryVoltageNoCharge/sampleavg

        # This re-enables charging to the device
        self.batteryStateSet(batteryEnable = 1, chargeEnable=0)
        for i in range(sampleavg):
            
            if self.i2cLock.acquire(timeout=0.005):
                batteryVoltageCharge += self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL)
                self.i2cLock.release()
            else:
                batteryVoltageCharge += self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL)
        batteryVoltageCharge = batteryVoltageCharge/sampleavg
        
        difference = batteryVoltageCharge - batteryVoltageNoCharge
        self.batteryStateSet(batteryEnable = 1, chargeEnable=1)
        self.batteryStateSet(batteryEnable = 1, chargeEnable=0)
        # print(self.measure.statusMonitor())
        if round( (difference), 6) > 0 or (self.measure.statusMonitor() == 'Charging'):
            self.purgeLog.logger('debug', 'Mains is on.')
            return True
        else:
            self.purgeLog.logger('debug', 'Mains is off')
            return False
    
    def eVentHandle(self):
        self.__emergencyVent()
        self.overPressureFlag = True
        self.sharedBoolFlags[5] = self.overPressureFlag
        self.purgeLog.logger('error','Device is emergency venting')
        subject = "Purgejig bot has a bad message for you!"
        bodyText = ("Dear Purgejig user,\n\n;"
                    "Error 10;Supply over-pressure occured;The Emergency vent state is active. Lower supply immediatelty. See logs FMI.;\n\n"
                    "Kind regards,\nPurgejig bot")
        self.display.lcd_clear()
        self.display.lcd_display_string("Error 10",1, 6)
        self.display.lcd_display_string("Supply overpressure!",2, 0)
        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
        self.display.lcd_display_string("P1={:5.2f} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 4)
        self.display.lcd_display_string("Lower supply!",4, 3)
        
        parallelMail = Process(target=self.mail.sendMailAttachment, args=(subject, bodyText,))
        parallelMail.start()
        # if self.mail.sendMailAttachment(subject, bodyText):
        #     self.display.lcd_display_string("Error 10",1, 6)
        # else:
        #     self.display.lcd_display_string("Error 10 & 16",1, 3)
        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
        while supplyPressure >= 1:
            # with self.i2cLock:
            supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
        
        time.sleep(1)
        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
        if supplyPressure < self.constant.EMERGENCYVENTPRESSURE:
            self.purgeLog.logger('debug','Device supply pressure is safe.')
            self.display.lcd_clear()
            self.display.lcd_display_string("Supply pressure safe",1)
            self.display.lcd_display_string("Venting manifold",2, 2)
            ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            self.display.lcd_display_string("P2={:5.2f} bar ".format(round(ventPressure,2)), 3, 4)
            
            # Pressure has been corrected
            # self.__idle()
            self.__emergencyVentClose
            # self.__beepOff()
            # with self.sharedBoolFlags.get_lock():
            self.sharedBoolFlags[3] = False
            # ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            while ventPressure > self.constant.MINSUPPLYPRESSURE:
                ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                self.display.lcd_display_string("{:5.2f}".format(round(ventPressure,2)), 3, 7)
            self.__idle()
            self.__beepOff()
            self.display.lcd_clear()
            self.display.lcd_display_string("Emergency vent",1, 3)
            self.display.lcd_display_string("success",2, 6)
            self.display.lcd_display_string("Press RESET",3, 4)
            
        else:
            self.__emergencyVent()
            self.purgeLog.logger('error','Device is emergency venting again.')

            self.eVentHandle()
            # self.display.lcd_clear()
            # self.display.lcd_display_string("Error 10",1, 6)
            # self.display.lcd_display_string("Supply overpressure!",2)
            # supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            # self.display.lcd_display_string("P1={:5.2f} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 4)
            # self.display.lcd_display_string("Lower supply!",4, 3)
            # while supplyPressure > self.constant.EMERGENCYVENTPRESSURE:
            #     # with self.i2cLock:
            #     supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            #     self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)

            # self.display.lcd_clear()
            # self.display.lcd_display_string("Supply pressure safe",1)
            # self.display.lcd_display_string("Venting manifold",2, 2)
            # ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            # self.display.lcd_display_string("P2={:5.2f} bar ".format(round(ventPressure,2)), 3, 4)
            # self.__emergencyVentClose
            # self.sharedBoolFlags[3] = False
            # while ventPressure > self.constant.MINSUPPLYPRESSURE:
            #     ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            #     self.display.lcd_display_string("{:5.2f}".format(round(ventPressure,2)), 3, 7)
            # self.__idle()
            # self.__beepOff()
            # self.display.lcd_clear()
            # self.display.lcd_display_string("Emergency vent",1, 3)
            # self.display.lcd_display_string("success",2, 6)
            # self.display.lcd_display_string("Press RESET",3, 4)

            # self.__idle()
            # self.__beepOff()
        self.overPressureFlag = False
        self.sharedBoolFlags[5] = self.overPressureFlag
        parallelMail.join()

    def __fixableError(self):
        self.purgeLog.logger('warning','Entering fix error user notifier')
        with self.sharedBoolFlags.get_lock():
            self.errorFlag = self.sharedBoolFlags[3]
        while self.errorFlag == 0 and (self.stopFlag == 0) and (self.resetFlag == 0):
            time.sleep(0.5)
            with self.sharedBoolFlags.get_lock():
                self.errorFlag = self.sharedBoolFlags[3]

        while self.errorFlag and (self.stopFlag == 0) and (self.resetFlag == 0):
            with self.sharedBoolFlags.get_lock():
                self.errorFlag = self.sharedBoolFlags[3]
            if self.stopFlag:
                with self.i2cLock:
                    self.display.backlight(0)
                time.sleep(0.5)
                with self.i2cLock:
                    self.display.backlight(1)
            else:
                # self.display.backlight(0)
                self.toggleBeep(0)
                time.sleep(0.5)
                self.toggleBeep(1)
                # self.display.backlight(1)
            time.sleep(1)
        self.toggleBeep(0)
        self.purgeLog.logger('warning','Exiting fix error user notifier')
        return True

    def batMon(self, queue):
        pass

    @customDecorator.customDecorators.exitAfter('chargetimeout')
    def checkBattery(self, state):
        with self.i2cLock:
            self.display.lcd_display_string("BATTERY CHECK",2,3)        
        
        # Its almost uncanny - assume eskom is off
        eskomIsOn = False
        majorFaultCounter = 0

        batteryStatus = self.measure.statusMonitor()
        # batteryStatus = 'Fault'
        # batteryStatus = 'Major fault'
        if batteryStatus == 'Major fault':
            self.purgeLog.logger('warning', 'Major fault on battery system.')
            subject = "Purgejig bot has a bad message for you!"
            bodyText = ("Dear Purgejig user,\n\n;"
                        "Error 11;Battery monitoring major fault triggered;Attempting to continue... See logs FMI.;\n\n"
                        "Kind regards,\nPurgejig bot")
            self.toggleBeep(1)
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 11",1, 6)
                self.display.lcd_display_string("Bat mon major fault.",2)
                self.display.lcd_display_string("Attempting to",3, 3)
                self.display.lcd_display_string("proceed...",4, 5)
            if self.mail.sendMailAttachment(subject, bodyText):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 11",1, 6)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 11 & 16",1, 3)
            batteryStatus = self.measure.statusMonitor()
            while batteryStatus == 'Major fault':
                if majorFaultCounter >= 3:
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[3] = True
                        # self.errorFlag = True
                    
                    # self.stopFlag = True
                    self.purgeLog.logger('error', 'Major fault not recovered.')
                    subject = "Purgejig bot has a bad message for you!"
                    bodyText = ("Dear Purgejig user,\n\n;"
                                "Error 11;Battery monitoring major fault triggered;The attempt to continue has failed.See logs FMI.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    if self.mail.sendMailAttachment(subject, bodyText):
                        with self.i2cLock:
                            # self.display.lcd_clear()
                            self.display.lcd_display_string("                    ",3)
                            self.display.lcd_display_string("Power-off device",4, 2)
                    else:
                        with self.i2cLock:
                            self.display.lcd_display_string("                    ",3)
                            self.display.lcd_display_string("Email failed",3, 4)
                            self.display.lcd_display_string("Power-off device",4, 2)

                    raise faultErrorException()
                else:
                    self.purgeLog.logger('debug', 'Major fault counter: {}.'.format(majorFaultCounter))
                    majorFaultCounter += 1
                    time.sleep(5)
                batteryStatus = self.measure.statusMonitor()
            self.__beepOff()
            self.purgeLog.logger('debug', 'Major fault recovered.')
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Proceeding",2,5)
            time.sleep(1)
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("BATTERY CHECK",2,3)
        elif batteryStatus == 'Fault':
            self.purgeLog.logger('debug', 'Minor fault on battery system.')
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 12",1, 6)
                self.display.lcd_display_string("Bat mon minor fault",2)
                self.display.lcd_display_string("                    ",3)
                self.display.lcd_display_string("No action req.",4, 3)
            subject = "Purgejig bot has a bad message for you!"
            bodyText = ("Dear Purgejig user,\n\n;"
                        "Error 12;Battery monitoring minor fault triggered;Device will continue... See logs FMI.;\n\n"
                        "Kind regards,\nPurgejig bot")
            if self.mail.sendMailAttachment(subject, bodyText):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 12",1, 6)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 12 & 16",1, 3)
                    self.display.lcd_display_string("Email failed,",3, 3)
                    self.display.lcd_display_string("Please fix!",4, 4)
            minorFaultCounter = 0
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = True
                # self.errorFlag = True
            
            while minorFaultCounter < 10:
                # There is no need to thread/multiprocess this
                time.sleep(0.5)
                minorFaultCounter +=1
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = False
                # self.errorFlag = False
            time.sleep(1)
        
        batteryVoltageCharge = 0
        batteryVoltageNoCharge = 0
        sampleavg = 15

        # This disables charging to the device
        self.batteryStateSet(batteryEnable = 1, chargeEnable=1)
        for i in range(sampleavg):
            with self.i2cLock:
                batteryVoltageNoCharge += self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL)
        
        batteryVoltageNoCharge = batteryVoltageNoCharge/sampleavg
        # print(batteryVoltageNoCharge)

        # This re-enables charging to the device
        self.batteryStateSet(batteryEnable = 1, chargeEnable=0)
        for i in range(sampleavg):
            with self.i2cLock:
                batteryVoltageCharge += self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL)
            
        
        batteryVoltageCharge = batteryVoltageCharge/sampleavg
        # print(batteryVoltageCharge)

        
        difference = batteryVoltageCharge - batteryVoltageNoCharge
        # print(round(difference, 6))
        if round( (difference), 6) > 0 and (self.measure.statusMonitor() == 'Charging'):
            eskomIsOn = True
            self.purgeLog.logger('debug', 'Mains is on.')
        else:
            eskomIsOn = False
            self.purgeLog.logger('debug', 'Mains is off')

        if eskomIsOn:
            self.batteryStateSet(batteryEnable = 0, chargeEnable=1)
            # print("Eskom is on")
        else:
            self.batteryStateSet(batteryEnable = 1, chargeEnable=1)
            # print("Eskom is off")
        # settling time
        time.sleep(0.1)

        # Measure the bat voltage as in SOC
        with self.i2cLock:
            batPercent = self.measure.stateOfCharge(self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL))
        # batPercent = 30
        if batPercent >= self.constant.BATLOW:
            self.purgeLog.logger('debug','Battery SOC is good.')
        else:
            batTimeoutFlag = False
            try:
                if eskomIsOn:
                    self.purgeLog.logger('debug','Battery SOC is less than 40%. Waiting for charge.')
                    subject = "Purgejig bot has a bad message for you!"
                    bodyText = ("Dear Purgejig user,\n\n;"
                                "Error 13;Battery voltage is too low;The batteries wont hold through load-shedding, the batteries will be attempting to charge. See logs FMI.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    self.__beepOn()
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 13",1, 6)
                        self.display.lcd_display_string("Bat critically low,",2, 1)
                        self.display.lcd_display_string("charging to 40%",3, 2)
                        self.display.lcd_display_string("Battery: ",4, 4)
                    if self.mail.sendMailAttachment(subject, bodyText):
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 13",1, 6)
                    else:
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 13 & 16",1, 3)
                            self.display.lcd_display_string(" Email failed!    ",3, 2)
                    
                    with self.i2cLock:
                        batPercent = self.measure.stateOfCharge(self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL))
                        self.display.lcd_display_string(str(batPercent-10)+"% ",4,13)
                    time.sleep(5)
                    # with self.i2cLock:
                    #     self.display.lcd_clear()
                    #     self.display.lcd_display_string("BATTERY CHECK",2,3) 
                    self.__beepOff()
                    # This sets charge enable and battery enable 
                    self.batteryStateSet(batteryEnable = 1, chargeEnable=0)
                    with self.i2cLock:
                        self.display.lcd_display_string("time elapsed: 00:00",3, 1)
                    # batPercent = 30
                    startTime = time.time()
                    while batPercent < self.constant.BATLOW:
                        hours, remainder = divmod((time.time()-startTime), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        displayTime = "{:0>2}:{:0>2}".format(int(hours),int(minutes))
                        time.sleep(5)
                        with self.i2cLock:
                            self.display.lcd_display_string(displayTime, 3, 15)
                            batPercent = self.measure.stateOfCharge(self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL))
                            self.display.lcd_display_string(str(batPercent-10)+"% ",4,13)
                        

                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("BATTERY CHECK",2,3)
                else:
                    batTimeoutFlag = True
                    self.purgeLog.logger('debug','Battery SOC is less than 40%. Mains is off. User must turn on mains and try again.')
                    
            except KeyboardInterrupt:
                batTimeoutFlag = True
                with self.sharedBoolFlags.get_lock():
                    sensorErrorException.sharedBoolFlags[3] = True
            finally:
                if batTimeoutFlag:
                    self.purgeLog.logger('debug','Battery SOC is less than 40%. Mains is off OR, the batteries werent charged enough in 30 minutes. Not enough to proceed.')
                    subjects = "Purgejig bot has a bad message for you!"
                    bodyTexts = ("Dear Purgejig user,\n\n;"
                                "Error 13;Battery voltage is STILL too low;The batteries wont hold through load-shedding, check batteries/charging circuit/mains power. See logs FMI.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    self.__beepOn()
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 13",1, 6)
                        self.display.lcd_display_string("Bat critically low",2, 1)
                        self.display.lcd_display_string("Try again later...",3, 1)
                        self.display.lcd_display_string("Press RESET",4, 4)
                    if self.mail.sendMailAttachment(subjects, bodyTexts):
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 13",1, 6)
                    else:
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 13 & 16",1, 3)
                            self.display.lcd_display_string("Email failed, try",3, 1)
                            self.display.lcd_display_string("again later.",4, 4)
                    raise batteryError()
                else:
                    self.purgeLog.logger('debug','Battery SOC is greater than 40%. The batteries were charged enough before 30 minutes. Proceeding.')
                    subjectss = "Purgejig bot has a good message for you!"
                    bodyTextss = ("Dear Purgejig user,\n\n;"
                                "Error 13 is now resolved!;Please press start on the purge jig to continue purging.;\n\n"
                                "Kind regards,\nPurgejig bot")        
                    self.mail.sendMailAttachment(subjectss, bodyTextss)
        self.batteryStateSet(batteryEnable = 1, chargeEnable=0)
        with self.i2cLock:
            batPercent = self.measure.stateOfCharge(self.measure.readVoltage(self.constant.BATTERYVOLTCHANNEL))
            self.display.lcd_display_string("{}%".format(batPercent),3,8)
        time.sleep(0.75)
        with self.i2cLock:
            self.display.lcd_clear()
        return True

    def waitTimeSync(self):
        # Query the system to see if NTP has synchronized

        #  WARNING: this is a blocking subprocess.

        subprocessInstance = subprocess.Popen(['timedatectl'], stdout=subprocess.PIPE,
                                            universal_newlines=True)
        cmdOut, _error = subprocessInstance.communicate()

        listOfParts = cmdOut.split('\n')
        stringVal = listOfParts[4].strip() # if this bombs out, type "timedatectl" in the terminal as see from there.
        listOfStrings = stringVal.split(":")
        stringVal = listOfStrings[1].strip()

        # Seems unintuitive... check how its used and will make sense.
        if stringVal == "yes":
            return False
        else:
            return True
    
    def checkHealth(self):
        system = checkHealth.healthyPi()
        metrics = system.checkPi()
        with self.i2cLock:
            self.display.lcd_display_string("HEALTH CHECK",2,4)
        # time.sleep(0.75)
        timeSync = False
        # I put this first so the logs make sense if email fails
        time.sleep(1)
        # metrics["Network"] = False
        if metrics["Network"]:
            self.purgeLog.logger('debug', 'RPi network is goood.')
            if self.waitTimeSync():
                self.display.lcd_display_string("TIME SYNCING...",3, 2)
                while self.waitTimeSync():
                    time.sleep(0.5)
                    self.purgeLog.logger('debug', 'waiting for timesync...')

                self.purgeLog.logger('debug', 'Time has sunk!')
                timeSync = True
                self.display.lcd_display_string("               ",3, 2)
            else:
                self.purgeLog.logger('debug', 'Time is synced.')
        else:
            # no point in trying to email here... the network will be restored at some point on its own.
            self.purgeLog.logger('debug', 'RPi network is down!')
        # Check available memory
        # metrics["Memory"] = False
        if metrics["Memory"]:
            self.purgeLog.logger('debug', 'RPi RAM is goood.')
        else:
            self.purgeLog.logger('warning', 'RPi RAM is over-used.')
            self.__beepOn()
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 17",1, 6)
                # self.display.lcd_display_string("                    ",2)
                self.display.lcd_display_string("RAM full",3, 6)
                self.display.lcd_display_string("Purge will cont.",4, 2)
            if self.mail.sendMailAttachment(
                subject = "Purgejig bot has a bad message for you!",
                bodyText = ("Dear Purgejig user,;\n\nError 17;RPi RAM is over-used!. Log in remotely and terminate unneccessary tasks.;\n\nKind regards,\nPurgejig bot")):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 17",1, 6)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 16 & 17",1, 3)
                    self.display.lcd_display_string("Email fail , and",2, 2)

            time.sleep(10)
            self.__beepOff()
            with self.i2cLock:
                self.display.lcd_clear()
                                    
        # Check available storage
        # metrics["Disk"] = False
        if metrics["Disk"]:
            self.purgeLog.logger('debug', 'RPi storage is goood.')
        else:
            self.purgeLog.logger('warning', 'RPi storage is over-used.')
            self.__beepOn()
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 17",1, 6)
                # self.display.lcd_display_string("                    ",2)
                self.display.lcd_display_string("Storage full",3, 4)
                self.display.lcd_display_string("Purge will cont.",4, 2)
            subject = "Purgejig bot has a bad message for you!"
            bodyText = ("Dear Purgejig user,\n\n;"
                        "Error 17;RPi storage is over-used!;Maintanence of the RPi may be required.;\n\n"
                        "Kind regards,\nPurgejig bot")
            if self.mail.sendMailAttachment(subject, bodyText):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 17",1, 6)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 16 & 17",1, 3)
                    self.display.lcd_display_string("Email fail , and",2, 2)
            
            time.sleep(10)
            self.__beepOff()
            with self.i2cLock:
                self.display.lcd_clear()

        # Check logfile
        if self.purgeLog.checkLogFile():
            self.purgeLog.logger('debug', 'Logfile is there and in good order.')
        else:
            # Possibly fruitless. might aswell try
            self.__beepOn()
            self.purgeLog.logger('warning', 'Logfile is not working.')
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 20",1, 6)
                self.display.lcd_display_string("Logging fault",3, 3)
                self.display.lcd_display_string("Purge will cont.",4, 2)
            subject = "Purgejig bot has a bad message for you!"
            bodyText = ("Dear Purgejig user,\n\n;"
                        "Error 20;Log file not found, or accessable!;Maintanence of the RPi may be required.;\n\n"
                        "Kind regards,\nPurgejig bot")
            if self.mail.sendMailAttachment(subject, bodyText):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 20",1, 6)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 16 & 20",1, 3)
                    self.display.lcd_display_string("Email fail , and",2, 2)
            time.sleep(10)
            self.__beepOff()
            with self.i2cLock:
                self.display.lcd_clear()
        with self.i2cLock:
            self.display.lcd_display_string("ALL GOOD",3,6)
        time.sleep(1)

    def __worker(self, input, output):
        for func, args in iter(input.get, 'STOP'):
            result = self.__parse(func, args)
            output.put(result)
    def __parse(self, tunc, args):
        result = tunc(args)
        return '%s says that %s%s is %s' % \
            (current_process().name, tunc.__name__, args, result)
   
    


    def __idle(self):
        """
        Internal method for setting an idle mode
        """
        self.purgeLog.logger('debug',"entered idle")
        GPIO.output(self.enPump, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.ventValve1, 0)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.enStepMotor, 0)
        # GPIO.output(self.enBuzzer, 0)

    def __initiate(self):
        """
        Internal method for opening supply pressure valve
        """
        self.purgeLog.logger('debug',"entered initiate")
        GPIO.output(self.enPump, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.ventValve1, 0)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.enStepMotor, 0)
        # GPIO.output(self.enBuzzer, 0)
        # Allow time for pressure to equalise
        # time.sleep(1)
    def __beepOff(self):
        # self.purgeLog.logger('debug',"beep off")
        GPIO.output(self.enBuzzer, 0)


    def __beepOn(self):
        # self.purgeLog.logger('debug',"beep on")
        GPIO.output(self.enBuzzer, 1)
        self.display.backlight(1)
    
    def toggleBeep(self, state):
        # Allows toggling beep outside of this class
        if state:
            self.__beepOn()
        else:
            self.__beepOff()
            self.display.backlight(0)

    def __emergencyVentClose(self):
        """
        Internal method for closing vent and supply(fill) valves. E-vent.
        """
        self.purgeLog.logger('debug',"entered E-vent")
        GPIO.output(self.enPump, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enBuzzer, 1)
        # time.sleep(5)
        GPIO.output(self.ventValve1, 1)
        GPIO.output(self.ventValve2, 1)
    
    def __emergencyVent(self):
        """
        Internal method for opening vent and supply(fill) valves. E-vent.
        """
        self.purgeLog.logger('debug',"entered E-vent")
        GPIO.output(self.enPump, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.ventValve1, 1)
        GPIO.output(self.ventValve2, 1)
        GPIO.output(self.fillValve, 1)
        GPIO.output(self.enStepMotor, 0)
        GPIO.output(self.enBuzzer, 1)

    def __heFill(self):
        """
        Internal method for setting a fill mode
        """
        self.purgeLog.logger('debug',"entered helium fill")
        GPIO.output(self.enPump, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.ventValve1, 1)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.fillValve, 1)
        GPIO.output(self.enStepMotor, 1)
        # GPIO.output(self.enBuzzer, 0)

    def __heFillExit(self):
        """
        Internal method for exiting hefill
        """
        self.purgeLog.logger('debug',"exited helium fill")
        GPIO.output(self.enPump, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.ventValve1, 0)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.fillValve, 0)
        time.sleep(2)
        GPIO.output(self.enStepMotor, 0)
        # GPIO.output(self.enBuzzer, 0)

    def __vent(self):
        self.purgeLog.logger('debug',"entered vent")
        GPIO.output(self.enPump, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.ventValve1, 1)
        GPIO.output(self.ventValve2, 1)
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.enStepMotor, 0)
        # GPIO.output(self.enBuzzer, 0)

    def __ventExit(self):
        self.purgeLog.logger('debug',"exited vent")
        GPIO.output(self.enPump, 0)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.ventValve1, 0)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.enStepMotor, 0)
        # GPIO.output(self.enBuzzer, 0)
    
    def __vacInit(self):
        self.purgeLog.logger('debug',"entered vacuum initialisation")
        GPIO.output(self.enPump, 1)
        GPIO.output(self.vacValve, 0)
        GPIO.output(self.ventValve1, 0)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.enStepMotor, 0)
        # GPIO.output(self.enBuzzer, 0)

    def __vac(self):
        self.purgeLog.logger('debug',"entered vacuum")
        GPIO.output(self.enPump, 1)
        GPIO.output(self.vacValve, 1)
        GPIO.output(self.ventValve1, 0)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.enStepMotor, 0)
        # GPIO.output(self.enBuzzer, 0)


    def __vacExit(self):
        self.purgeLog.logger('debug',"exited vacuum")

        
        GPIO.output(self.vacValve, 0)
        time.sleep(2)   # This closes the valve before the vacuum pump turns off
                        # reducing the chance of contamination
        GPIO.output(self.enPump, 0)
        GPIO.output(self.ventValve1, 0)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.enStepMotor, 0)
        # GPIO.output(self.enBuzzer, 0)
    
    # Take note that this is not a set of char being passed into
    # this decorator. It is an attribute of purgeModes class.
    # See __init__ for self.venttimeout
    @customDecorator.customDecorators.exitAfter('venttimeout')
    def __ventProcess(self):
        
        # self.state = "vent"
        with self.state.get_lock():
            self.state[0] = 1
        ventType = 'None'
        try:
            # Venting process
            with self.i2cLock:
                ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            with self.i2cLock:
                self.display.lcd_display_string("Venting", 2, 4)
                self.display.lcd_display_string("P2={:5.2f} bar ".format(round(ventPressure,2)), 3, 4)
            if (ventPressure < -0.1) and self.stopFlag == 0 and self.resetFlag == 0:
                # Insert error here
                ventType = 'Vacuum'
            elif (ventPressure >= self.constant.VENTPRESSURE) and self.stopFlag == 0 and self.resetFlag == 0:
                ventType = 'Pressurised'
            self.__vent()
            while ventPressure >= self.constant.VENTPRESSURE or ventPressure < -0.05:
                with self.i2cLock:
                    ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                    self.display.lcd_display_string("{:5.2f}".format(round(ventPressure,2)), 3,7)

                with self.sharedBoolFlags.get_lock():
                    self.stopFlag = self.sharedBoolFlags[1]
                if self.stopFlag:
                    self.purgeLog.logger('debug', 'Emergency stop flag. Exiting from vent.')
                    break
                    # raise pins.emergencyStopException() # this is a hack. Fix later
        except KeyboardInterrupt:
        
            # self.stopFlag = True
            self.timeoutFlag = True
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = True
                # self.errorFlag = True
            self.__ventExit()
        except Exception as e:
            print(e)
            self.purgeLog.logger('error', 'Error vent:{}'.format(e))
            time.sleep(10)

        finally:
            if self.timeoutFlag:
                self.__idle()
                self.purgeLog.logger('error', 'Vent timeout errror!')
                with self.i2cLock:
                    self.display.lcd_clear()
                subject = "Purgejig bot has a bad message for you!"
                if ventType == 'Pressurised':
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 8", 1, 6)
                        self.display.lcd_display_string("Vent timeout",2, 4)
                        self.display.lcd_display_string("Press RESET",4, 4)
                    bodyText = ("Dear Purgejig user,\n\n;"
                                "Error 8;Vent stage timeout;The vent stage took too long, there may be leaks or other errros. See logs FMI.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    if self.mail.sendMailAttachment(subject, bodyText):
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 8",1, 6)
                    else:
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 8 & 16",1, 3)
                            self.display.lcd_display_string("Email failed",2, 4)
                elif ventType == 'Vacuum':
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 3",1, 6)
                        self.display.lcd_display_string("Vent timeout",2, 4)
                        self.display.lcd_display_string("Sensor 2 fault",3, 3)
                        self.display.lcd_display_string("Press RESET",4, 4)
                    bodyText = ("Dear Purgejig user,\n\n;"
                                "Error 3;Vent stage timeout;The vent stage took too long, there may be leaks or vent sensor failure. See logs FMI.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    if self.mail.sendMailAttachment(subject, bodyText):
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 3",1, 6)
                    else:
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 3 & 16",1, 3)
                else:
                    bodyText = ("Dear Purgejig user,\n\n;"
                                "Unknown error code;Vent stage timeout;See logs FMI.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    if self.mail.sendMailAttachment(subject, bodyText):
                        with self.i2cLock:
                            self.display.lcd_display_string("Error unknown",1, 4)
                            self.display.lcd_display_string("Vent timeout",2, 4)
                            self.display.lcd_display_string("Press RESET",4, 4)
                    else:
                        with self.i2cLock:
                            self.display.lcd_display_string("Error unknown & 16",1, 1)
                            self.display.lcd_display_string("Vent timeout",2, 4)
                            self.display.lcd_display_string("Email failed",3, 4)
                            self.display.lcd_display_string("Press RESET",4, 4)
                raise timeOutError()
            else:
                self.__ventExit()
                with self.i2cLock:
                    # self.display.lcd_display_string("                    ", 2)
                    self.display.lcd_display_string("                    ", 3)
                
    @customDecorator.customDecorators.exitAfter('initialvactimeout')
    def __initVacProcess(self):
        # self.state = "initvacuum"
        with self.state.get_lock():
            self.state[0] = 3
        with self.i2cLock:
            ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
        if ventPressure > 0.5:
            self.__idle()
            self.purgeLog.logger('error', 'Manifold pressure too high to vacuum.')
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 19",1, 6)
                self.display.lcd_display_string("Vent failure",2, 4)
                self.display.lcd_display_string("Press RESET",4, 4)
            subject = "Purgejig bot has a bad message for you!"
            bodyText = ("Dear Purgejig user,\n\n;"
                        "Error 19;Initial vacuum stage failure;The Vent stage failed to properly vent, vacuum cant continue. See logs FMI.;\n\n"
                        "Kind regards,\nPurgejig bot")
            if self.mail.sendMailAttachment(subject, bodyText):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 19",1, 6)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 19 & 16",1, 3)
                    self.display.lcd_display_string("Email failed",3, 4)

            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = True
            raise overPressureException()
        else:
            try:
                with self.i2cLock:
                    self.display.lcd_display_string("Vacuum ", 2, 4)
                    self.display.lcd_display_string("mbar",3,13)
                self.__vacInit()
                with self.i2cLock:
                    vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                    self.display.lcd_display_string("{:.2e}".format(vacuumPressure),3,4)

                # Check for 10 seconds
                sleepTime = 0.2
                totalTime = 15
                initcount = 0
                while initcount < (totalTime/sleepTime):
                    with self.i2cLock:
                        vacuumPressuredPdt = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                        self.display.lcd_display_string("{:.2e}".format(vacuumPressuredPdt),3,4)
                    time.sleep(sleepTime)
                    initcount += 1

                if vacuumPressure >= vacuumPressuredPdt:
                    while vacuumPressure >= self.constant.INITVACUUMPRESSURE:
                        with self.i2cLock:
                            vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                        with self.i2cLock:
                            self.display.lcd_display_string("{:.2e}".format(vacuumPressure),3,4)

                        with self.sharedBoolFlags.get_lock():
                            self.stopFlag = self.sharedBoolFlags[1]
                        if self.stopFlag:
                            self.purgeLog.logger('debug', 'Emergency stop flag. Exiting from initial vacuum.')
                            break
                            # raise pins.emergencyStopException()
                else:
                    self.purgeLog.logger('error', 'Vacuum pump not detected')
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 9",1, 6)
                        self.display.lcd_display_string("Vacuum pump not",2, 2)
                        self.display.lcd_display_string("detected",3, 6)
                        self.display.lcd_display_string("Press RESET",4, 4)
                    subject = "Purgejig bot has a bad message for you!"
                    bodyText = ("Dear Purgejig user,\n\n;"
                                "Error 9;Vacuum pump not detected;The vacuum stage failed due to no load, check if vacuum pump is connected and on, else check vac sensor. See logs FMI.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    if self.mail.sendMailAttachment(subject, bodyText):
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 9",1, 6)
                    else:
                        with self.i2cLock:
                            self.display.lcd_clear()
                            self.display.lcd_display_string("Error 9 & 16",1, 3)
                            self.display.lcd_display_string("detected, Email fail",3)
                    
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[3] = True
                    # self.errorFlag = True
                    self.__vacExit()
                    self.vacexception = True

            except KeyboardInterrupt:
                self.timeoutFlag = True
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.stopFlag = True
                self.__vacExit()
            except Exception as g:
                print(g)
                self.purgeLog.logger('error', 'Error vacini: {}'.format(g))
            finally:
                with self.sharedBoolFlags.get_lock():
                    self.errorFlag = self.sharedBoolFlags[3]
                if self.timeoutFlag:
                    self.__idle()
                    self.purgeLog.logger('error', 'Initialising vacuum timeout errror!')
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 5",1, 6)
                        self.display.lcd_display_string("Initial vac timeout",2)
                        self.display.lcd_display_string("Press RESET",4, 4)
                    subject = "Purgejig bot has a bad message for you!"
                    bodyText = ("Dear Purgejig user,\n\n;"
                                "Error 5;Inital vacuum stage timeout;The inital vacuum generation timed out, vacuum cant continue. See logs FMI.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    if self.mail.sendMailAttachment(subject, bodyText):
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 5",1, 6)
                    else:
                        with self.i2cLock:
                            self.display.lcd_display_string("Error 5 & 16",1, 3)
                            self.display.lcd_display_string("Email failed",3, 4)
                    # self.errorFlag = True
                    raise timeOutError()
                elif self.vacexception:
                    raise vacuumException()
                elif self.stopFlag:
                    pass
                elif self.errorFlag:
                    pass
                else:
                    pass
                    # self.__vacExit()
                    # with self.i2cLock:
                    #     self.display.lcd_display_string("                    ", 2)
                    #     self.display.lcd_display_string("                    ", 3)
    
    def dPdt(self, p1, p2, deltaTime):
        return (p1-p2)/deltaTime

    def timerFunc(self, timer, initValues, userNotified = False):
        with self.state.get_lock():
            sstate = self.state[0]

        if sstate == 4: # incase the is_alive time.cancel doesnt work
            with self.i2cLock:
                p2 = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
            deltaTime = time.monotonic() - initValues[0]

            self.purgeLog.logger('debug', 'Pressure 1: {}'.format(initValues[1]))
            self.purgeLog.logger('debug', 'Pressure 2: {}'.format(p2))

            dPdt = self.dPdt(initValues[1], p2, deltaTime)
            self.purgeLog.logger('debug', 'dP/dt is: {}'.format(dPdt))
            if dPdt > float(self.acceptabledPdt):
                self.purgeLog.logger('debug', 'Vacuum dP/dt good.')
                userNotified = False
                with self.i2cLock:
                    self.display.lcd_display_string("dP/dt is fine",4, 4)
            else:
                self.purgeLog.logger('warning', 'Vacuum dP/dt bad. Vacuum not dropping')
                with self.i2cLock:
                    self.display.lcd_display_string("dP/dt is bad ",4, 4)
                if userNotified:
                    pass
                else:
                    #NOTIFY USER
                    subject = "Purgejig bot has a bad message for you!"
                    bodyText = ("Dear Purgejig user,\n\n;"
                                "Warning;The vacuum dP/dt is low;Timeout error may kick in, and the purge would have to be restarted. See logs FMI.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    if self.mail.sendMailAttachment(subject, bodyText):
                        # Send 1 email. Instead of spamming every 10 mins (or whatever time we set for dPdt)
                        userNotified = True
                    else:
                        userNotified = False

            initValues[0] = time.monotonic()
            initValues[1] = p2            

            self.timer = threading.Timer(int(self.dPdtTime), self.timerFunc, args=(self.timer, initValues, userNotified))
            self.timer.start()

            
    @customDecorator.customDecorators.exitAfter('vacuumtimeout')
    def __vacProcess(self):
        # self.state = "vacuum"
        with self.state.get_lock():
            self.state[0] = 4
        try:
            # Vacuum process
            with self.i2cLock:
                fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")

            if (fillPressure >= self.constant.SAFETOVACUUM) and self.stopFlag == 0 and self.resetFlag == 0:
# Remember to change the error class to a suitable vacuum name and also display what needs to be displayed
                self.purgeLog.logger('error', 'Manifold pressure too high to open to vac')
                subject = "Purgejig bot has a bad message for you!"
                bodyText = ("Dear Purgejig user,\n\n;"
                            "Error 19;Vacuum stage failure;The Vent stage failed to properly vent, vacuum cant continue. See logs FMI.;\n\n"
                            "Kind regards,\nPurgejig bot")
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 19",1, 6)
                    self.display.lcd_display_string("Vent failure",2, 4)
                    self.display.lcd_display_string("Press RESET",4, 4)
                if self.mail.sendMailAttachment(subject, bodyText):
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 19",1,6)
                else:
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 19 & 16",1,3)
                        self.display.lcd_display_string("Email failed",3)
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                    # self.errorFlag = True
                self.__vacExit()
                raise overPressureException()
            else:
                with self.i2cLock:
                    # self.display.lcd_display_string("Vacuum", 2, 4)
                    vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                    self.display.lcd_display_string("{:.2e} mbar".format(vacuumPressure),3, 4)
                time.sleep(1)
                self.__vac()
                with self.i2cLock:
                    vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                    self.display.lcd_display_string("{:.2e} mbar".format(vacuumPressure),3, 4)
                time.sleep(0.5)
                with self.i2cLock:
                    vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                    self.display.lcd_display_string("{:.2e} mbar".format(vacuumPressure),3, 4)
            
            # with self.i2cLock:
            #     vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
            with self.i2cLock:
                fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            if (vacuumPressure >= self.constant.INITVACUUMPRESSURE) or (fillPressure < 1 and fillPressure > -1) and self.stopFlag == 0 and self.resetFlag == 0:
                initValues = [time.monotonic(), vacuumPressure]
                self.timer = threading.Timer(int(self.dPdtTime), self.timerFunc, args=(None, initValues, False))
                self.timer.start()
                while vacuumPressure >= self.constant.VACUUMPRESSURE:
                    with self.i2cLock:
                        vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                        self.display.lcd_display_string("{:.2e}".format(vacuumPressure),3,4)
                    with self.sharedBoolFlags.get_lock():
                        self.stopFlag = self.sharedBoolFlags[1]
                    if self.stopFlag:
                        self.purgeLog.logger('debug', 'Emergency stop flag. Exiting from vacuum.')
                        break
                        # raise pins.emergencyStopException() # this is a hack. fix later
                
                if self.timer.is_alive():
                    self.purgeLog.logger('debug','Killing Vacuum dP/dt timer.')
                    self.timer.cancel()
            else:
# Remember to change the error class to a suitable vacuum name and also display what needs to be displayed
                self.purgeLog.logger('error', 'Vacuum load not detected. The pressure did not increase when solenoid opened!')
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 9",1, 6)
                    self.display.lcd_display_string("Vacuum load not",2, 2)
                    self.display.lcd_display_string("detected",3, 6)
                    self.display.lcd_display_string("Press RESET",4, 4)
                subject = "Purgejig bot has a bad message for you!"
                bodyText = ("Dear Purgejig user,\n\n;"
                            "Error 9;Vacuum load not detected;The vacuum stage failed due to no load, check if vacuum pump is connected, else check vac sensor. See logs FMI.;\n\n"
                            "Kind regards,\nPurgejig bot")
                if self.mail.sendMailAttachment(subject, bodyText):
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 9",1, 6)
                else:
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 9 & 16",1, 3)
                        self.display.lcd_display_string("detected, Email fail",3)
                
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                self.__vacExit()
                self.vacexception = True
                

        except KeyboardInterrupt:
            self.timeoutFlag = True
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = True
            self.__vacExit()
        except Exception as g:
            print(g)
            self.purgeLog.logger('error', 'Error vac: {}'.format(g))
        finally:
            with self.sharedBoolFlags.get_lock():
                self.errorFlag = self.sharedBoolFlags[3]
            if self.timeoutFlag:
                self.__idle()
                self.purgeLog.logger('error', 'Vacuum timeout errror!')
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 21",1, 6)
                    self.display.lcd_display_string("Vacuum timeout",2, 3)
                    self.display.lcd_display_string("Press RESET",4, 4)
                subject = "Purgejig bot has a bad message for you!"
                bodyText = ("Dear Purgejig user,\n\n;"
                            "Error 21;Vacuum timeout reached;The vacuum stage took too long, there is a leak or purge component is very dirty. See logs FMI.;\n\n"
                            "Kind regards,\nPurgejig bot")
                if self.mail.sendMailAttachment(subject, bodyText):
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 21",1, 6)
                else:
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 21 & 16",1, 3)
                        self.display.lcd_display_string("Email failed!",3, 4)
                raise timeOutError()

            elif self.vacexception:
                raise vacuumException()
            elif self.stopFlag:
                pass
            elif self.errorFlag:
                self.__vacExit()
            else:
                self.__vacExit()
                with self.i2cLock:
                    # self.display.lcd_display_string("                    ", 2)
                    self.display.lcd_display_string("                    ", 4)
    

    @customDecorator.customDecorators.exitAfter('filltimeout')
    def __fillProcess(self):
        # self.state = "fill"
        with self.state.get_lock():
            self.state[0] = 2
        # Check if supply pressure is safe to apply
        try:
            self.__initiate()
            with self.sharedValues.get_lock():
                cycleCount = self.sharedValues[4]
            with self.i2cLock:
                supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            with self.sharedValues.get_lock():
                supplyPressure = self.sharedValues[0]
            if (supplyPressure >= self.constant.PROOFPRESSURE):
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                self.overPressureFlag = True
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[5] = self.overPressureFlag
                # raise overPressureException()
            
            elif (supplyPressure < self.constant.MAXSUPPLYPRESSURE):
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 22",1, 6)
                    self.display.lcd_display_string("Supply underpressure",3)
                    self.display.lcd_display_string("Please fix!", 4, 4)
                self.__beepOn()
                # subject = "Purgejig bot has a bad message for you!"
                # bodyText = ("Dear Purgejig user,\n\n;"
                #             "Error 22;Supply under-pressure;The supply pressure has dropped below the last fill pressure (16 bar)."
                #             "Purge will continue til the last cycle then wait for the correct pressure. See logs FMI.;\n\n"
                #             "Kind regards,\nPurgejig bot")
                # if self.mail.sendMailAttachment(subject, bodyText):
                #     with self.i2cLock:
                #         self.display.lcd_display_string("Error 22",1)
                # else:
                #     with self.i2cLock:
                #         self.display.lcd_display_string("Error 22 & 16",1)
                if self.lastCycleFlag:
                    pass
                else:
                    time.sleep(10)
                    self.__beepOff()
                with self.i2cLock:
                    self.display.lcd_clear()
            else:
                self.purgeLog.logger('debug',"The supply pressure is within bounds")
            # Check whether it is the last cycle, if it is, fill to 16 bar rather
            if self.lastCycleFlag:
                # Helium fill process
                if (supplyPressure >= self.constant.LASTFILLPRESSURE and supplyPressure < self.constant.PROOFPRESSURE) and self.stopFlag == 0:
                    self.purgeLog.logger('debug',"The supply pressure is greater than 16bar for last fill")
                    self.__heFill()
                    with self.i2cLock:
                        # self.display.lcd_clear()
                        self.display.lcd_display_string("Filling", 2, 4)
                        self.display.lcd_display_string("%d/%d"%((self.noOfCycles+1), cycleCount), 2, 13)
                        self.display.lcd_display_string("P1={:5.2f} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 4)
                        self.display.lcd_display_string("P2={:5.2f} bar".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 4)

                    while (fillPressure <= self.constant.MAXLOWGAUGE) or (supplyPressure <= self.constant.LASTFILLPRESSURE):
                        with self.sharedValues.get_lock():
                            supplyPressure = self.sharedValues[0]
                        with self.i2cLock:
                            # supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                            fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                            self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                            self.display.lcd_display_string("{:5.2f}".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.overPressureFlag = True
                            # raise overPressureException()
                        elif self.stopFlag:
                            self.purgeLog.logger('debug', 'Emergency stop flag. Exiting')
                            break
                            # raise pins.emergencyStopException() # this is a hack. fix later
                    # time.sleep(5)
                else:
                    self.purgeLog.logger('debug',"The supply pressure is less than 16bar for last fill")
                    self.__beepOn()
                    with self.sharedValues.get_lock():
                        supplyPressure = self.sharedValues[0]
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 22",1, 6)
                        self.display.lcd_display_string("Supply underpressure",2)
                        self.display.lcd_display_string("Please fix!", 4, 4)
                        self.display.lcd_display_string("P1={:5.2f} bar".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 4)
                    # subject = "Purgejig bot has a bad message for you!"
                    # bodyText = ("Dear Purgejig user,\n\n;"
                    #             "Error 22;Supply Pressure too low;Please increase the supply pressure, see logs FMI.;\n\n"
                    #             "Kind regards,\nPurgejig bot")
                    # if self.mail.sendMailAttachment(subject, bodyText):
                    #     with self.i2cLock:
                    #         self.display.lcd_display_string("Error 22",1)
                    # else:
                    #     with self.i2cLock:
                    #         self.display.lcd_display_string("Error 22 & 16",1)

                    with self.sharedValues.get_lock():
                        supplyPressure = self.sharedValues[0]
                    while supplyPressure < self.constant.LASTFILLPRESSURE:
                        with self.sharedValues.get_lock():
                            supplyPressure = self.sharedValues[0]
                        with self.i2cLock:
                            self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)

                    self.__beepOff()
                    self.__heFill()
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Filling", 2, 4)
                        self.display.lcd_display_string("%d/%d"%((self.noOfCycles+1), cycleCount), 2, 13)
                        self.display.lcd_display_string("P1={:5.2f} bar".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 4)
                        self.display.lcd_display_string("P2={:5.2f} bar".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 4)

                    while (fillPressure <= self.constant.MAXLOWGAUGE) or (supplyPressure <= self.constant.LASTFILLPRESSURE) and self.stopFlag == 0:
                        with self.sharedValues.get_lock():
                            supplyPressure = self.sharedValues[0]
                        with self.i2cLock:
                            # supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                            fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                            self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                            self.display.lcd_display_string("{:5.2f}".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.overPressureFlag = True
                            # raise faultErrorException()
                        elif self.stopFlag:
                            self.purgeLog.logger('debug', 'Emergency stop flag. Exiting')
                            break
                            # raise pins.emergencyStopException() # this is a hack. fix later
                    # time.sleep(5)
            else:
                # Helium fill process
                self.purgeLog.logger('debug', 'Not the last fill cycle')
                if supplyPressure > self.constant.FILLPRESSURE:
                    if fillPressure <= self.constant.FILLPRESSURE and self.stopFlag == 0:
                        self.__heFill()
                        with self.i2cLock:
                            self.display.lcd_display_string("Filling", 2, 4)
                            self.display.lcd_display_string("%d/%d"%((self.noOfCycles+1), cycleCount), 2, 13)
                            self.display.lcd_display_string("P1={:5.2f} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 4)
                            self.display.lcd_display_string("P2={:5.2f} bar".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 4)
                    while fillPressure <= self.constant.FILLPRESSURE:
                        with self.sharedValues.get_lock():
                            supplyPressure = self.sharedValues[0]
                        with self.i2cLock:
                            # supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                            fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                            self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                            self.display.lcd_display_string("{:5.2f}".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.overPressureFlag = True                       
                            # raise overPressureException()
                        elif self.stopFlag:
                            self.purgeLog.logger('debug', 'Emergency stop flag. Exiting')
                            break
                            # raise pins.emergencyStopException() # this is a hack. fix later
                    
                else:
                    self.purgeLog.logger('debug',"The supply pressure is less than 4bar for normal fill")
                    self.__beepOn()
                    with self.sharedValues.get_lock():
                        supplyPressure = self.sharedValues[0]
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 22",1, 6)
                        self.display.lcd_display_string("Supply underpressure",2)
                        self.display.lcd_display_string("Please fix!", 4, 4)
                        self.display.lcd_display_string("P1={:5.2f} bar".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 4)
                    # subject = "Purgejig bot has a bad message for you!"
                    # bodyText = ("Dear Purgejig user,\n\n;"
                    #             "Error 22;Supply Pressure too low;Supply pressure is too low to continue, Correct supply pressure ASAP!, see logs FMI.;\n\n"
                    #             "Kind regards,\nPurgejig bot")
                    # if self.mail.sendMailAttachment(subject, bodyText):
                    #     with self.i2cLock:
                    #         self.display.lcd_display_string("Error 22",1)
                    # else:
                    #     with self.i2cLock:
                    #         self.display.lcd_display_string("Error 22 & 16",1)

                    with self.sharedValues.get_lock():
                        supplyPressure = self.sharedValues[0]
                    while supplyPressure < self.constant.LASTFILLPRESSURE:
                        with self.sharedValues.get_lock():
                            supplyPressure = self.sharedValues[0]
                        with self.i2cLock:
                            self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)

                    self.__beepOff()
                    self.__heFill()
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Filling", 2, 4)
                        fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                        self.display.lcd_display_string("%d/%d"%((self.noOfCycles+1), cycleCount), 2, 13)
                        self.display.lcd_display_string("P1={:5.2f} bar".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 4)
                        self.display.lcd_display_string("P2={:5.2f} bar".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 4)

                    while (fillPressure <= self.constant.FILLPRESSURE) and self.stopFlag == 0:
                        with self.sharedValues.get_lock():
                            supplyPressure = self.sharedValues[0]
                        with self.i2cLock:
                            # supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                            fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                            self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                            self.display.lcd_display_string("{:5.2f}".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.overPressureFlag = True
                            # raise faultErrorException()
                        elif self.stopFlag:
                            self.purgeLog.logger('debug', 'Emergency stop flag. Exiting')
                            break
                            # raise pins.emergencyStopException() # this is a hack. fix later
                    

        except KeyboardInterrupt:
            self.timeoutFlag = True
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = True
            self.__heFillExit()
        except Exception as g:
            print(g)
            self.purgeLog.logger('error', 'Error fill: {}'.format(g))
        finally:
            with self.sharedBoolFlags.get_lock():
                self.errorFlag = self.sharedBoolFlags[3]
            if self.timeoutFlag:
                self.__idle()
                self.purgeLog.logger('error', 'Fill timeout errror!')
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 7",1, 6)
                    self.display.lcd_display_string("Fill timeout",2, 4)
                    self.display.lcd_display_string("Press RESET",4, 4)
                subject = "Purgejig bot has a bad message for you!"
                bodyText = ("Dear Purgejig user,\n\n;"
                            "Error 7;Helium fill timeout reached;The fill stage took too long, there could be a leak or the supply solenoid valve/relay broke. See logs FMI.;\n\n"
                            "Kind regards,\nPurgejig bot")
                if self.mail.sendMailAttachment(subject, bodyText):
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 7",1, 6)
                else:
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 7 & 16",1, 3)
                        self.display.lcd_display_string("Email failed",3, 4)
                raise timeOutError()
            elif self.overPressureFlag:
                # self.__idle()
                self.purgeLog.logger('error', 'Supply over pressure error!')
                # The seperate parallel process will handle this
                # with self.i2cLock:
                #     self.display.lcd_clear()
                #     self.display.lcd_display_string("Error 10:",1)
                #     self.display.lcd_display_string("Supply overpressure",2)
                #     self.display.lcd_display_string("Press Reset",4)

            elif self.stopFlag:
                pass
            elif self.errorFlag:
                pass
            else:
                # MAKE SURE TO ADD A CHECK FOR WHEN LOW GAUGE == HIGH GAUGE
                self.__heFillExit()
                with self.i2cLock:
                    self.display.lcd_display_string("                    ", 2)
                    self.display.lcd_display_string("                    ", 3)
                    self.display.lcd_display_string("                    ", 4)
                self.overPressureFlag = False

    def __stateMachine(self):
        """Add in provision to check for stopFlag and resetFlag"""
        with self.i2cLock:
            self.display.lcd_clear()
        # Operate only untill the desired number of cycles are complete
        with self.sharedBoolFlags.get_lock():
            self.errorFlag = self.sharedBoolFlags[3]
        with self.sharedValues.get_lock():
            cycleCount = self.sharedValues[4]

        while (self.noOfCycles < cycleCount) and (self.errorFlag == False):
            self.__idle()
            # time.sleep(1)
            # Check if it is the last cycle to be run
            if (self.noOfCycles) == (cycleCount - 1):
                self.purgeLog.logger('debug','Last cycle flag set True')
                self.lastCycleFlag = True
            else:
                self.lastCycleFlag = False
            
            with self.i2cLock:
                self.display.lcd_display_string("%d/%d"%((self.noOfCycles+1), cycleCount), 2, 13)
            
            self.__ventProcess()
            time.sleep(1)
            self.__initVacProcess()

            self.__vacProcess()
    
            self.__fillProcess()
            time.sleep(1)

            # Increment cycle count
            self.noOfCycles += 1

            with self.sharedBoolFlags.get_lock():
                self.errorFlag = self.sharedBoolFlags[3]
           
    
    def stateChecks(self):
        self.__initiate()

# Display once to save processing time
        with self.i2cLock:
            self.display.lcd_clear()
            self.display.lcd_display_string("Purging Cycles: ", 1, 1)
            self.display.lcd_display_string("Press START", 4, 4)

        with self.i2cLock:
            supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            self.display.lcd_display_string("P1={:5.2f} bar".format(round(supplyPressure,2)), 2, 4)
            self.display.lcd_display_string("P2={:5.2f} bar".format(round(ventPressure,2)), 3, 4)
# ____________User input_______________________________
        with self.sharedBoolFlags.get_lock():
            self.startFlag = self.sharedBoolFlags[0]
            cycleCount = self.sharedValues[4]
        while (self.startFlag == 0 and self.resetFlag == 0) and (self.stopFlag == 0):
            with self.i2cLock:
                with self.sharedBoolFlags.get_lock():
                    cycleCount = self.sharedValues[4]
                self.display.lcd_display_string("%d  "%cycleCount, 1, 17)
                supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")

            # This is the implementation of the emergency vent
            if supplyPressure >= self.constant.EMERGENCYVENTPRESSURE:
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                self.__emergencyVent()
                self.overPressureFlag = True
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[5] = self.overPressureFlag
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 10", 1, 6)
                    self.display.lcd_display_string("Supply overpressure!", 2)
                    self.display.lcd_display_string("P1={:5.2f} bar".format(round(supplyPressure,2)), 3, 4)
                    self.display.lcd_display_string("Lower supply", 4, 4)
                
                subject = "Purgejig bot has a bad message for you!"
                bodyText = ("Dear Purgejig user,\n\n;"
                            "Error 10;Supply over-pressure occured;The Emergency vent state is active. Lower supply immediatelty. See logs FMI.;\n\n"
                            "Kind regards,\nPurgejig bot")
                parallelMail = Process(target=self.mail.sendMailAttachment, args=(subject, bodyText,))
                parallelMail.start()
                # if self.mail.sendMailAttachment(subject, bodyText):
                #     pass
                # else:
                #     with self.i2cLock:
                #         self.display.lcd_display_string("                    ", 1)
                #         self.display.lcd_display_string("Error 10 & 16", 1, 4)
                while supplyPressure >= 1:
                    with self.i2cLock:
                        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                
                self.__emergencyVentClose()
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Supply P fixed", 1, 3)
                    self.display.lcd_display_string("P2={:5.2f} bar".format(round(ventPressure,2)), 3, 4)
                    self.display.lcd_display_string("Venting manifold", 4, 2)
                    ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                while ventPressure >= 1:
                    with self.i2cLock:
                        ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                        self.display.lcd_display_string("{:5.2f}".format(round(ventPressure,2)), 3, 7)
                
                self.__idle()
                self.__beepOff()
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = False
                
                # self.errorFlag = False


                # if self.startFlag == 1:
                #     self.purgeLog.logger('debug', 'Start was pressed during e-vent')
                #     self.startFlag = 0
                #     self.startAddCallbacks()
                # else:
                #     self.purgeLog.logger('debug', 'Start wasnt pressed during e-vent')
                #     pass
                # ____________________Add something to look for start and cycle press___________________________________________
                
                # pins.logicPins.startAddCallbacks()
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Purging Cycles: ", 1, 1)
                    self.display.lcd_display_string("Press START", 4, 4)
                    ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                    supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    self.display.lcd_display_string("P1={:5.2f} bar".format(round(supplyPressure,2)), 2, 4)
                    self.display.lcd_display_string("P2={:5.2f} bar".format(round(ventPressure,2)), 3, 4)
                self.overPressureFlag = False
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[5] = self.overPressureFlag
                parallelMail.join()
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), 2, 7)
                    self.display.lcd_display_string("{:5.2f}".format(round(ventPressure,2)), 3, 7)
            with self.sharedBoolFlags.get_lock():
                self.startFlag = self.sharedBoolFlags[0]

        time.sleep(0.1)
        with self.i2cLock:
            self.display.lcd_clear()

        # This is here to catch the code from running away on a thread by itself and continuing dangerously
        while self.resetFlag == 1 or self.stopFlag == 1:
            # print("Halted")
            time.sleep(0.2)
#____________________________Check sensors____________________________________________________ 
        self.__checkSensors()

    
        return True

    def __checkSensors(self):
        with self.i2cLock:
            supplyPressure = supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")

        if (supplyPressure < self.constant.MAXSUPPLYPRESSURE) or (ventPressure < -2):

            if supplyPressure < self.constant.SUPPLYBROKEN and ventPressure < self.constant.VENTBROKEN:
                self.purgeLog.logger('error', 'Sensor 1 and 2 no signal, likely power supply off.')
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 2 & 4",1, 4)
                    self.display.lcd_display_string("P1 & P2 sensors not",2)
                    self.display.lcd_display_string("detected",3, 6)
                    self.display.lcd_display_string("Press RESET",4, 4)
                subject = "Purgejig bot has a bad message for you!"
                bodyText = ("Dear Purgejig user,\n\n;"
                            "Error 2 & 4;Pressure sensor 1 and sensor 2 not detected;Supply and manifold/vent pressure sensors are broken or no power delivered. See logs FMI.;\n\n"
                            "Kind regards,\nPurgejig bot")
                if self.mail.sendMailAttachment(subject, bodyText):
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 2 & 4",1, 4)
                else:
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 2, 4, 16",1, 3)
                        # self.display.lcd_display_string("found, Email failed",3)
                raise sensorErrorException()
            elif supplyPressure < self.constant.SUPPLYBROKEN and ventPressure > self.constant.VENTBROKEN:
                self.purgeLog.logger('error', 'Pressure sensor 1 no signal. Likely broken.')
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 2",1, 6)
                    self.display.lcd_display_string("Sensor P1 not",2, 3)
                    self.display.lcd_display_string("detected",3, 6)
                    self.display.lcd_display_string("Press RESET", 4, 4)
                subject = "Purgejig bot has a bad message for you!"
                bodyText = ("Dear Purgejig user,\n\n;"
                            "Error 2;Pressure sensor 1 not detected;The supply pressure sensor is broken or has no power, please check. See logs FMI.;\n\n"
                            "Kind regards,\nPurgejig bot")
                if self.mail.sendMailAttachment(subject, bodyText):
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 2",1, 6)
                else:
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 2 & 16",1, 4)
                        # self.display.lcd_display_string("Email failed",3, 4)
                raise sensorErrorException()
            elif supplyPressure > self.constant.SUPPLYBROKEN and ventPressure < self.constant.VENTBROKEN:
                self.purgeLog.logger('error', 'Pressure sensor 2 no signal. Likely broken.')
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 4",1, 6)
                    self.display.lcd_display_string("Sensor P2 not",2, 3)
                    self.display.lcd_display_string("detected",3, 6)
                    self.display.lcd_display_string("Press RESET",4, 4)
                subject = "Purgejig bot has a bad message for you!"
                bodyText = ("Dear Purgejig user,\n\n;"
                            "Error 4;Pressure sensor 2 not detected;The manifold/vent pressure sensor is broken or has no power, please check. See logs FMI.;\n\n"
                            "Kind regards,\nPurgejig bot")
                if self.mail.sendMailAttachment(subject, bodyText):
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 4",1, 6)
                else:
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 4 & 16",1, 4)
                        # self.display.lcd_display_string("Email failed",3, 4)
                raise sensorErrorException()

            elif supplyPressure > self.constant.SUPPLYBROKEN and supplyPressure < 1:
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                self.errorFlag = True

                self.purgeLog.logger('error', 'The supply is not connected. Allowing user to fix it')
                # time.sleep(0.3)
                self.__beepOn()
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 1 ",1, 6)
                    supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    self.display.lcd_display_string("P1={:5.2f} bar ".format(round(supplyPressure,2)), 2, 4)
                    self.display.lcd_display_string("No supply connected",3)
                    self.display.lcd_display_string("Please fix!", 4, 4)
                subject = "Purgejig bot has a bad message for you!"
                bodyText = ("Dear Purgejig user,\n\n;"
                            "Error 1;Helium supply is not connected;Please attach a He supply, see logs FMI.;\n\n"
                            "Kind regards,\nPurgejig bot")
                if self.mail.sendMailAttachment(subject, bodyText):
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 1 ",1, 6)
                else:
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 1 & 16",1, 4)
                if self.stopFlag:
                    with self.i2cLock:
                        self.display.lcd_display_string("Press RESET", 3, 4)
                    self.stopFlag = False
                

                while (supplyPressure <= self.constant.MAXSUPPLYPRESSURE):
                    with self.i2cLock:
                        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), 2, 7)

                    with self.sharedBoolFlags.get_lock():
                        self.stopFlag = self.sharedBoolFlags[1]
                        self.resetFlag = self.sharedBoolFlags[2]

                    if self.stopFlag or self.resetFlag:
                        break

                if self.stopFlag:
                    raise pins.emergencyStopException    
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = False

                self.__beepOff()

                time.sleep(1)
                with self.i2cLock:
                    supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                if (supplyPressure >= self.constant.PROOFPRESSURE) or (supplyPressure <= self.constant.MAXSUPPLYPRESSURE):
                    self.purgeLog.logger('error', 'The supply pressure is out of bounds. User failed to fix it')
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[3] = True
                    # self.errorFlag = True
                    return False
                else:
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[3] = False
                    # self.errorFlag = False
                    self.purgeLog.logger('warning', 'The no supply was connected. User succeeded to fix it')
                    subject = "Purgejig bot has a good message for you!"
                    bodyText = ("Dear Purgejig user,\n\n;"
                                "Error 1 resolved!;Helium supply has since been detected, purge will carry on as normal.;\n\n"
                                "Kind regards,\nPurgejig bot")
                    try:
                        self.mail.sendMailAttachment(subject, bodyText)
                    except Exception:
                        pass
                    
                    # if (supplyPressure > self.constant.MAXSUPPLYPRESSURE) and (supplyPressure < self.constant.PROOFPRESSURE):
                    #     self.__preFillCheck(supplyPressure, 'higher')
                    # else:
                    #     self.__preFillCheck(supplyPressure, 'lower')
                    # return True
            else:
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                
                # self.p.start()
                self.purgeLog.logger('error', 'The supply pressure is out of bounds. Allowing user to fix it')
                # time.sleep(0.3)
                self.toggleBeep(1)
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 22",1, 6)
                    self.display.lcd_display_string("Supply underpressure",3)
                    self.display.lcd_display_string("Please fix!", 4, 4)
                    supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    self.display.lcd_display_string("P1={:5.2f} bar ".format(round(supplyPressure,2)), 2, 4)
                # subject = "Purgejig bot has a bad message for you!"
                # bodyText = ("Dear Purgejig user,\n\n;"
                #             "Error 22;Supply Pressure too low;Please increase the supply pressure, see logs FMI.;\n\n"
                #             "Kind regards,\nPurgejig bot")
                # if self.mail.sendMailAttachment(subject, bodyText):
                #     with self.i2cLock:
                #         self.display.lcd_display_string("Error 22",1, 6)
                # else:
                #     with self.i2cLock:
                #         self.display.lcd_display_string("Error 22 & 16",1, 3)

                # p = Process(target=self.__fixableError, args=('self',))
                if self.stopFlag:
                    with self.i2cLock:
                        self.display.lcd_display_string("Press RESET", 3, 4)
                    self.stopFlag = False
                # self.p.start()
                
                while (supplyPressure >= self.constant.PROOFPRESSURE) or (supplyPressure <= self.constant.MAXSUPPLYPRESSURE):
                    with self.i2cLock:
                        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        self.display.lcd_display_string("{:5.2f}".format(round(supplyPressure,2)), 2, 7)

                    # This
                    if self.stopFlag or self.resetFlag:
                        # if self.p.is_alive():
                        #     # self.p.join()
                        #     with self.i2cLock:
                        #         self.display.lcd_clear()
                        #     time.sleep(1)
                        #     self.p.terminate()
                        #     self.toggleBeep(0)
                        break
                        # raise pins.emergencyStopException

                #  This
                if self.stopFlag:
                    raise pins.emergencyStopException
                
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = False
                # self.errorFlag = False
                # if self.p.is_alive():
                #     # self.p.join()
                #     time.sleep(1)
                #     self.p.terminate()
                #     self.toggleBeep(0)
                self.toggleBeep(0)

                time.sleep(1)
                with self.i2cLock:
                    supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                if (supplyPressure >= self.constant.PROOFPRESSURE) or (supplyPressure <= self.constant.MAXSUPPLYPRESSURE):
                    self.purgeLog.logger('error', 'The supply pressure is out of bounds. User failed to fix it')
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[3] = True
                    # self.errorFlag = True
                    return False
                else:
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[3] = False
                    # self.errorFlag = False
                    self.purgeLog.logger('warning', 'The supply pressure was out of bounds. User succeeded to fix it')
                    """
                    if (supplyPressure > self.constant.MAXSUPPLYPRESSURE) and (supplyPressure < self.constant.PROOFPRESSURE):
                        self.__preFillCheck(supplyPressure, 'higher')
                    else:
                        self.__preFillCheck(supplyPressure, 'lower')
                    """
                    # return True
                    
        # Another check incase
        if (supplyPressure > self.constant.MAXSUPPLYPRESSURE) and\
        (supplyPressure < self.constant.PROOFPRESSURE):
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = False
            # self.errorFlag = False
            self.purgeLog.logger('warning', "The supply pressure is SAFELY high. Program will continue")
            # self.__preFillCheck(supplyPressure, 'higher')
        else:
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = False
            # self.errorFlag = False
            self.purgeLog.logger('debug', 'The supply pressure was set SAFELY low. Program will continue+')
            # self.__preFillCheck(supplyPressure, 'lower')
        with self.i2cLock:
            vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
        if vacuumPressure == self.constant.VACUUMBROKEN:
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = True
            # self.errorFlag = True
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 6",1, 6)
                self.display.lcd_display_string("Sensor vac not",2, 3)
                self.display.lcd_display_string("detected",3, 6)
                self.display.lcd_display_string("Press RESET",4, 4)
            subject = "Purgejig bot has a bad message for you!"
            bodyText = ("Dear Purgejig user,\n\n;"
                        "Error 6;Vacuum sensor not detected;The vacuum sensor is broken or has no power, please check. See logs FMI.;\n\n"
                        "Kind regards,\nPurgejig bot")
            
            if self.mail.sendMailAttachment(subject, bodyText):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 6",1, 6)
            else:
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 6 & 16",1, 4)
                    # self.display.lcd_display_string("found, Email failed!",3)
            raise sensorErrorException()

    def machineRun(self, state, queue):
        """
        Method used to check if the sensors report viable values
        for the device to operate safely and as expected
        """
        self.__beepOff()
        self.checkBattery(1)
        self.checkHealth()
        # self.state = "idle"
        with self.state.get_lock():
            self.state[0] = 0
        if self.stateChecks():
            self.purgeLog.logger('debug','Initial state checks pass')
            self.__stateMachine()
            # self.state = "idle"
            with self.state.get_lock():
                self.state[0] = 0
            self.startFlag = False
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[0] = self.startFlag
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("PURGING DONE.",1, 3)
            
            subject = "Purgejig bot has a good message for you!"
            bodyText = ("Dear Purgejig user,\n\n;"
                        "The purge you initiated has successfully completed.; Please attend to this ASAP.;\n\n"
                        "Kind regards,\nPurgejig bot")
            
            try:
                if self.mail.sendMailAttachment(subject, bodyText):
                    with self.i2cLock:
                        self.display.lcd_display_string("To start a new",2, 3)
                        self.display.lcd_display_string("purge process,",3, 3)
                        self.display.lcd_display_string("press RESET",4, 4)
                else:
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 16: Email fail",1)
                        self.display.lcd_display_string("PURGING DONE.",2, 3)
                        self.display.lcd_display_string("Press RESET to",3, 3)
                        self.display.lcd_display_string("purge again.",4, 4)
            except Exception as err:
                self.purgeLog.logger('error','Purge done, but error "{}" crept in.'.format(err))
                with self.i2cLock:
                    self.display.lcd_display_string("Error 16: Email fail",1)
                    self.display.lcd_display_string("PURGING DONE.",2, 3)
                    self.display.lcd_display_string("Press RESET to",3, 3)
                    self.display.lcd_display_string("purge again.",4, 4)
                    
            while GPIO.input(self.nResetButton):
                time.sleep(0.3)
            return True
    # stateChecks should only return false if some major stuff-up happens
        else:
            self.__idle()
            raise faultErrorException()
        
        return False
    
    # Return start point for text on a 20x4 display
    def centreText(self, text):
        pos = int(10.0 - float(len(text))/2.0)
        return pos



class purge(object):
    def __init__(self, noOfCycles, state, std):
        # Get number of cycles and pass it to parent. Other option is to press cycle
        # button to increment before the purge process begins
        self.measure = monitor.measure(8, 1)
        self.sharedBools = Array('b', [False, False, False, False, False, False, False]) # start, stop, reset, error, shutdown, over pressure flags
        self.sharedValues = Array('d', [0.0, 0.0, 0.0, 0.0, noOfCycles])    # pressure 1 - potentially stat 1 and 2 and bat voltage and cycleCount for 2,3,4,5

        # State share is an array instead of a "value" because value gave issues with spinlock
        self.stateShare = Array('i', [0])
        # self.i2cLock = BoundedSemaphore(value=1) # No need for semaphore anymore
        self.i2cLock = RLock()

        # self.i2cLock.acquire(block=)

        self.runrun = purgeModes(self.measure, self.i2cLock, self.sharedBools, self.sharedValues, self.stateShare)
        self.task1 = safetyCheck.safety(self.measure, self.i2cLock, self.sharedBools, self.sharedValues)
        self.task3 = lowSupplyCheck.lowSupply(self.measure, self.runrun.mail, self.i2cLock, self.sharedBools, self.sharedValues, self.stateShare)
        self.task4 = batMon.batteryMonitoring(self.measure, self.runrun.mail, self.i2cLock, self.sharedBools, self.sharedValues)
        self.task5 = userinput.remoteUserInput(self.sharedBools, std)
        
    def runPurge(self):
        """
        4 seperate threads should run here.
        One involving battery health and safety check
        (low prio) and the other should handle purging (high prio)
        """      

        # Shared resources
        mpqueue = Queue()
        # Check battery and satefy check
        state = 1
        tasks = [multiCore.Process(
                target=self.task1.safetyCheck,
                args=(),
                kwargs=dict(queue=mpqueue))] + \
                [multiCore.Process(
                target=self.runrun.machineRun,
                args=(state,),
                kwargs=dict(queue=mpqueue))] + \
                [multiCore.Process(
                target=self.task3.lowSuppCheck,
                args=(),
                kwargs=dict(queue=mpqueue))] + \
                [multiCore.Process(
                target=self.task4.batteryMonitor,
                args=(),
                kwargs=dict(queue=mpqueue))] #+ \
                # [multiCore.Process(
                # target=self.task5.readTerm,
                # args=(),
                # kwargs=dict(queue=mpqueue))]

        try:

            [taskprocesses.start() for taskprocesses in tasks]

            while tasks[0].is_alive() or tasks[1].is_alive() or tasks[2].is_alive() or tasks[3].is_alive():# or tasks[4].is_alive():
                with self.sharedBools.get_lock():
                    stopFlag = self.sharedBools[1]
                    resetFlag = self.sharedBools[2]
                    errorFlag = self.sharedBools[3]
                    shutdownFlag = self.sharedBools[4]
                    rebootFlag = self.sharedBools[6]
                if errorFlag:
                    with self.sharedBools.get_lock():
                        self.sharedBools[1] = False
                else:
                    if stopFlag:
                        with self.i2cLock:
                            self.runrun.display.lcd_clear()
                        
                        [taskprocesses.terminate() for taskprocesses in tasks]

                        while tasks[0].is_alive() or tasks[1].is_alive() or tasks[2].is_alive() or tasks[3].is_alive():# or tasks[4].is_alive():
                            pass

                        self.runrun.display.lcd_display_string("Emergency stop!", 2, 2)
                        self.runrun.display.lcd_display_string("Press RESET", 3, 4)
                        raise pins.emergencyStopException
                    
                if (resetFlag or rebootFlag) and self.runrun.overPressureFlag == False:
                    with self.i2cLock:
                        self.runrun.display.lcd_clear()

                    [taskprocesses.terminate() for taskprocesses in tasks]

                    while tasks[0].is_alive() or tasks[1].is_alive() or tasks[2].is_alive() or tasks[3].is_alive():# or tasks[4].is_alive():
                        pass
                        
                    raise pins.emergencyStopException
                    
                elif shutdownFlag and self.runrun.overPressureFlag == False:
                    with self.i2cLock:
                        self.runrun.display.lcd_clear()
                    
                    [taskprocesses.terminate() for taskprocesses in tasks]
                    while tasks[0].is_alive() or tasks[1].is_alive() or tasks[2].is_alive() or tasks[3].is_alive():# or tasks[4].is_alive():
                        pass
                    raise pins.emergencyStopException
                
                
                # with self.stateShare.get_lock():
                #     print(self.stateShare[0])
                # if self.runrun.state == "idle":
                #     with self.stateShare.get_lock():
                #         self.stateShare[0] = 0
                # elif self.runrun.state == "vent":
                #     with self.stateShare.get_lock():
                #         self.stateShare[0] = 1
                # elif self.runrun.state == "fill":
                #     with self.stateShare.get_lock():
                #         self.stateShare[0] = 2
                # elif self.runrun.state == "initvacuum":
                #     with self.stateShare.get_lock():
                #         self.stateShare[0] = 3
                # else:
                #     with self.stateShare.get_lock():
                #         self.stateShare[0] = 4

                t1 = tasks[0]
                if t1.exception:
                    error, task1Traceback = t1.exception

                    with self.sharedBools.get_lock():
                        overPError = self.sharedBools[3]
                    
                    # Do not wait until task_2 is finished
                    [taskprocesses.terminate() for taskprocesses in tasks]

                    if overPError:
                        self.runrun.eVentHandle()
                    self.runrun.purgeLog.logger('error','safetyCheck code gave exception!')
                    raise overPressureException
                    # print("T1 exception")
                    # raise ChildProcessError(task1Traceback)
                    
                t2 = tasks[1]
                if t2.exception:
                    error, task2Traceback = t2.exception

                    [taskprocesses.terminate() for taskprocesses in tasks]

                    raise error
                    # raise ChildProcessError(task2Traceback)
                t4 = tasks[3]
                if t4.exception:
                    error, task4Traceback = t4.exception
                    [taskprocesses.terminate() for taskprocesses in tasks]

                    raise shutdownException

            # task1Process.join()
            # task2Process.join()
            task1and2Results = mpqueue.get()

        except (overPressureException, pins.emergencyStopException, timeOutError, sensorErrorException, vacuumException, ChildProcessError, batteryError) as e:
            print(e)
            self.runrun.purgeLog.logger('error', 'Error: {}'.format(e))
            beepbeepPeriod = 0.5 # seconds
            stopFlag = self.sharedBools[1]
            resetFlag = self.sharedBools[2]
            errorFlag = self.sharedBools[3]
            shutdownFlag = self.sharedBools[4]
            rebootFlag = self.sharedBools[6]
            while GPIO.input(self.runrun.nResetButton) and (resetFlag == False) and (shutdownFlag == False) and (rebootFlag == False):
                stopFlag = self.sharedBools[1]
                resetFlag = self.sharedBools[2]
                shutdownFlag = self.sharedBools[4]
                self.runrun.toggleBeep(0)
                if stopFlag == True or resetFlag:
                    self.runrun.display.backlight(0)
                    time.sleep(beepbeepPeriod/2)
                    self.runrun.display.backlight(1)
                else:
                    self.runrun.display.backlight(0)
                    self.runrun.toggleBeep(0)
                    time.sleep(beepbeepPeriod/2)
                    if resetFlag or stopFlag:
                        pass
                    else:
                        self.runrun.toggleBeep(1)
                    self.runrun.display.backlight(1)
                if GPIO.input(self.runrun.nStopButton) == 0:
                    self.sharedBools[1] = 1
                    self.runrun.toggleBeep(0)
                    if GPIO.input(self.runrun.nStopButton):
                        pass
                    else:
                        time.sleep(0.3)
                        if GPIO.input(self.runrun.nStopButton):
                            pass
                        else:
                            time.sleep(0.3)
                            if GPIO.input(self.runrun.nStopButton):
                                pass
                            else:
                                time.sleep(0.3)
                                if GPIO.input(self.runrun.nStopButton) == 0:
                                    shutdownFlag = True
                    
                
                time.sleep(beepbeepPeriod*2)
            self.runrun.toggleBeep(0)
            # time.sleep(1.5)
            if resetFlag:
                time.sleep(0.5)
            else:
                pass
            if stopFlag or errorFlag or shutdownFlag:
                self.runrun.display.lcd_clear()
            if shutdownFlag:
                # time.sleep(0.5)
                self.runrun.purgeLog.logger('debug', 'Shutdown button has been pressed')
                # self.runrun.display.lcd_clear()
                # time.sleep(0.1)
                shutDownText1 = "SHUTTING DOWN DEVICE"
                shutDownText2 = "GOODBYE!"
                self.runrun.display.lcd_display_string(shutDownText1, 2, self.runrun.centreText(shutDownText1))
                self.runrun.display.lcd_display_string(shutDownText2, 3, self.runrun.centreText(shutDownText2))
                time.sleep(1)
                shutDownText3 = "SHUTDOWN SUCCESS!"
                self.runrun.display.lcd_clear()
                self.runrun.display.lcd_display_string(shutDownText3, 2, self.runrun.centreText(shutDownText3))
                time.sleep(1)
                os.system("sudo shutdown now -h")
            elif GPIO.input(self.runrun.nResetButton) and rebootFlag == False:
                self.runrun.purgeLog.logger('debug', 'Reset button has been pressed')
                # self.runrun.display.lcd_clear()
                # time.sleep(0.2)
                self.runrun.display.lcd_display_string("RESETTING", 2, 5)
                del self.sharedValues
                del self.sharedBools
                time.sleep(0.5)
                os.execl(sys.executable, sys.executable, *sys.argv)
            else:
                self.runrun.purgeLog.logger('debug', 'Reboot button has been pressed')
                # 
                # time.sleep(1)
                if self.runrun.checkMains():
                    # self.runrun.display.lcd_clear()
                    restarttext1 = "RESTARTING"
                    restarttext2 = "DEVICE"
                    self.runrun.display.lcd_display_string(restarttext1, 2, self.runrun.centreText(restarttext1))
                    self.runrun.display.lcd_display_string(restarttext2, 3, self.runrun.centreText(restarttext2))
                    # self.runrun.display.lcd_display_string("Please be patient.", 2)
                    os.system("sudo reboot now -h")
                else:
                    # self.runrun.display.lcd_clear()
                    # time.sleep(0.1)
                    shutDownText1 = "SHUTTING DOWN DEVICE"
                    shutDownText2 = "GOODBYE!"
                    self.runrun.display.lcd_display_string(shutDownText1, 2, self.runrun.centreText(shutDownText1))
                    self.runrun.display.lcd_display_string(shutDownText2, 3, self.runrun.centreText(shutDownText2))
                    time.sleep(1)
                    shutDownText3 = "SHUTDOWN SUCCESS!"
                    self.runrun.display.lcd_clear()
                    self.runrun.display.lcd_display_string(shutDownText3, 2, self.runrun.centreText(shutDownText3))
                    time.sleep(1)
                    os.system("sudo shutdown now -h")
        except shutdownException as sde:
            self.runrun.purgeLog.logger('error', 'Error: {}'.format(sde))
            shutDownText1 = "SHUTTING DOWN DEVICE"
            shutDownText2 = "GOODBYE!"
            self.runrun.display.lcd_display_string(shutDownText1, 2, self.runrun.centreText(shutDownText1))
            self.runrun.display.lcd_display_string(shutDownText2, 3, self.runrun.centreText(shutDownText2))
            time.sleep(2)
            shutDownText3 = "SHUTDOWN SUCCESS!"
            self.runrun.display.lcd_clear()
            self.runrun.display.lcd_display_string(shutDownText3, 2, self.runrun.centreText(shutDownText3))
            time.sleep(2)
            os.system("sudo shutdown now -h")
        except Exception as e:
            print(e)
            self.runrun.purgeLog.logger('error', 'Error: {}'.format(e))
        finally:
            del self.sharedValues
            del self.sharedBools