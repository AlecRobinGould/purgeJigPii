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

# Concurrency
from multiprocessing import Process, current_process, RLock, Lock, BoundedSemaphore, Queue, Array

import pins
from loggingdebug import log
from Display import displayLCD
from Decorate import customDecorator
from measurements import monitor, checkHealth
from Multicore import multiCore, safetyCheck

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
        EMERGENCYVENTPRESSURE = 23

        MAXLOWGAUGE = 10
        MAXHIGHGAUGE = 34

        # These are the values returned (roughly) for broken gauge
        SUPPLYBROKEN = -8
        VENTBROKEN = -2
        VACUUMPROKEN = -1

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

# class timeOutError(pins.Error):
#     """
#     Class for over reset exception
#     """
#     def __init__(self, message='Exception rasied through a process taking too long.'):
#         # Call the base class constructor with the parameters it needs
#         super(timeOutError, self).__init__(message)

class batteryError(pins.Error):
    """
    Class for battery or related circuity misbehaving
    """
    def __init__(self, message='Exception rasied through a faulty charging/battery related issue.'):
        # Call the base class constructor with the parameters it needs
        super(batteryError, self).__init__(message)

# inherit ability to control and monitor pins, logging, and notifcations
# This is the superclass!
"""Inheriting because... lazy. Composition over inheritance!!! Might fix this in future"""
class purgeModes(pins.logicPins):
    def __init__(self, measure, lock, sharedBools, sharedValues, state = 'idle'):
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
        self.display = displayLCD.lcd()
        self.mail = notify.emailNotification()
        self.purgeLog = log.log()
        self.decorate = customDecorator.customDecorators(self.purgeLog)
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
        else:
            # print("Config not found! Exiting!")
            # sys.exit(1)
            self.purgeLog.logger('error', 'Timeout config file not found')
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 20",1)
                self.display.lcd_display_string("Timeout",1)
                self.display.lcd_display_string("Config file failed!",3)
                self.display.lcd_display_string("Please check file.",4)
            
            self.__beepOn()
            time.sleep(10)
            self.__beepOff()
            

        
        # self.parallelProcessQueue()
        """Dont think we need this anymore"""
        self.p = Process(target=self.__fixableError)
    
    def eVentHandle(self):
        self.__emergencyVent()
        self.purgeLog.logger('error','Device is emergency venting')
        self.display.lcd_clear()
        self.display.lcd_display_string("Error 10",1)
        self.display.lcd_display_string("Supply over pressure",2)
        self.display.lcd_display_string("Press1:",self.constant.SUPPLYPRESSURECHANNEL)
        self.display.lcd_display_string("Please lower supply!",4)
        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
        while supplyPressure > 23:
            # with self.i2cLock:
            supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)

        time.sleep(0.5)
        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
        if supplyPressure < 23:
            self.purgeLog.logger('debug','Device supply pressure is safe.')
            # Pressure has been corrected
            self.__idle()
            self.__beepOff()
            # with self.sharedBoolFlags.get_lock():
            self.sharedBoolFlags[3] = False
        else:
            self.__emergencyVent()
            self.purgeLog.logger('error','Device is emergency venting again.')
            while supplyPressure > 23:
                # with self.i2cLock:
                supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)

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

    def checkBattery(self, state):
        with self.i2cLock:
            self.display.lcd_display_string("Battery check in",1)
            self.display.lcd_display_string("Progress.",2)
            self.display.lcd_display_string("Please be patient",3)
            self.display.lcd_display_string("                    ",4)

        # Its almost uncanny - assume eskom is off
        eskomIsOn = False
        majorFaultCounter = 0

        batteryStatus = self.measure.statusMonitor()
    
        if batteryStatus == 'Major fault':
            self.purgeLog.logger('warning', 'Major fault on battery system.')
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 11:",1)
                self.display.lcd_display_string("Bat mon major fault",2)
                self.display.lcd_display_string("Attempting to",3)
                self.display.lcd_display_string("proceed...",4)
            self.toggleBeep(1)
            while batteryStatus == 'Major fault':
                batteryStatus == self.measure.statusMonitor()
                if majorFaultCounter >= 3:
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[3] = True
                        # self.errorFlag = True
                    
                    # self.stopFlag = True
                    self.purgeLog.logger('error', 'Major fault not recovered.')
                    with self.i2cLock:
                        self.display.lcd_clear()
                    
                        self.display.lcd_display_string("                    ",3)
                        self.display.lcd_display_string("Power-off device",4)
                    raise faultErrorException()
                else:
                    self.purgeLog.logger('debug', 'Major fault counter: {}.'.format(majorFaultCounter))
                    majorFaultCounter += 1
                    time.sleep(5)
            self.purgeLog.logger('debug', 'Major fault recovered.')
        elif batteryStatus == 'Fault':
            self.purgeLog.logger('debug', 'Minor fault on battery system.')
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 12:",1)
                self.display.lcd_display_string("Bat mon minor fault",2)
                self.display.lcd_display_string("                    ",3)
                self.display.lcd_display_string("No action req.      ",4)
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
        if batPercent >= 40:
            self.purgeLog.logger('debug','Battery SOC is good.')
        else:
            self.purgeLog.logger('debug','Battery SOC is less than 40%. Not enough to proceed.')
            raise batteryError()

        self.batteryStateSet(batteryEnable = 1, chargeEnable=0)
        return True
    
    def checkHealth(self):
        system = checkHealth.healthyPi()
        metrics = system.checkPi()
        with self.i2cLock:
            self.display.lcd_display_string("Health check in ",1)
            # self.display.lcd_display_string("                    ",4)
        # I put this first so the logs make sense if email fails
        time.sleep(1)
        if metrics["Network"]:
            self.purgeLog.logger('debug', 'RPi network is goood.')
        else:
            # no point in trying to email here... the network will be restored at some point on its own.
            self.purgeLog.logger('debug', 'RPi network is down!')
        # Check available memory
        if metrics["Memory"]:
            self.purgeLog.logger('debug', 'RPi RAM is goood.')
        else:
            self.purgeLog.logger('warning', 'RPi RAM is over-used.')
            with self.i2cLock:
                self.display.lcd_clear()
            if self.mail.sendMailAttachment(
                subject = "Purgejig bot has a bad message for you!",
                bodyText = "Dear Purgejig user,\n\nRPi RAM is over-used!.\n\nKind regards,\nPurgejig bot"):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 17",1)
                    self.display.lcd_display_string("                    ",2)
                    self.display.lcd_display_string("RAM full",3)
                    self.display.lcd_display_string("Purge will cont.",4)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 16, 17:",1)
                    self.display.lcd_display_string("Email fail , and",2)
                    self.display.lcd_display_string("RAM full",3)
                    self.display.lcd_display_string("Purge will cont.",4)

            time.sleep(10)
            with self.i2cLock:
                self.display.lcd_clear()
                                    
        # Check available storage
        if metrics["Disk"]:
            self.purgeLog.logger('debug', 'RPi storage is goood.')
        else:
            self.purgeLog.logger('warning', 'RPi storage is over-used.')
            with self.i2cLock:
                self.display.lcd_clear()
            if self.mail.sendMailAttachment(
                subject = "Purgejig bot has a bad message for you!",
                bodyText = "Dear Purgejig user,\n\nRPi storage is over-used!.\n\nKind regards,\nPurgejig bot"):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 17",1)
                    self.display.lcd_display_string("                    ",2)
                    self.display.lcd_display_string("Storage full",3)
                    self.display.lcd_display_string("Purge will cont.",4)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 16, 17:",1)
                    self.display.lcd_display_string("Email fail , and",2)
                    self.display.lcd_display_string("Storage full",3)
                    self.display.lcd_display_string("Purge will cont.",4)
            
            time.sleep(10)
            with self.i2cLock:
                self.display.lcd_clear()

        # Check logfile
        if self.purgeLog.checkLogFile():
            self.purgeLog.logger('debug', 'Logfile is there and in good order.')
        else:
            # Possibly fruitless. might aswell try
            self.purgeLog.logger('warning', 'Logfile is not working.')
            with self.i2cLock:
                self.display.lcd_clear()
            if self.mail.sendMailAttachment(
                subject = "Purgejig bot has a bad message for you!",
                bodyText = "Dear Purgejig user,\n\nLog file not found, or accessable!.\n\nKind regards,\nPurgejig bot"):
                with self.i2cLock:
                    self.display.lcd_display_string("Error 21",1)
                    self.display.lcd_display_string("                    ",2)
                    self.display.lcd_display_string("Logging fault",3)
                    self.display.lcd_display_string("Purge will cont.",4)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 16, 21:",1)
                    self.display.lcd_display_string("Email fail , and",2)
                    self.display.lcd_display_string("Storage full",3)
                    self.display.lcd_display_string("Purge will cont.",4)
            time.sleep(10)
            with self.i2cLock:
                self.display.lcd_clear()

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
    
    def toggleBeep(self, state):
        # Allows toggling beep outside of this class
        if state:
            self.__beepOn()
        else:
            self.__beepOff()
    
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
        time.sleep(1)   # This closes the valve before the vacuum pump turns off
                        # reducing the chance of contamination
        GPIO.output(self.enPump, 0)
        GPIO.output(self.ventValve1, 0)
        GPIO.output(self.ventValve2, 0)
        GPIO.output(self.fillValve, 0)
        GPIO.output(self.enStepMotor, 0)
        # GPIO.output(self.enBuzzer, 0)
    
    # Take note that this is not a set of char being passes into
    # this decorator. It is an attribute of purgeModes class.
    # See __init__ for self.venttimeout
    @customDecorator.customDecorators.exitAfter('venttimeout')
    def __ventProcess(self):
        self.state = 'vent'
        ventType = 'None'
        try:
            # Venting process
            with self.i2cLock:
                ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            if (ventPressure < 0) and self.stopFlag == 0 and self.resetFlag == 0:
                # Insert error here
                ventType = 'Vacuum'
                self.__vent()
                with self.i2cLock:
                    self.display.lcd_display_string("Venting vacuum...", 2)
            elif (ventPressure >= self.constant.VENTPRESSURE) and self.stopFlag == 0 and self.resetFlag == 0:
                ventType = 'Pressurised'
                self.__vent()
                with self.i2cLock:
                    self.display.lcd_display_string("Venting Process...", 2)
            while ventPressure >= self.constant.VENTPRESSURE or ventPressure < -0.1:
                with self.i2cLock:
                    ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                    self.display.lcd_display_string("Press2: {} bar ".format(round(ventPressure,2)), 3)

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
        finally:
            if self.timeoutFlag:
                self.__idle()
                self.purgeLog.logger('error', 'Vent timeout errror!')
                with self.i2cLock:
                    self.display.lcd_clear()
                time.sleep(0.1)
                if ventType == 'Pressurised':
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 8:",1)
                        self.display.lcd_display_string("Vent timeout",2)
                        self.display.lcd_display_string("Press Reset",4)
                elif ventType == 'None':
                    with self.i2cLock:
                        self.display.lcd_display_string("Error 3:",1)
                        self.display.lcd_display_string("Vent timeout",2)
                        self.display.lcd_display_string("Sensor 2 fault",3)
                        self.display.lcd_display_string("Press Reset",4)
                else:
                    with self.i2cLock:
                        self.display.lcd_display_string("Error unknown:",1)
                        self.display.lcd_display_string("Vent timeout",2)
                        self.display.lcd_display_string("Press Reset",4)
                raise timeOutError()
            else:
                self.__ventExit()
                with self.i2cLock:
                    self.display.lcd_display_string("                    ", 2)
                    self.display.lcd_display_string("                    ", 3)
                
    @customDecorator.customDecorators.exitAfter('initialvactimeout')
    def __initVacProcess(self):
        self.state = 'initvacuum'
        manifoldPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
        if manifoldPressure > 0.5:
            self.__idle()
            self.purgeLog.logger('error', 'Manifold pressure too high to vacuum.')
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 19:",1)
                self.display.lcd_display_string("Vent failure",2)
                self.display.lcd_display_string("Press Reset",4)
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = True
            raise overPressureException()
        else:
            try:
                with self.i2cLock:
                    self.display.lcd_display_string("Initisalising vac...", 2)
                    self.display.lcd_display_string("Vac: ",3)
                self.__vacInit()
                with self.i2cLock:
                    vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                while vacuumPressure >= self.constant.INITVACUUMPRESSURE:
                    with self.i2cLock:
                        vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                    with self.i2cLock:
                        self.display.lcd_display_string("{:.2e}".format(vacuumPressure),3,5)

                    with self.sharedBoolFlags.get_lock():
                        self.stopFlag = self.sharedBoolFlags[1]
                    if self.stopFlag:
                        self.purgeLog.logger('debug', 'Emergency stop flag. Exiting from initial vacuum.')
                        break
                        # raise pins.emergencyStopException()
            except KeyboardInterrupt:
                self.timeoutFlag = True
                # self.stopFlag = True
                self.__vacExit()
            finally:
                with self.sharedBoolFlags.get_lock():
                    self.errorFlag = self.sharedBoolFlags[3]
                if self.timeoutFlag:
                    self.__idle()
                    self.purgeLog.logger('error', 'Initialising vacuum timeout errror!')
                    with self.i2cLock:
                        self.display.lcd_clear()
                        self.display.lcd_display_string("Error 5:",1)
                        self.display.lcd_display_string("Initial vac timeout",2)
                        self.display.lcd_display_string("Press Reset",4)
                    with self.sharedBoolFlags.get_lock():
                        self.sharedBoolFlags[3] = True
                    # self.errorFlag = True
                    raise timeOutError()
                elif self.stopFlag:
                    pass
                elif self.errorFlag:
                    pass
                else:
                    self.__vacExit()
                    with self.i2cLock:
                        self.display.lcd_display_string("                    ", 2)
                        self.display.lcd_display_string("                    ", 3)
            
    @customDecorator.customDecorators.exitAfter('vacuumtimeout')
    def __vacProcess(self):
        self.state = 'vacuum'
        try:
            # Vacuum process
            with self.i2cLock:
                fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")

            if (fillPressure >= self.constant.SAFETOVACUUM) and self.stopFlag == 0 and self.resetFlag == 0:
