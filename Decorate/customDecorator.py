#!/usr/bin/env python

"""
================================================

Requires modules from "List of dependencies.txt"
================================================
"""
from __future__ import print_function
import sys
import threading
from time import sleep

# Python 2 support?
try:
    import thread
except ImportError:
    import _thread as thread

class customDecorators():

    def __init__(self):
        pass

    def quitFunction(fnName):
        # print to stderr, unbuffered in Python 2.
        print('{0} took too long'.format(fnName), file=sys.stderr)
        sys.stderr.flush() # Python 3 stderr is likely buffered.
        # thread.exit()
        # raise timeOutError()
        thread.interrupt_main() # raises KeyboardInterrupt

    def exitAfter(s):
        '''
        use as decorator to exit process if 
        function takes longer than s number seconds
        '''
        # print(s)

        def outer(fn):
            def inner(self, *args, **kwargs):
                timeLimit = int(getattr(self, s))
                print("The time limit is: {}".format(timeLimit))
                timer = threading.Timer(timeLimit, customDecorators.quitFunction, args=[fn.__name__])
                timer.start()
                try:
                    result = fn(self, *args, **kwargs)
                finally:
                    timer.cancel()
                return result
            return inner
        return outer
"""
    # Usage example as a countdown timer
    @exitAfter(3)
    def countdown(n):
        print('countdown started', flush=True)
        for i in range(n, -1, -1):
            print(i, end=', ', flush=True)
            sleep(1)
        print('countdown finished')
"""