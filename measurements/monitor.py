#!/usr/bin/env python

"""
=====================================================

Check "List of dependencies.txt" for required modules
=====================================================
"""
import RPi.GPIO as GPIO
try:
    import sys
    sys.path.append('.')
    # Can comment 1 below out
    import pins
    import time
    from loggingdebug import log
    from measurements import DifferentialADCPi
    # from DifferentialADCPi import TimeoutError as TE
    # import pins
    # from Display import displayLCD
except ImportError:
    raise ImportError(
        "Failed to import library from parent folder")

class measure(object):
    """Class for taking measurements, including conversions"""
    def __init__(self, statMon1, statMon2):
        """
         Class constructor - Initialise measurements class
         :param statMon1: receives monitoring pin number when measure class in instantiated
         :type int:
         :param statMon2: receives monitoring pin number when measure class in instantiated
         :type int: 
         """

        # self.gpio = pins.logicPins()

        self.TE = DifferentialADCPi.TimeoutError

        self.logthis = log.log()

        self.statMon1 = statMon1
        self.statMon2 = statMon2

        # self.logthis.logger("debug", "Measure constructor has run")
        
        self.SOCLookUp = [
            0.96637, 100,
            0.94336, 90,
            0.92035, 80,
            0.89734, 70,
            0.87433, 60,
            0.85132, 50,
            0.82831, 40
        ]
        self.vacuumLookUp = [
            2.000000, 0.001170000,      # 1.170000E-03
            1.972166, 0.003016505,      # 3.016505E-03
            1.886420, 0.006832010,      # 6.832010E-03
            1.800673, 0.010079412,      # 1.007941E-02
            1.629181, 0.017359195,      # 1.735920E-02
            1.457688, 0.028149044,      # 2.814904E-02
            1.286195, 0.038351617,      # 3.835162E-02
            1.114703, 0.050657184,      # 5.065718E-02
            0.943210, 0.065567967,      # 6.556797E-02
            0.771717, 0.084853359,      # 8.485336E-02
            0.600224, 0.124111778,      # 1.241118E-01
            0.428732, 0.183521313,      # 1.835213E-01
            0.257239, 0.286452702,      # 2.864527E-01
            0.171493, 0.453614182,      # 4.536142E-01
            0.128620, 0.668560822,      # 6.685608E-01
            0.102896, 1.466336647,      # 1.466337E+00
            0.085746, 10.11756952,      # 1.011757E+01
            0.068597, 69.81017169,      # 6.981017E+01
            0.051448, 481.6828844,      # 4.816829E+02
            0.050000, 1026.000000,      # 1.026000E+03
            0.000000, -1
        ]
        # Initialise the ADC with default values
        bits=16
        # try:
        self.adc = DifferentialADCPi.ADCDifferentialPi(address=0x6E, rate=bits, bus=1, logObj = self.logthis)
        # except:
        #     # Juuuuust incase
        #     try:
        #         self.adc = DifferentialADCPi.ADCDifferentialPi(address=0x6F, rate=bits, bus=1, logObj=self.logthis)
        #     except:
        #         try:
        #             self.adc = DifferentialADCPi.ADCDifferentialPi(address=0x68, rate=bits, bus=1, logObj=self.logthis)
        #         except:
        #             self.adc = DifferentialADCPi.ADCDifferentialPi(address=0x6D, rate=bits, bus=1, logObj=self.logthis)
        # except Exception as v:
        #     raise TimeoutError

            # print("ADC I2C adress no valid")

        # Setting additional adc parameters
        self.adc.set_pga(1)
        self.adc.set_conversion_mode(0)
        # self.adc.set_bit_rate(bits)

        
    
    def readVoltage(self, channelNo):
        if (channelNo > 4) or (channelNo < 1):
            raise ValueError("Channel number does not exist outside of 1-4")
        return self.adc.read_voltage(channelNo)
    
    def stateOfCharge(self, voltage):
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Leaving a note here to check if charging should be disabled first before checking battery percentage
# ====================================================================================================
        # return 30
        if voltage > self.SOCLookUp[0]:
            return self.SOCLookUp[1]
        elif voltage < self.SOCLookUp[12]:
            return self.SOCLookUp[13]
        else:
            for i in range(len(self.SOCLookUp)):
                if voltage < self.SOCLookUp[i] and voltage > self.SOCLookUp[i+2]:
                    return self.SOCLookUp[i+1]
    
    def pressureConversion(self, volt, type):
        """
        method for getting pressure from pressure sensors

        :param volt: Voltage from the ADC
        :type volt: float
        :param type: Type of pressure sensor to convert (0-10bar) or (0-34bar)
        :type type: string
        :return: Pressure of the voltage channel, of a type
        :rtype: float
        :raises IOError: Value does not correspond
        """
        try:
            if type == "0-10bar":
                # print("Volt10bar: {}\n".format(volt))
                if volt >= 0.4:
                    return (volt - 0.4019)*6.25 # 0.4012 calculated from resistor netowrk actual value
                else:
                    # return 0.00
                    return (volt - 0.4019)*6.25
            else:
                # print("Volt34bar: {}\n".format(volt))
                if volt >= 0.4:
                    return (volt - 0.3985)*21.54625
                else:
                    # return 0.00
                    return (volt - 0.39845)*21.54625
        except ValueError:
                raise ValueError("Value does not correspond")
    
    def vacuumConversion(self, voltage):
        # print("Voltage: {}".format(voltage))
        if voltage <= self.vacuumLookUp[40]:
            return self.vacuumLookUp[41]
        elif voltage > self.vacuumLookUp[0]:
            return self.vacuumLookUp[1]
        elif voltage < self.vacuumLookUp[38] and voltage > self.vacuumLookUp[40]:
            return self.vacuumLookUp[39]
        else:
            for v in range(len(self.vacuumLookUp)):
                i=v*2
                if voltage <= self.vacuumLookUp[i] and voltage >= self.vacuumLookUp[i+2]:
                    return self.vacuumLookUp[i+3] -((self.vacuumLookUp[i+3] - self.vacuumLookUp[i+1]) *\
                            ((voltage - self.vacuumLookUp[i+2]) / (self.vacuumLookUp[i] - self.vacuumLookUp[i+2])))
                
    def statusMonitor(self):
        stat1MonValue = GPIO.input(self.statMon1)
        stat2MonValue = GPIO.input(self.statMon2)

        # stat1MonValue = 0
        # stat2MonValue = 0
        # return 'Fault'
        # return 'Major fault'
        if stat1MonValue:
            if stat2MonValue:
                # self.logthis.logger('debug', 'Battery is charged')
                return 'Charged'
            else:
                # self.logthis.logger('debug', 'Battery is charging')
                return 'Charging'
        else:
            if stat2MonValue:
                # self.logthis.logger('warning', 'Over-voltage or over-temperature fault')
                return 'Fault'
            else:
                # self.logthis.logger('error', 'Over-current or charge timeout fault')
                return 'Major fault'