#!/usr/bin/env python
"""
================================================



================================================




"""

from __future__ import absolute_import, division, print_function, \
                                                    unicode_literals
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


def main():
    '''
    Main program function
    '''

    adc = ADCDifferentialPi(address=0x6E, rate=18, bus=1)
    adc.set_pga(1)
    adc.set_conversion_mode(0)
    adc.set_bit_rate(18)

    while True:

        # avgFactor = 10
        # ADCSUM = 0
        # 
# 
        # read from ADC channels and print to screen
        # print("Channel 1: %02f" % adc.read_voltage(1))
        # for i in range(avgFactor):
            # ADCSUM += adc.read_voltage(1)
# 
        # ADCAVG = ADCSUM/avgFactor
        # print("Channel 1: %02f" % ADCAVG)
        # print("Channel 1: %02f" % adc.read_voltage(1))
        print("Channel 2: %02f" % adc.read_voltage(2))
        # print("Channel 3: %02f" % adc.read_voltage(3))
        # print("Channel 4: %02f" % adc.read_voltage(4))
        # print("Channel 5: %02f" % adc.read_voltage(5))
        # print("Channel 6: %02f" % adc.read_voltage(6))
        # print("Channel 7: %02f" % adc.read_voltage(7))
        # print("Channel 8: %02f" % adc.read_voltage(8))

        # wait 0.2 seconds before reading the pins again
        time.sleep(0.5)
        # clear the console
        # os.system('clear')

if __name__ == "__main__":
    main()