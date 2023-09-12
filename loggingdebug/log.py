#!/usr/bin/env python

import logging
import os
from time import strftime

class log():

    def __init__(self):    
        # set up logging to file - see previous section for more details
        basePath = os.path.dirname(os.path.abspath(__file__))
        self.logpath = basePath + '/logfiles/'
        self.logfile = '{}.log'.format(strftime('%d-%m-%y'))
        self.statefile = 'state.log'
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                            datefmt='%d-%m-%y %H:%M',
                            filename=self.logpath+self.logfile ,
                            filemode='a')
        # define a Handler which writes INFO messages or higher to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        # set a format which is simpler for console use
        formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
        # tell the handler to use this format
        console.setFormatter(formatter)
        # add the handler to the root logger
        logging.getLogger('').addHandler(console)
    
    def logger(self, logtype='debug', message='default'):
        """
        Receivers parameters and creates logs in a log file.
        :param logtype : Nature of the information to be logged
        error is serious, warning requires attension and debug is general logs.
        :type logtype : string, optional
        :param message : Information to be logged.        
        :type message : string, optional
        """
        
        if logtype == 'error':
            logging.error(message)
        elif logtype == 'warning':
            logging.warning(message)
        elif logtype == 'info':
            logging.info(message)
        elif logtype == 'debug':
            # print('logtype is: {}'.format(logtype))
            # print('message is: {}'.format(message))
            logging.debug(message)
        else:
            logging.warning('Logger has been used out of condition')

    def checkLogFile(self):
        
        fileName = self.logpath + self.logfile
        try:
            file = open(fileName, "r")
            file.close()
        except:
            return False            
        return True

    def readState(self):
        """
        Opens a file named state and checks file size
        If the file size is 1kb or greater, the last line is copied to a variable,  
        logged to a logfile and returned as a string
        If there are no file contents, an empty string is return (only a string null)
        """
        with open(self.logpath + self.statefile, "rb") as file:
            if os.path.getsize(self.logpath + self.statefile):
                try:
                    file.seek(-2, os.SEEK_END)
                    while file.read(1) != b'\n':
                        file.seek(-2, os.SEEK_CUR)
                except OSError:
                    file.seek(0)
                lastLine = file.readline().decode()
                self.logger('debug', 'Last state recoverd as {}'.format(lastLine))
            else:
                lastLine = ''
                self.logger('debug', 'Last state cannot be recovered')
        return lastLine