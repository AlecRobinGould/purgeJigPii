import sys
import select
import tty
import termios
import time

class remoteUserInput(object):
    def __init__(self, sharedBools, stdIN):
        self.sharedBools = sharedBools
        self.stdIN = stdIN
        

    def __isData(self):
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])
    
    def readTerm(self, queue):
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
                time.sleep(1)
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
                        with self.sharedBools.get_lock():
                            errorcheck = self.sharedBools[3]
                        if errorcheck:
                            pass
                        else:
                            with self.sharedBools.get_lock():
                                self.sharedBools[4] = True
                        v = ''
                    elif v.__contains__('reboot\n') or v.__contains__('Reboot\n') or v.__contains__('REBOOT\n'):
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
        except Exception:
            pass
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

# def main():
#     test = remoteUserInput()

#     test.readTerm()


# if __name__ == "__main__":
#     main()
