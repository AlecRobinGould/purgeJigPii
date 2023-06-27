from __future__ import print_function
import sys
import threading
from time import sleep
try:
    import pins
    import thread
except ImportError:
    import _thread as thread
    import sys
    sys.path.append('.')
    import pins


class timeOutError(pins.Error):
    """
    Class for error exception
    """
    def __init__(self, message='Error rasied though a timeout'):
        # Call the base class constructor with the parameters it needs
        super(timeOutError, self).__init__(message)

class Test():

    def __init__(self):
        pass

    def quitFunction(self, fnName):
        # print to stderr, unbuffered in Python 2.
        print('{0} took too long'.format(fnName), file=sys.stderr)
        sys.stderr.flush() # Python 3 stderr is likely buffered.
        # thread.exit()
        # raise timeOutError()
        
        thread.interrupt_main() # raises KeyboardInterrupt

    def exit_after(s):
        '''
        use as decorator to exit process if 
        function takes longer than s seconds
        '''
        def outer(fn):
            def inner(self, *args, **kwargs):
                timer = threading.Timer(s, self.quitFunction, args=[fn.__name__])
                timer.start()
                try:
                    result = fn(*args, **kwargs)
                finally:
                    timer.cancel()
                return result
            return inner
        return outer
    
    @exit_after(60)
    def countdown(n):
        print('countdown started', flush=True)
        for i in range(n, -1, -1):
            print(i, end=', ', flush=True)
            sleep(1)
        print('countdown finished')


# This is the usage method. Take note of the error handling
def main():
    '''
    Main program function
    '''
    try:    
        try:
            test = Test()
            test.countdown(6)
            x = 0
        except KeyboardInterrupt:
            print('do something else')
            x = 1
        if x:
            sleep(2)
            raise timeOutError()
            # raise timeOutError()
    except KeyboardInterrupt or timeOutError as e:
        print(e)
        print("Program has entered second exception")
    finally:
        print("Program has now completed")

if __name__ == "__main__":
    main()