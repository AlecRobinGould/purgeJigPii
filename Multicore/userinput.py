import sys
import select
import tty
import termios
import time
from multiprocessing import Array, Queue

class remoteUserInput(object):
    def __init__(self, sharedBools, std):
        self.sharedBools = sharedBools
        self.std = std
        
    def __isData(self):
        return select.select([self.std ], [], [], 0) == ([self.std ], [], [])
    
    def readTerm(self, queue):
        sys.stdin = os.fdopen(self.std.fileno())
        old_settings = termios.tcgetattr(sys.stdin)
        print("Past old settings")
        try:
            print("try")
        
            tty.setcbreak(sys.stdin.fileno())
            
            i = 0
            
            v = ''
            remoteStartFlag = False
            remoteStopFlag = False
            remoteResetFlag = False
            remoteRebootFlag = False
            remoteShutdownFlag = False
            # self.sharedBools = Array('b', [False, False, False, False, False, False]) # start, stop, reset, error, shutdown, over pressure flags

            while True:
                i += 1

                with self.sharedBools.get_lock():
                    remoteStartFlag = self.sharedBools[0]
                    remoteStopFlag = self.sharedBools[1]
                    remoteResetFlag = self.sharedBools[2]
                    remoteShutdownFlag = self.sharedBools[4]
                    remoteRebootFlag = self.sharedBools[6]
                    errorcheck = self.sharedBools[3]
                
                if self.__isData():
                    c = sys.stdin.read(1)
                    v = v + c
                    if c == '\x1b':         # x1b is ESC
                        break
                    elif v.__contains__('start\n') or v.__contains__('Start\n') or v.__contains__('START\n'):
                        print("start")
                        with self.sharedBools.get_lock():
                            errorcheck = self.sharedBools[3]
                        if errorcheck:
                            pass
                        else:
                            if remoteStartFlag:
                                pass
                            else:
                                with self.sharedBools.get_lock():
                                    self.sharedBools[0] = True
                                    self.sharedBools[1] = False
                                remoteStartFlag = True
                                remoteStopFlag = False
                        v = ''

                    elif v.__contains__('stop\n') or v.__contains__('Stop\n') or v.__contains__('STOP\n'):
                        print("stop")
                        with self.sharedBools.get_lock():
                            errorcheck = self.sharedBools[3]
                        if errorcheck:
                            pass
                        else:
                            if remoteStopFlag:
                                with self.sharedBools.get_lock():
                                    self.sharedBools[1] = False
                                remoteStopFlag = False

                                with self.sharedBools.get_lock():
                                    self.sharedBools[0] = True
                                remoteStartFlag = True
                            else:
                                pass
                        v = ''
                    elif v.__contains__('reset\n') or v.__contains__('Reset\n') or v.__contains__('RESET\n'):
                        print("reset")
                        with self.sharedBools.get_lock():
                            errorcheck = self.sharedBools[3]
                        if errorcheck:
                            pass
                        else:
                            remoteStartFlag = False
                            remoteStopFlag = False
                            remoteResetFlag = True
                            with self.sharedBools.get_lock():
                                self.sharedBools[0] = False
                                self.sharedBools[1] = False
                                self.sharedBools[2] = True
                        v = ''
                    elif v.__contains__('shutdown\n') or v.__contains__('Shutdown\n') or v.__contains__('SHUTDOWN\n'):
                        print("shutdown")
                        with self.sharedBools.get_lock():
                            errorcheck = self.sharedBools[3]
                        if errorcheck:
                            pass
                        else:
                            with self.sharedBools.get_lock():
                                self.sharedBools[4] = True
                        v = ''
                    elif v.__contains__('reboot\n') or v.__contains__('Reboot\n') or v.__contains__('REBOOT\n'):
                        print("reboot")
                        with self.sharedBools.get_lock():
                            errorcheck = self.sharedBools[3]
                        if errorcheck:
                            pass
                        else:
                            remoteRebootFlag = True
                            with self.sharedBools.get_lock():
                                self.sharedBools[4] = True
                        v = ''
                    elif len(v) > 10 or c.__contains__(' ') or v.__contains__('\n'):
                        v = ''
        except Exception as e:
            print(e)
        finally:
            termios.tcsetattr(sys.stdin , termios.TCSADRAIN, old_settings)

def main():

    sharedTest = Array('b', [False, False, False, False, False, False, False])
    mpqueue = Queue()   
    x = sys.stdin
    test = remoteUserInput(sharedTest, x)

    test.readTerm(mpqueue)


if __name__ == "__main__":
    main()
