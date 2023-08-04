from multiprocessing import Process, Value, Array, Lock
import time

def add_100(number, lock):
    for _ in range(100):
        time.sleep(0.01)
        with lock:
            number.value += 1

def add_100_array(numbers, lock):
    for _ in range(100):
        time.sleep(0.01)
        for i in range(len(numbers)):
            with lock:
                numbers[i] += 1
def changeBool(bools, lock):

    for i in range(len(bools)):
        with lock:
            bools[i] = True

if __name__ == "__main__":
    lock = Lock()
    shared_number = Value('i', 0) 
    print('Value at beginning:', shared_number.value)

    shared_array = Array('d', [0.0, 100.0, 200.0])
    print('Array at beginning:', shared_array[:])

    secondsharedArray = Array('b', [False, False, False, False])
    print('bool Array at beginning:', secondsharedArray[:])
    

    process1 = Process(target=add_100, args=(shared_number, lock))
    process2 = Process(target=add_100, args=(shared_number, lock))

    process3 = Process(target=add_100_array, args=(shared_array, lock))
    process4 = Process(target=add_100_array, args=(shared_array, lock))

    process5 = Process(target = changeBool, args = (secondsharedArray, lock))

    process1.start()
    process2.start()
    process3.start()
    process4.start()
    process5.start()

    process1.join()
    process2.join()
    process3.join()
    process4.join()
    process5.join()


    print('Value at end:', shared_number.value)
    print('Array at end:', shared_array[:])
    print('bool Array at end:', secondsharedArray[:])

    print('end main')