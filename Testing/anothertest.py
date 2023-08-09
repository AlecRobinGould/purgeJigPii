import multiprocessing
import traceback

from time import sleep
###############################################################
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
##################################################################

# Pretty much an overload of the process module
class Process(multiprocessing.Process):
    """
    Class which returns child Exceptions to Parent.
    """

    def __init__(self, *args, **kwargs):

        # super.__init__(...)
        multiprocessing.Process.__init__(self, *args, **kwargs)
        # Can be used for pipe comms betweeen processes - NOTE: not thread or process safe like a Queue, use locks
        self._parent_conn, self._child_conn = multiprocessing.Pipe()
        self._exception = None

    
    def run(self):
        try:
            multiprocessing.Process.run(self)
            self._child_conn.send(None)
        except Exception as e:
            tb = traceback.format_exc()
            self._child_conn.send((e, tb))
            # raise e  # You can still rise this exception if you need to

    @property
    def exception(self):
        if self._parent_conn.poll():
            self._exception = self._parent_conn.recv()
        return self._exception


class Task_1(object):
    def __init__(self, z):
        self.z = z

    def do_something(self, lock, shared, values, queue):
        # z.lcd_display_string("Hello")
        # print("task 1")
        with shared.get_lock():
            errorFlag = shared[0]
        with lock:
            self.z.lcd_display_string("Press1:", 3)
        while not errorFlag:
            print("there")
            with shared.get_lock():
                errorFlag = shared[0]
            with values.get_lock():
                with lock:
                    self.z.lcd_display_string("{} bar ".format(round(values[0],2)), 3, 7)
        # queue.put(dict(users=2))
        # with lock:
        #     for x in range(len(shared)):
        #         shared[x] = False

# Use this task to check for E-vent case (pretty much if supp press > 23 bar)
class Task_2:
    def __init__(self, locks):
        self.lock = locks

    def do_something(self, z, lock, shared, values, queue):
        # sleep(5)
        # print("task 2")
        with self.lock:
            supplyPressure = z.pressureConversion(z.readVoltage(3), "0-34bar")
        with values.get_lock():
            values[0] = supplyPressure

        while supplyPressure < 23:
            print("here")
            with self.lock:
                supplyPressure = z.pressureConversion(z.readVoltage(3), "0-34bar")
            with values.get_lock():
                values[0] = supplyPressure   
        # queue.put(dict(users=5))
        with shared.get_lock():
        #     for x in range(len(shared)):
            shared[0] = True # errorFlag?
        raise Exception


def main():
    try:
        x = monitor.measure(1,2)
        display = displayLCD.lcd()
        lock3 = multiprocessing.Lock()
        task_1 = Task_1(display)
        task_2 = Task_2(lock3)

        # Example of multiprocessing which is used:
        # https://eli.thegreenplace.net/2012/01/16/python-parallelizing-cpu-bound-tasks-with-multiprocessing/
        task_1_queue = multiprocessing.Queue()
        task_2_queue = multiprocessing.Queue()

        # lock = multiprocessing.Lock()
        # lock2 = multiprocessing.Lock()
        
        shared = multiprocessing.Array('b', [False, False, False, False], lock=True)
        values = multiprocessing.Array('d', [0.0, 0.0, 0.0, 0.0], lock=True)

        ###########################################
        
        
        # vacuumPressure = x.vacuumConversion(x.readVoltage(3))
        with lock3:
            display.lcd_display_string("Hello")
        ############################################


        task_1_process = Process(
            target=task_1.do_something, args=(lock3, shared, values)
            ,kwargs=dict(queue=task_1_queue))

        task_2_process = Process(
            target=task_2.do_something, args=(x,lock3, shared, values)
            ,kwargs=dict(queue=task_2_queue))

        task_1_process.start()
        task_2_process.start()

        while task_1_process.is_alive() or task_2_process.is_alive():
            # sleep(10)
            print("main")
            # sleep(10)

            # with lock:
            #     for z in range(len(shared)):
            #         print("Index value: ", z)
            #         print("Shared value: ", shared[z])
            #     print("\n")

            if task_1_process.exception:
                error, task_1_traceback = task_1_process.exception

                # Do not wait until task_2 is finished
                task_2_process.terminate()

                raise ChildProcessError(task_1_traceback)

            if task_2_process.exception:
                error, task_2_traceback = task_2_process.exception

                # Do not wait until task_1 is finished
                task_1_process.terminate()

                # while True:
                    # print("correct something")
                # raise ChildProcessError(task_2_traceback)

        task_1_process.join()
        task_2_process.join()

        del shared
        del values

        task_1_results = task_1_queue.get()
        task_2_results = task_2_queue.get()

        task_1_users = task_1_results['users']
        task_2_users = task_2_results['users']

    except Exception:
        # Here usually I send email notification with error.
        print('traceback:', traceback.format_exc())

    finally:
        print("Program ended")
if __name__ == "__main__":
    main()