# Remember to change the error class to a suitable vacuum name and also display what needs to be displayed
                self.purgeLog.logger('error', 'Manifold pressure too high to open to vac')
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 19:",1)
                    self.display.lcd_display_string("Vent failure",2)
                    self.display.lcd_display_string("Press Reset",4)
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                    # self.errorFlag = True
                raise overPressureException()
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Vacuum Process...   ", 2)
                    self.display.lcd_display_string("Vac: ",3)
                self.__vac()
            time.sleep(1)
            with self.i2cLock:
                vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))

            if (vacuumPressure >= self.constant.INITVACUUMPRESSURE) and self.stopFlag == 0 and self.resetFlag == 0:
                while vacuumPressure >= self.constant.VACUUMPRESSURE:
                    with self.i2cLock:
                        vacuumPressure = self.measure.vacuumConversion(self.measure.readVoltage(self.constant.VACUUMCHANNEL))
                        self.display.lcd_display_string("{:.2e}".format(vacuumPressure),3,5)
                    with self.sharedBoolFlags.get_lock():
                        self.stopFlag = self.sharedBoolFlags[1]
                    if self.stopFlag:
                        self.purgeLog.logger('debug', 'Emergency stop flag. Exiting from vacuum.')
                        break
                        # raise pins.emergencyStopException() # this is a hack. fix later
            else:
