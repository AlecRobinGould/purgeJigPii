import time

class safety(object):
    def __init__(self, monitor: object, spinlock: object, sharedBools: bool, sharedValues: float):
        self.monitor = monitor
        self.spinlock = spinlock
        self.sharedBools = sharedBools
        self.sharedValues = sharedValues

    def safetyCheck(self, queue):
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
        with self.sharedBools.get_lock():
            startFlag = self.sharedBools[0]
        while startFlag == False:
            with self.sharedBools.get_lock():
                startFlag = self.sharedBools[0]
            time.sleep(0.2)
        print("startFlag pressed")

        with self.spinlock:
            supplyPressure = self.monitor.pressureConversion(self.monitor.readVoltage(3), "0-34bar")
        with self.sharedValues.get_lock():
            self.sharedValues[0] = supplyPressure

        while supplyPressure < 23:
            with self.spinlock:
                supplyPressure = self.monitor.pressureConversion(self.monitor.readVoltage(3), "0-34bar")
            
            print(supplyPressure)
            with self.sharedValues.get_lock():
                self.sharedValues[0] = supplyPressure   

        with self.sharedValues.get_lock():
            print("errorflag true")
            self.sharedBools[3] = True # errorFlag?


        # while supplyPressure > 23:
        #     with spinlock:
        #         supplyPressure = monitor.pressureConversion(monitor.readVoltage(3), "0-34bar")
        #     with sharedValues.get_lock():
        #         sharedValues[0] = supplyPressure

        # with sharedValues.get_lock():
        # #     for x in range(len(shared)):
        #     sharedBools[3] = False # errorFlag?

        raise Exception