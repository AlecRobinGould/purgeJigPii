import time

class lowSupply(object):
    def __init__(self, monitor: object, notify: object, spinlock: object, sharedBools: bool, sharedValues: float):
        self.lowSupplyPressure = 16
        self.superLowSupplyPressure = 4

        self.monitor = monitor
        self.notify = notify
        self.spinlock = spinlock
        self.sharedBools = sharedBools
        self.sharedValues = sharedValues


    def lowSuppCheck(self, queue):
        """
        multicore method - Check saftey supply pressure in parallel to main
        :param monitor: access to measurements/monitor.py
        :type monitor object:
        :param spinlock: Since this is multicore, only write/read one at a time
        :type Lock object: for i2c bus
        :param sharedBools: Since this is multicore, a common memory space is needed
        :type Array of bools:
        :param sharedValues: Since this is multicore, a common memory space is needed
        :type Array of double: 
        """

        subject = "Purgejig bot has a bad message for you!"
        bodyText = ("Dear Purgejig user,\n\n;"
                    "Error 22;Supply under-pressure;The supply pressure has dropped below the last fill pressure (16 bar)."
                    "Purge will continue til the last cycle then wait for the correct pressure. See logs FMI.;\n\n"
                    "Kind regards,\nPurgejig bot")
        bodyTexts = ("Dear Purgejig user,\n\n;"
                    "Error 22;Supply under-pressure;The supply pressure has dropped below the normal fill pressure (4 bar)."
                    "Purge cannot continue til the last cycle then wait for the correct pressure. See logs FMI.;\n\n"
                    "Kind regards,\nPurgejig bot")

        
        with self.sharedBools.get_lock():
            startFlag = self.sharedBools[0]
        while startFlag == False:
            with self.sharedBools.get_lock():
                startFlag = self.sharedBools[0]
            time.sleep(0.2)

        while startFlag:

            with self.spinlock:
                supplyPressure = self.monitor.pressureConversion(self.monitor.readVoltage(3), "0-34bar")
            with self.sharedValues.get_lock():
                self.sharedValues[0] = supplyPressure
            
            if supplyPressure < self.lowSupplyPressure:
                if supplyPressure < self.superLowSupplyPressure:
                    if self.notify.sendMailAttachment(subject, bodyTexts):
                        time.sleep(60)
                    else:
                        pass
                else:
                    if self.notify.sendMailAttachment(subject, bodyText):
                        time.sleep(5*60)
                    else:
                        pass
            else:
                pass
            
            with self.sharedBools.get_lock():
                startFlag = self.sharedBools[0]