# Remember to change the error class to a suitable vacuum name and also display what needs to be displayed
                self.purgeLog.logger('error', 'Vacuum load not detected. The pressure did not increase when solenoid opened!')
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 9:",1)
                    self.display.lcd_display_string("Vacuum load not",2)
                    self.display.lcd_display_string("detected",3)
                    self.display.lcd_display_string("Press Reset",4)
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                raise vacuumException()

        except KeyboardInterrupt:
            self.timeoutFlag = True
            self.__vacExit()
        finally:
            with self.sharedBoolFlags.get_lock():
                self.errorFlag = self.sharedBoolFlags[3]
            if self.timeoutFlag:
                self.__idle()
                self.purgeLog.logger('error', 'Vacuum timeout errror!')
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 21:",1)
                    self.display.lcd_display_string("Vacuum timeout",2)
                    self.display.lcd_display_string("Press Reset",4)
                raise timeOutError()
            elif self.stopFlag:
                pass
            elif self.errorFlag:
                pass
            else:
                self.__vacExit()
                with self.i2cLock:
                    self.display.lcd_display_string("                    ", 2)
                    self.display.lcd_display_string("                    ", 3)
    

    @customDecorator.customDecorators.exitAfter('filltimeout')
    def __fillProcess(self):
        self.state = 'fill'
        # Check if supply pressure is safe to apply
        try:
            self.__initiate()
            with self.i2cLock:
                # supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
            with self.sharedValues.get_lock():
                supplyPressure = self.sharedValues[0]
            if (supplyPressure >= self.constant.PROOFPRESSURE) or\
            (supplyPressure < self.constant.MINSUPPLYPRESSURE):
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                self.overPressureFlag = True
                # raise overPressureException()
            else:
                self.purgeLog.logger('debug',"The supply pressure is within bounds")

            # Check whether it is the last cycle, if it is, fill to 16 bar rather
            if self.lastCycleFlag:
                # Helium fill process
                if (supplyPressure >= self.constant.LASTFILLPRESSURE and supplyPressure < self.constant.PROOFPRESSURE) and self.stopFlag == 0:
                    self.purgeLog.logger('debug',"The supply pressure is greater than 16bar for last fill")
                    self.__heFill()
                    with self.i2cLock:
                        self.display.lcd_display_string("Last Fill Process...", 2)
                        self.display.lcd_display_string("Press1:", self.constant.SUPPLYPRESSURECHANNEL)
                        self.display.lcd_display_string("Press2:", self.constant.VENTPRESSURECHANNEL)

                    while (supplyPressure <= self.constant.LASTFILLPRESSURE) or (fillPressure <= self.constant.MAXLOWGAUGE):
                        with self.sharedValues.get_lock():
                            supplyPressure = self.sharedValues[0]
                        with self.i2cLock:
                            # supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                            fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                            self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                            self.display.lcd_display_string("{} bar ".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.overPressureFlag = True
                            # raise overPressureException()
                        elif self.stopFlag:
                            self.purgeLog.logger('debug', 'Emergency stop flag. Exiting')
                            break
                            # raise pins.emergencyStopException() # this is a hack. fix later
                else:
                    self.purgeLog.logger('debug',"The supply pressure is less than 16bar for last fill")
                    self.__initiate()
                    time.sleep(1)
                    with self.i2cLock:
                        highestPossiblePressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                    self.__heFill()
                    with self.i2cLock:
                        self.display.lcd_display_string("Last Fill Process...", 2)
                        self.display.lcd_display_string("Press1:", self.constant.SUPPLYPRESSURECHANNEL)
                        self.display.lcd_display_string("Press2:", self.constant.VENTPRESSURECHANNEL)

                    while (supplyPressure <= highestPossiblePressure) or\
                    (fillPressure <= self.constant.MAXLOWGAUGE) and self.stopFlag == 0:
                        with self.sharedValues.get_lock():
                            supplyPressure = self.sharedValues[0]
                        with self.i2cLock:
                            # supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                            fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                            self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                            self.display.lcd_display_string("{} bar ".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                        if supplyPressure >= self.constant.PROOFPRESSURE:
                            self.overPressureFlag
                            raise faultErrorException()
                        elif self.stopFlag:
                            self.purgeLog.logger('debug', 'Emergency stop flag. Exiting')
                            break
                            # raise pins.emergencyStopException() # this is a hack. fix later
            else:
                # Helium fill process
                self.purgeLog.logger('debug', 'Not the last fill cycle')
                if fillPressure <= self.constant.FILLPRESSURE and self.stopFlag == 0:
                    self.__heFill()
                    with self.i2cLock:
                        self.display.lcd_display_string("Fill Process...", 2)
                        self.display.lcd_display_string("Press1: {} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL)
                        self.display.lcd_display_string("Press2: {} bar ".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL)
                while fillPressure <= self.constant.FILLPRESSURE:
                    with self.sharedValues.get_lock():
                        supplyPressure = self.sharedValues[0]
                    with self.i2cLock:
                        # supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        fillPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
                        self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 7)
                        self.display.lcd_display_string("{} bar ".format(round(fillPressure,2)), self.constant.VENTPRESSURECHANNEL, 7)
                    if supplyPressure >= self.constant.PROOFPRESSURE:
                        self.overPressureFlag = True                       
                        raise overPressureException()
                    elif self.stopFlag:
                        self.purgeLog.logger('debug', 'Emergency stop flag. Exiting')
                        break
                        # raise pins.emergencyStopException() # this is a hack. fix later
        except KeyboardInterrupt:
            self.timeoutFlag = True
            self.__heFillExit()
        finally:
            if self.timeoutFlag:
                self.__idle()
                self.purgeLog.logger('error', 'Fill timeout errror!')
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 7:",1)
                    self.display.lcd_display_string("Fill timeout",2)
                    self.display.lcd_display_string("Press Reset",4)
                raise timeOutError()
            elif self.overPressureFlag:
                self.__idle()
                self.purgeLog.logger('error', 'Supply over pressure error!')
                # with self.i2cLock:
                #     self.display.lcd_clear()
                #     self.display.lcd_display_string("Error 10:",1)
                #     self.display.lcd_display_string("Supply over pressure",2)
                #     self.display.lcd_display_string("Press Reset",4)

            elif self.stopFlag:
                pass
            else:
                # MAKE SURE TO ADD A CHECK FOR WHEN LOW GAUGE == HIGH GAUGE
                self.__heFillExit()
                with self.i2cLock:
                    self.display.lcd_display_string("                    ", 2)
                    self.display.lcd_display_string("                    ", 3)
                    self.display.lcd_display_string("                    ", 4)

    def __stateMachine(self):
        """Add in provision to check for stopFlag and resetFlag"""
        with self.i2cLock:
            self.display.lcd_clear()
        # Operate only untill the desired number of cycles are complete
        with self.sharedBoolFlags.get_lock():
                self.errorFlag = self.sharedBoolFlags[3]
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
                self.display.lcd_display_string("Cycle %d of %d"%((self.noOfCycles+1), cycleCount), 1)
            
            self.__ventProcess()

            self.__initVacProcess()

            self.__vacProcess()
    
            self.__fillProcess()

            # Increment cycle count
            self.noOfCycles += 1

            with self.sharedBoolFlags.get_lock():
                self.errorFlag = self.sharedBoolFlags[3]
           
    
    def stateChecks(self):
        self.__initiate()

