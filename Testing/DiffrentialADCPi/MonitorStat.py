from __future__ import absolute_import, division, print_function, \
                                                    unicode_literals
import RPi.GPIO as GPIO
import time
import os

try:
    # from DifferentialADCPi import DifferentialADCPi
    from DifferentialADCPi import ADCDifferentialPi
except ImportError:
    print("Failed to import ADCDifferentialPi from python system path")
    print("Importing from parent folder instead")
    try:
        import sys
        sys.path.append('..')
        # from DifferentialADCPi import DifferentialADCPi
        from DifferentialADCPi import ADCDifferentialPi
    except ImportError:
        raise ImportError(
            "Failed to import library from parent folder")

GPIO.setmode(GPIO.BCM)
stat1Mon = 8
stat2Mon = 1
batteryEnable = 19

GPIO.setup(stat1Mon,GPIO.IN)
GPIO.setup(stat2Mon,GPIO.IN)
GPIO.setup(batteryEnable,GPIO.OUT)


if __name__ == "__main__":
        
        adc = ADCDifferentialPi(address=0x6E, rate=18, bus=1)
        adc.set_pga(1)
        adc.set_conversion_mode(0)
        adc.set_bit_rate(18)

        GPIO.output(batteryEnable, True)

        while True:

                stat1MonValue = GPIO.input(stat1Mon)
                stat2MonValue = GPIO.input(stat2Mon)
                if stat2MonValue == 1 and stat1MonValue == 1:
                        print("Battery is charged: %02f" % adc.read_voltage(2))
                else:
                        print("Device is charging")
                
                print("Stat1: ", stat1MonValue)
                print("Stat2: ", stat2MonValue)
                print("")

                time.sleep(10)