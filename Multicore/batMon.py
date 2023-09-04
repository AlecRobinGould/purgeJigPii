import time

class batteryMonitoring(object):
    def __init__(self, monitor: object, notify: object, spinlock: object, sharedBools: bool, sharedValues: float):
        self.minSOC = 40

        self.monitor = monitor
        self.notify = notify
        self.spinlock = spinlock
        self.sharedBools = sharedBools
        self.sharedValues = sharedValues

    def batteryMonitor(self, queue):
        """
        multicore method - Check battery stats in parallel to main
        :param monitor: access to measurements/monitor.py
        :type monitor object:
        :param notify: access email notifications - notificationHandle/emailNotification.py
        :type notify object:
        :param spinlock: Since this is multicore, only write/read one at a time
        :type Lock object: for i2c bus
        :param sharedBools: Since this is multicore, a common memory space is needed
        :type Array of bools:
        :param sharedValues: Since this is multicore, a common memory space is needed
        :type Array of double: 
        """

        subject = "Purgejig bot has a bad message for you!"
        bodyText = ("Dear Purgejig user,\n\n;"
                    "Error 13;Battery voltage is too low; The battery percentage is too low and isnt charging, purge may fail. See logs FMI.;\n\n"
                    "Kind regards,\nPurgejig bot")
        
        with self.sharedBools.get_lock():
            startFlag = self.sharedBools[0]
        while startFlag == False:
            with self.sharedBools.get_lock():
                startFlag = self.sharedBools[0]
            time.sleep(0.2)
        
        while startFlag:
            
            if self.monitor.statusMonitor() == 'Charging':
                time.sleep(600)
            else:
                with self.spinlock:
                    batSOC = self.monitor.stateOfCharge(self.monitor.readVoltage(2))
                if batSOC <= self.minSOC:
                    if self.notify.sendMailAttachment(subject, bodyText):
                        time.sleep(60)
                    else:
                        pass
                else:
                    time.sleep(5*60)

            with self.sharedBools.get_lock():
                startFlag = self.sharedBools[0]