# Display once to save processing time
        with self.i2cLock:
            self.display.lcd_display_string("No of cycles: ", 1)
            self.display.lcd_display_string("Press start", 2)
            self.display.lcd_display_string("Press1: ", 3)
            self.display.lcd_display_string("Press2: ", 4)

        with self.i2cLock:
            supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
            ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")
# ____________User input_______________________________
        with self.sharedBoolFlags.get_lock():
            self.startFlag = self.sharedBoolFlags[0]
            cycleCount = self.sharedValues[4]
        while (self.startFlag == 0 and self.resetFlag == 0) and (self.stopFlag == 0):
            with self.i2cLock:
                with self.sharedBoolFlags.get_lock():
                    cycleCount = self.sharedValues[4]
                self.display.lcd_display_string("%d  "%cycleCount, 1, 14)
                supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                ventPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.VENTPRESSURECHANNEL), "0-10bar")

            # This is the implementation of the emergency vent
            if supplyPressure >= self.constant.EMERGENCYVENTPRESSURE:
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                self.__emergencyVent()
                with self.i2cLock:
                    self.display.lcd_display_string("Emergency vent!     ", 1)
                    self.display.lcd_display_string("Supply too high     ", 2)
                    self.display.lcd_display_string("Lower it!!!         ", 4)

                while supplyPressure >= self.constant.EMERGENCYVENTPRESSURE:
                    with self.i2cLock:
                        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        self.display.lcd_display_string("{} bar  ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 8)
                    
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
                    self.display.lcd_display_string("No of cycles:", 1)
                    self.display.lcd_display_string("Press start", 2)
                    self.display.lcd_display_string("Press1:", 3)
                    self.display.lcd_display_string("Press2:", 4)

            else:
                with self.i2cLock:
                    self.display.lcd_display_string("{} bar  ".format(round(supplyPressure,2)), self.constant.SUPPLYPRESSURECHANNEL, 8)
                    self.display.lcd_display_string("{} bar  ".format(round(ventPressure,2)), self.constant.VENTPRESSURECHANNEL, 8)
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
                    self.display.lcd_display_string("Error 2 & 4:",1)
                    self.display.lcd_display_string("Sensor 1 and 2 not",2)
                    self.display.lcd_display_string("found",3)
                    self.display.lcd_display_string("Press Reset",4)
                raise sensorErrorException()
            elif supplyPressure < self.constant.SUPPLYBROKEN and ventPressure > self.constant.VENTBROKEN:
                self.purgeLog.logger('error', 'Sensor 1 no signal. Likely broken.')
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 2:",1)
                    self.display.lcd_display_string("Sensor 1 not found",2)
                    self.display.lcd_display_string("Press Reset",4)
                raise sensorErrorException()
            elif supplyPressure > self.constant.SUPPLYBROKEN and ventPressure < self.constant.VENTBROKEN:
                self.purgeLog.logger('error', 'Sensor 2 no signal. Likely broken.')
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                # self.errorFlag = True
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 4:",1)
                    self.display.lcd_display_string("Sensor 2 not found",2)
                    self.display.lcd_display_string("Press Reset",4)
                raise sensorErrorException()

            elif supplyPressure > self.constant.SUPPLYBROKEN and supplyPressure < 1:
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = True
                self.errorFlag = True

                self.purgeLog.logger('error', 'The supply is not connected. Allowing user to fix it')
                time.sleep(0.3)
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 1",1)
                    self.display.lcd_display_string("                    ",2)
                    self.display.lcd_display_string("No supply connected",3)
                    self.display.lcd_display_string("Please fix!", 4)

                    self.display.lcd_display_string("Press1:", 2)

                if self.stopFlag:
                    self.display.lcd_display_string("Press reset!", 3)
                    self.stopFlag = False
                self.toggleBeep(1)

                while (supplyPressure <= self.constant.MAXSUPPLYPRESSURE):
                    with self.i2cLock:
                        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), 2, 8)

                    with self.sharedBoolFlags.get_lock():
                        self.stopFlag = self.sharedBoolFlags[1]
                        self.resetFlag = self.sharedBoolFlags[2]

                    if self.stopFlag or self.resetFlag:
                        raise pins.emergencyStopException
                    
                with self.sharedBoolFlags.get_lock():
                    self.sharedBoolFlags[3] = False
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
                    self.purgeLog.logger('warning', 'The no supply was connected. User succeeded to fix it')
                    
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
                time.sleep(0.3)
                with self.i2cLock:
                    self.display.lcd_clear()
                    self.display.lcd_display_string("Error 22",1)
                    self.display.lcd_display_string("                    ",2)
                    self.display.lcd_display_string("Supply too low",3)
                    self.display.lcd_display_string("Please fix!", 4)

                    self.display.lcd_display_string("Press1:", 2)

                # p = Process(target=self.__fixableError, args=('self',))
                if self.stopFlag:
                    self.display.lcd_display_string("Press reset!", 3)
                    self.stopFlag = False
                # self.p.start()
                self.toggleBeep(1)
                while (supplyPressure >= self.constant.PROOFPRESSURE) or (supplyPressure <= self.constant.MAXSUPPLYPRESSURE):
                    with self.i2cLock:
                        supplyPressure = self.measure.pressureConversion(self.measure.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), "0-34bar")
                        self.display.lcd_display_string("{} bar ".format(round(supplyPressure,2)), 2, 8)

                    # This
                    if self.stopFlag or self.resetFlag:
                        # if self.p.is_alive():
                        #     # self.p.join()
                        #     with self.i2cLock:
                        #         self.display.lcd_clear()
                        #     time.sleep(1)
                        #     self.p.terminate()
                        #     self.toggleBeep(0)
                        raise pins.emergencyStopException

                #  This
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
        if vacuumPressure == -1:
            with self.sharedBoolFlags.get_lock():
                self.sharedBoolFlags[3] = True
            # self.errorFlag = True
            with self.i2cLock:
                self.display.lcd_clear()
                self.display.lcd_display_string("Error 6:",1)
                self.display.lcd_display_string("Vacuum sensor not",2)
                self.display.lcd_display_string("found",3)
                self.display.lcd_display_string("Press Reset",4)
            raise sensorErrorException()



    def machineRun(self, state, queue):
        """
        Method used to check if the sensors report viable values
        for the device to operate safely and as expected
        """
        self.__beepOff()
        self.checkBattery(1)
        self.checkHealth()
        if self.stateChecks():
            self.purgeLog.logger('debug','Initial state checks pass')
            self.__stateMachine()
            self.state = 'idle'
            self.startFlag = False
            with self.i2cLock:
                self.display.lcd_clear()
            if self.mail.sendMailAttachment(
                subject = "Purgejig bot has a good message for you!",
                bodyText = "Dear Purgejig user,\n\nThe purge you initiated has successfully completed.\n\nKind regards,\nPurgejig bot"):
                with self.i2cLock:
                    self.display.lcd_display_string("Purge has completed.",1)
                    self.display.lcd_display_string("Please restart to",2)
                    self.display.lcd_display_string("proceed further.",3)
            else:
                with self.i2cLock:
                    self.display.lcd_display_string("Error 16: Email fail",1)
                    self.display.lcd_display_string("Purge has completed.",2)
                    self.display.lcd_display_string("Please restart to",3)
                    self.display.lcd_display_string("proceed further.",4)

            while GPIO.input(self.nResetButton):
                time.sleep(0.3)
            return True
    # stateChecks should only return false if some major stuff-up happens
        else:
            self.__idle()
            raise faultErrorException()
        
        return False

