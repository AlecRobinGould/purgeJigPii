import time
from multiprocessing import Process, Lock, current_process, Array, Queue


class MyProcess(Process):

    def __init__(self, lock, array, target=None, name=None, args=(), kwargs={}, daemon=None):

        tasks = [(self.safetyCheck, ())] + \
                [(self.checkBattery, ())]
        taskQueue = Queue()
        doneQueue = Queue()

        if taskQueue.empty():
            print("task Q empty")
            for task in tasks:
                taskQueue.put(task)

        super().__init__(
            group=None, target=self.worker, name=name, args=(taskQueue, doneQueue), kwargs=kwargs, daemon=daemon
        )
        # `args` and `kwargs` are stored as `self._args` and `self._kwargs`
        self.lock = lock
        self.array = array

    # def run(self) :
    #     with self.lock :
    #         for i in range(3):
    #             print(current_process().name, *self._args)
    #             # time.sleep(1)


    def worker(self, input, output):
        print("3")
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
        print(tunc,*args)
        result = tunc(*args)
        return '%s says that %s%s is %s' % \
             (current_process().name, tunc.__name__, args, result)

    def checkBattery(self):
        time.sleep(1)

        
        for i in range(len(self.array)):
            with self.lock:
                self.array[i] += 1
            
        return True
    
    def safetyCheck(self):
        
        for i in range(len(self.array)):
            with self.lock:
                self.array[i] += 5
        return True


if __name__ == '__main__' :

    lock = Lock()
    sharedArray = Array('d', [0.0, 0.0, 0.0, 0.0])
    print("1")
    
    p1 = MyProcess(lock=lock, array= sharedArray, args=())
    p2 = MyProcess(lock=lock, array= sharedArray, args=())

    p1.start()
    p2.start()

    p1.join()  # don't forget joining to prevent parent from exiting too soon.
    p2.join()