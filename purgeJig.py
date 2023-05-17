import pins
import time
# from loggingdebug import log

def main():
    '''
    Main program function
    '''
    test = pins.logicPins('testing')

    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()