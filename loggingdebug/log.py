import logging
from time import strftime

class log():

    def __init__(self):    
        # set up logging to file - see previous section for more details
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                            datefmt='%d-%m-%y %H:%M',
                            filename='/home/antlabpi/purgeJig/loggingdebug/{}.log'.format(strftime('%d-%m-%y')) ,
                            filemode='a')
        # define a Handler which writes INFO messages or higher to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        # set a format which is simpler for console use
        formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
        # tell the handler to use this format
        console.setFormatter(formatter)
        # add the handler to the root logger
        logging.getLogger('').addHandler(console)
    
    def logger(self, logtype='debug', message='default'):

        
        
        if logtype == 'error':
            logging.error(message)
        elif logtype == 'warning':
            logging.warning(message)
        elif logtype == 'info':
            logging.info(message)
        elif logtype == 'debug':
            print('logtype is: {}'.format(logtype))
            print('message is: {}'.format(message))
            logging.debug(message)
        else:
            logging.warning('Logger has been used out of condition')


# def main():
    # '''
    # Main program function
    # '''
    # DEBUG = log()
    # DEBUG.logger('debug', 'This is a test')
    # DEBUG.logger('warning', 'This is a warning')
    # DEBUG.logger('info', 'This is info')
    # DEBUG.logger('error', 'This is an error')
# 
# if __name__ == "__main__":
    # main()