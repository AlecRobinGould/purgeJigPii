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

# Python 2 support? probably will delete
try:
    import thread
except ImportError:
    import _thread as thread

class customDecorators(object):

    def __init__(self, log):
        self.log = log

    def quitFunction(self, fnName):
        """
        method closing off thread

        :param self: object from the parent (this)
        :type self: object
        :param fnName: name of the parent function that calls the decorator where fn is the member function
        :type fnName: string
        :return: None
        :rtype: None
        :raises KeyboardInterrupt: Keyboard interrupt
        """
        # print to stderr, unbuffered in Python 2.
        # print('{0} took too long'.format(fnName), file=sys.stderr)
        self.purgeLog.logger('error','{0} took too long'.format(fnName))
        # sys.stderr.flush() # Python 3 stderr is likely buffered.
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
                # print("The time limit is: {}".format(timeLimit))
                self.purgeLog.logger('debug','The time limit is: {}'.format(timeLimit))
                timer = threading.Timer(timeLimit, customDecorators.quitFunction, args=[self, fn.__name__])
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