class purge(object):
    def __init__(self, noOfCycles, state):
        # Get number of cycles and pass it to parent. Other option is to press cycle
        # button to increment before the purge process begins
        self.measure = monitor.measure(8, 1)
        self.sharedBools = Array('b', [False, False, False, False]) # start, stop, reset, error flags
        self.sharedValues = Array('d', [0.0, 0.0, 0.0, 0.0, noOfCycles])    # pressure 1 - potentially stat 1 and 2 and bat voltage and cycleCount for 2,3,4,5
        # self.i2cLock = BoundedSemaphore(value=1)
        self.i2cLock = RLock()

        # self.i2cLock.acquire(block=)

        self.runrun = purgeModes(self.measure, self.i2cLock, self.sharedBools, self.sharedValues, state)
        self.task1 = safetyCheck.safety(self.measure, self.i2cLock, self.sharedBools, self.sharedValues)
        
    def runPurge(self):
        """
        Two seperate threads should run here.
        One involving battery health and safety check
        (low prio) and the other should handle purging (high prio)
        """      

        # Shared resources
        mpqueue = Queue()
        # Check battery and satefy check
        

        task1Process = multiCore.Process(
            target=self.task1.safetyCheck,
            args=(),
            kwargs=dict(queue=mpqueue))

        state = 1
        task2Process = multiCore.Process(
            target=self.runrun.machineRun,
            args=(state,),
            kwargs=dict(queue=mpqueue))
        
        task3Process = multiCore.Process(
            target=self.runrun.machineRun,
            args=(state,),
            kwargs=dict(queue=mpqueue))

        try:
            task1Process.start()
            task2Process.start()

            while task1Process.is_alive() or task2Process.is_alive():
                # print("alive")
                with self.sharedBools.get_lock():
                    stopFlag = self.sharedBools[1]
                    resetFlag = self.sharedBools[2]
                if resetFlag:
                    task1Process.terminate()
                    task2Process.terminate()
                    time.sleep(0.5)
                    if GPIO.input(self.runrun.nResetButton):
                        # with self.i2cLock:
                        self.runrun.display.lcd_clear()
                        self.runrun.display.lcd_display_string("Reset pressed", 1)
                        time.sleep(0.1)
                        os.execl(sys.executable, sys.executable, *sys.argv)
                    else:
                        # with self.i2cLock:
                        self.runrun.display.lcd_clear()
                        self.runrun.display.lcd_display_string("Restarting device,", 1)
                        self.runrun.display.lcd_display_string("Please be patient.", 2)
                        os.system("sudo reboot now -h")
                elif stopFlag:
                    task1Process.terminate()
                    task2Process.terminate()
                    # with self.i2cBusLock:
                    self.runrun.display.lcd_clear()
                    self.runrun.display.lcd_display_string("E-stop pressed", 1)
                    self.runrun.display.lcd_display_string("Press reset to", 2)
                    self.runrun.display.lcd_display_string("Continue...", 3)
                    # time.sleep(0.3)
                    raise pins.emergencyStopException
                    
                if task1Process.exception:
                    error, task1Traceback = task1Process.exception

                    #_______________________________ Do something here to correct it_____________________________________________________________________

                    # raise ChildProcessError(task1Traceback)
                    with self.sharedBools.get_lock():
                        overPError = self.sharedBools[3]

                    
                    # Do not wait until task_2 is finished
                    task2Process.terminate()      
            
                    if overPError:
                        self.runrun.eVentHandle()

                    raise overPressureException
                    # raise ChildProcessError(task1Traceback)
                    

                if task2Process.exception:
                    error, task2Traceback = task2Process.exception

                    # Do not wait until task_1 is finished
                    task1Process.terminate()

                    raise error
                    # raise ChildProcessError(task2Traceback)

            # task1Process.join()
            # task2Process.join()
                        

            task1and2Results = mpqueue.get()

        except (overPressureException, pins.emergencyStopException, timeOutError, sensorErrorException, vacuumException, ChildProcessError) as e:
            print(e)
            beepbeepPeriod = 0.5 # seconds
            resetFlag = self.sharedBools[2]
            while GPIO.input(self.runrun.nResetButton) and resetFlag == 0:
                stopFlag = self.sharedBools[1]
                resetFlag = self.sharedBools[2]
                self.runrun.toggleBeep(0)
                if stopFlag == 1:
                    self.runrun.display.backlight(0)
                    time.sleep(beepbeepPeriod)
                    self.runrun.display.backlight(1)
                    
                else:
                    self.runrun.display.backlight(0)
                    self.runrun.toggleBeep(0)
                    time.sleep(beepbeepPeriod)
                    self.runrun.toggleBeep(1)
                    self.runrun.display.backlight(1)
                
                time.sleep(beepbeepPeriod*2)
            self.runrun.purgeLog.logger('debug', 'Reset button has been pressed')
            time.sleep(0.5)
            if GPIO.input(self.runrun.nResetButton):
                self.runrun.display.lcd_clear()
                self.runrun.display.lcd_display_string("Reset pressed", 1)
                os.execl(sys.executable, sys.executable, *sys.argv)
            else:
                time.sleep(1)
                self.runrun.display.lcd_clear()
                self.runrun.display.lcd_display_string("Restarting device,", 1)
                self.runrun.display.lcd_display_string("Please be patient.", 2)
                os.system("sudo reboot now -h")
            # self.removeCallBacks()
        finally:
            if task1Process.is_alive() or task2Process.is_alive():
                task1Process.terminate()
                task2Process.terminate()
            del self.sharedValues
            del self.sharedBools
            
            

            # purge SM
            

        
# This is the usage method. Take note of the error handling
def main():
    '''
    Main program function
    '''
    test = purge(5,'idle')
    try:
        test.runPurge()
        print("program has ended")
        

    except KeyboardInterrupt as e:
        test.runrun.setIdle()
        
        
        test.runrun.display.lcd_clear()
        test.runrun.display.lcd_display_string("Error! Program",1)
        test.runrun.display.lcd_display_string("exited externally.",2)
        test.runrun.display.lcd_display_string("Perform a full power",3)
        test.runrun.display.lcd_display_string("cycle to continue.",4)
        time.sleep(1)
        GPIO.cleanup()
        # time.sleep(1)
    except faultErrorException as e:
        test.runrun.setIdle()
        test.runrun.toggleBeep(1)
        print(e)

    finally:
        pass





    

if __name__ == "__main__":
    main()