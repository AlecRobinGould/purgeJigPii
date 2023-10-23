import time

class safety(object):
    def __init__(self, monitor: object, spinlock: object, sharedBools: bool, sharedValues: float):
        self.unsafePressure = 22
        self.sensorOff = -2 # sensor power off means sensor measures -8.59 bar

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
        # print("startFlag pressed")

        with self.spinlock:
            supplyPressure = self.monitor.pressureConversion(self.monitor.readVoltage(3), "0-34bar")
        with self.sharedValues.get_lock():
            self.sharedValues[0] = supplyPressure

        while supplyPressure < self.unsafePressure:
            # Dont look at the try except for answers
            try:
                with self.spinlock:
                    supplyPressure = self.monitor.pressureConversion(self.monitor.readVoltage(3), "0-34bar")
                with self.sharedValues.get_lock():
                    self.sharedValues[0] = supplyPressure
            except Exception as v:
                print(v)
            
            if supplyPressure < self.sensorOff:
                time.sleep(5)

        with self.sharedValues.get_lock():
            # print("errorflag true")
            self.sharedBools[3] = True # errorFlag?

        """This kills the other tasks in the main process.
        Dont forget that exceptions terminate all locks
        """
        raise Exception