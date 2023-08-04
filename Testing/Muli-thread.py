import threading
import time
import _thread as thread
from threading import Thread, Lock
from queue import Queue

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

# @dataclass(frozen = True)
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

class Test(notify.emailNotification):


    def __init__(self):

        # super().__init__()
        self.x = monitor.measure(1,1)
        self.display = displayLCD.lcd()
        self.constant = constantsNamespace()
        # self.vacuumPressure = round(self.x.vacuumConversion(self.x.readVoltage(1)), 6)
        # self.display.lcd_display_string("WTF")
        self.vacuumPressure = 0
        self.display.lcd_clear()
        self.lock = Lock()


    def checkBattery(self, state):
        

        # while True:
        #     self.vacuumPressure = round(self.x.vacuumConversion(self.x.readVoltage(1)), 6)
        return True
    
    def safetyCheck(self, state):
        time.sleep(5)
        print("State: ", state)
        # self.display.lcd_display_string("Vacuum: ")
        # while True:
        #     self.display.lcd_display_string("{:.2e}".format(self.vacuumPressure),1,8)
        return True

    


    def __worker(self, input, output):
        
        for func, args in iter(input.get, 'STOP'):
            # print(type(args))
            # print(args)
            if type(args) is tuple:
                result = self.__parses(func, *args)
            else:
                result = self.__parse(func, args)
            output.put(result)
    def __parse(self, tunc, args):
        result = tunc(args)
        return '%s says that %s%s is %s' % \
            (threading.current_thread().name, tunc.__name__, args, result)
    
    def __parses(self, tunc, *args, **kwargs):

        # print("tunc: ",tunc)
        # print("*args", *args)
        # print("**kwargs", **kwargs)
        result = tunc(*args)
        # return '%s says that %s%s is %s' % \
        #     (threading.current_thread().name, tunc.__name__, args, result)
        return (threading.current_thread(), tunc.__name__, args, result)
    
    # def __parses(self, tunc, sting, p, q):
    #     result = tunc(sting, p, q)
    #     return '%s says that %s%s is %s' % \
    #         (threading.current_thread().name, tunc.__name__, (sting, p, q), result) 

    
    def measureSomething(self, typeofSensor, channel):
        # print("1")
        # time.sleep(5)
        if typeofSensor == 'vac':
            with self.lock:
                self.vacuumPressure = self.x.vacuumConversion(self.x.readVoltage(channel))
            return True
        elif typeofSensor == '10bar':
            pass
        else:
            with self.lock:
                self.supplyPressure = self.x.pressureConversion(self.x.readVoltage(self.constant.SUPPLYPRESSURECHANNEL), '0-34bar')
            if self.supplyPressure >= 23:
                print("There is kak!")
            else:
                print("safe supply")
        
        return False
        
        
    def displaySomething(self, message, line, pos):
        # print("2")
        message = "{:.2e}".format(message)
        with self.lock:
            self.display.lcd_display_string(message, line, pos)
        return True


    def test(self):
        noOfProcesses = 4
        state = 1
        self.display.lcd_display_string("Vac: ",3)
        # kwargs = 
        # tasks = [(self.safetyCheck, (state))] + \
        #             [( self.checkBattery, (state) )] +\
        #             [(self.x.vacuumConversion, (self.x.readVoltage(self.constant.VACUUMCHANNEL)))] +\
        #             [(self.display.lcd_display_string, (self.vacuumPressure, 3, 5))]
        # tasks =     [(self.measureSomething, ('vac',1))] +\
        #             [(self.displaySomething, (self.vacuumPressure, 3, 5))]
        
        # tasks = [(self.safetyCheck, (state))] + \
        #             [(self.measureSomething, ('vac',1))] +\
        #             [(self.displaySomething, (self.vacuumPressure, 3, 5))]
        # tasks = [(self.displaySomething, (self.vacuumPressure, 3, 5))] +\
        #         [(self.measureSomething, ('vac',1))] +\
        #         [(self.measureSomething, ('0-34bar',2))]
        taskQueue = Queue()
        doneQueue = Queue()

        print("hello from parallel")
        try:
            
            while True:
                

                # if taskQueue.empty():
                #     # print("task Q empty")
                #     for task in tasks:
                #         taskQueue.put(task)
                # else:

                print("adding to the Q")
                taskQueue.put((self.safetyCheck, (state)))
                taskQueue.put((self.displaySomething, (self.vacuumPressure, 3, 5)))
                taskQueue.put((self.measureSomething, ('0-34bar',2)))
                taskQueue.put((self.measureSomething, ('vac',1)))

                print (taskQueue.empty())


                


                for i in range(noOfProcesses):
                    # print("process init")
                    Thread(target=self.__worker, args=(taskQueue, doneQueue)).start()
                    # time.sleep(0.5)
                    doneQueue.get()
                    # for i in range(len(taskQueue)):
                for i in range(noOfProcesses):
                    # doneQueue.get()
                    # print("getting results")
                    print('\t', doneQueue.get())
                for i in range(noOfProcesses):
                    taskQueue.put('STOP')
                    # taskQueue.put((self.displaySomething, (self.vacuumPressure, 3, 5)))
                    # taskQueue.put((self.measureSomething, ('0-34bar',2)))
                    # taskQueue.put((self.measureSomething, ('vac',1)))
                        
                # taskQueue.put((self.safetyCheck, (state)))
                
                    
                    

        except KeyboardInterrupt:
            pass

        finally:
            for i in range(noOfProcesses):
                print("stopping tasks")
                taskQueue.put('STOP')

class idiot():

    def __init__(self):
        self.run = Test()
    def runrun(self):
        self.run.test()


if __name__ == '__main__':
    # freeze_support()

    try:
        idi = idiot()

        idi.runrun()

    except KeyboardInterrupt:
        pass


    
# SuperFastPython.com
# example of using the queue
# from time import sleep
# from random import random
# from threading import Thread
# from queue import Queue


# try:
#     from Display import displayLCD
#     from notificationHandle import emailNotification as notify
#     from measurements import monitor
# except ImportError:
#     try:
#         import sys
#         sys.path.append('.')
#         from notificationHandle import emailNotification as notify
#         from measurements import monitor
#     except ImportError:
#         raise ImportError(
#             "Failed to import library from parent folder")



 
# # generate work
# def producer(queue):
#     print('Producer: Running')
#     # generate work
#     for i in range(10):
#         # generate a value
#         value = random()
#         # block
#         sleep(value)
#         # add to the queue
#         queue.put(value)
#     # all done
#     queue.put(None)
#     print('Producer: Done')
 
# # consume work
# def consumer(queue):
#     print('Consumer: Running')
#     # consume work
#     while True:
#         # get a unit of work
#         item = queue.get()
#         # check for stop
#         if item is None:
#             time.sleep(0.1)
        
    
 
# try:
    
#     # create the shared queue
#     queue = Queue()
#     # start the consumer
#     consumer = Thread(target=consumer, args=(queue,))
#     consumer.start()
#     # start the producer
#     producer = Thread(target=producer, args=(queue,))
#     producer.start()
# except KeyboardInterrupt:
#     producer.terminate()
#     consumer.terminate()
# finally:
#     # wait for all threads to finish
#     producer.join()
#     consumer.join()