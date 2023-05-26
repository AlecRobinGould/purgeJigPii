#!/usr/bin/env python

"""
=====================================================

Check "List of dependencies.txt" for required modules
=====================================================
"""
import RPi.GPIO as GPIO
import DifferentialADCPi
try: 
    from purgeJig import pins
    from Display import displayLCD
except ImportError:
    print("Failed to import pins from python system path")
    try:
        import sys
        sys.path.append('.')
        # from purgeJig import pins
        from purgeJig import pins
        from Display import displayLCD
    except ImportError:
        raise ImportError(
            "Failed to import library from parent folder")

class measure(pins.logicPins):
    """Class for taking measurements, including conversions"""
    def __init__(self):

        super().__init__() # This initialises the inherited class such that an instance does not
                           # to be explicitly created, including the log class.

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
            0.050000, 1026.000000       # 1.026000E+03
        ]
        # Initialise the ADC with default values
        try:
            self.adc = DifferentialADCPi.ADCDifferentialPi(address=0x6E, rate=18, bus=1)
        except:
            self.adc = DifferentialADCPi.ADCDifferentialPi(address=0x6F, rate=18, bus=1)
            print("ADC I2C adress has bugged out to 0x6F again")

        # Setting additional adc parameters
        self.adc.set_pga(1)
        self.adc.set_conversion_mode(0)
        # self.adc.set_bit_rate(18)

        """Create instance of the lcd class. WIll later be inherited where it needs to be"""
        self.display = displayLCD.lcd()
    
    def readVoltage(self, channelNo):
        if (channelNo > 4) or (channelNo < 1):
            raise ValueError("Channel number does not exist outside of 1-4")
        return self.adc.read_voltage(channelNo)
    
    def stateOfCharge(self, voltage):
        if voltage > self.SOCLookUp[0]:
            return self.SOCLookUp[1]
        elif voltage < self.SOCLookUp[12]:
            return self.SOCLookUp[13]
        else:
            for i in range(len(self.SOCLookUp)):
                if voltage < self.SOCLookUp[i] and voltage > self.SOCLookUp[i+2]:
                    return self.SOCLookUp[i+1]
    
    def pressureConversion(self, volt, type):
        try:
            if type == "0-10bar":
                return (volt - 0.4)*6.25
            else:
                return (volt - 0.4)*21.5625
        except ValueError:
                raise ValueError("Value does not correspond")
    
    def vacuumConversion(self, voltage):
        if voltage > self.vacuumLookUp[0]:
            return self.vacuumLookUp[1]
        elif voltage < self.vacuumLookUp[38]:
            return self.vacuumLookUp[39]
        else:
            for v in range(len(self.vacuumLookUp)):
                i=v*2
                if voltage <= self.vacuumLookUp[i] and voltage >= self.vacuumLookUp[i+2]:
                    return self.vacuumLookUp[i+3] -((self.vacuumLookUp[i+3] - self.vacuumLookUp[i+1]) * ((voltage - self.vacuumLookUp[i+2]) / (self.vacuumLookUp[i] - self.vacuumLookUp[i+2])))
                
    def statusMonitor(self):
        stat1MonValue = GPIO.input(self.stat1Mon)
        stat2MonValue = GPIO.input(self.stat2Mon)

        if stat1MonValue:
            if stat2MonValue:
                self.logger('debug', 'Battery is charged')
                return 'Charged'
            else:
                self.logger('debug', 'Battery is charging')
                return 'Charging'
        else:
            if stat2MonValue:
                self.logger('warning', 'Over-voltage or over-temperature fault')
                return 'Fault'
            else:
                self.logger('error', 'Over-current or charge timeout fault')
                return 'Major fault'
            
def main():
    read = measure()
    read.batteryStateSet(1, 0)
    try:
        while True:
            for i in range(1,5):
                # x = round(read.readVoltage(i), 2)
                if i == 1:
                    x = read.vacuumConversion(read.readVoltage(i))
                elif i == 2:
                    x = read.readVoltage(i)
                elif i == 3:
                    x = read.pressureConversion(read.readVoltage(i), "0-34bar")
                elif i == 4:
                    x = read.pressureConversion(read.readVoltage(i), "0-10bar")

                if i != 2:
                    # read.display.lcd_display_string("ADC {}: ".format(i)+ str(x)+" V ",i)
                    read.display.lcd_display_string("sensor {}: ".format(i)+ "{:.2e}".format(x),i)
                else:
                    read.display.lcd_display_string("Batt: "+str(read.stateOfCharge(x))+"% ",i)
    except KeyboardInterrupt:
        print("\nExited measurements through keyboard interupt")
        GPIO.cleanup()
    
if __name__ == "__main__":
    main()