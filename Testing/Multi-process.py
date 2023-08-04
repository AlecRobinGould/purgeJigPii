import time
import random
import concurrent.futures
from multiprocessing import Process, Queue, current_process, Array, Lock, Manager

from multiprocessing.pool import Pool
# from smbus import SMBus

try:
    from Display import displayLCD
    from notificationHandle import emailNotification as notify
    from measurements import monitor
except ImportError:
    try:
        import sys
        sys.path.append('.')
        from notificationHandle import emailNotification as notify
        from measurements import monitor
    except ImportError:
        raise ImportError(
            "Failed to import library from parent folder")

#
# Function run by worker processes
#

class Test(notify.emailNotification):


    def __init__(self):

        # super().__init__()
        x = monitor.measure(1,2)
        self.display = displayLCD.lcd()
        vacuumPressure = x.vacuumConversion(x.readVoltage(3))
        self.display.lcd_display_string("Hello")
        # global lock
        # lock = Lock()
        # global sharedArray
        # sharedArray = Array('d', [0.0, 0.0, 0.0, 0.0])
       

    def checkBattery(self, lock, toBeShared):
        time.sleep(1)

        
        for i in range(len(toBeShared)):
            with lock:
                toBeShared[i] += 1
            
        return True
    
    def safetyCheck(self, lock, toBeShared):
        
        for i in range(len(toBeShared)):
            with lock:
                toBeShared[i] += 5
        return True
    

    def worker(self, input, output):
        for func, args in iter(input.get, 'STOP'):
            if type(args) is tuple:
                result = self.parses(func, *args)
            else:
                result = self.parse(func, args)
            output.put(result)
    def parse(self, tunc, args):
        result = tunc(args)
        return '%s says that %s%s is %s' % \
            (current_process().name, tunc.__name__, args, result) 
    
    def parses(self, tunc, *args, **kwargs):

        result = tunc(*args)
        return '%s says that %s%s is %s' % \
             (current_process().name, tunc.__name__, args, result)
#
#
#

    def test(self):
        noOfProcesses = 2
        state = 1
        lock = Lock()
        tasks = [(self.safetyCheck, (lock))] + \
                [(self.checkBattery, (lock))]
        taskQueue = Queue()
        doneQueue = Queue()
        print("hello from parallel")

        if taskQueue.empty():
            print("task Q empty")
            for task in tasks:
                taskQueue.put(task)

        # Process(target=self.shareInit, args=(sharedArray, l))
        # for i in range(noOfProcesses):
        #     print("process init")
        #     Process(target=self.worker, args=(taskQueue, doneQueue)).start()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_url = {executor.submit(self.worker, taskQueue)}
            for future in concurrent.futures.as_completed(future_to_url):
                # url = future_to_url[future]
                try:
                    data = future.result()
                except Exception as exc:
                    # print('%r generated an exception: %s' % (url, exc))
                    pass
                else:
                    # print('%r page is %d bytes' % (url, len(data)))
                    pass

        for i in range(len(tasks)):
            print("getting results")
            print('\t', doneQueue.get())
        
        for i in range(noOfProcesses):
            print("stopping tasks")
            taskQueue.put('STOP')

# class idiot():
    
#     def __init__(self):
#         self.run = Test()
#     def runrun(self):
#         self.run.test()


if __name__ == '__main__':
    testing = Test()
    testing.test()


    # freeze_support()
    # idi = idiot()

    # idi.runrun()