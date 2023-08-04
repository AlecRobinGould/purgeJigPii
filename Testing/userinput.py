import sys
import select
import tty
import termios
import time

def isData():
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

old_settings = termios.tcgetattr(sys.stdin)
try:
    tty.setcbreak(sys.stdin.fileno())

    i = 0
    v = ''
    while 1:
        print(i)
        time.sleep(1)
        i += 1
        
        if isData():
            c = sys.stdin.read(1)
            v = v + c
            # print(v)
            if c == '\x1b':         # x1b is ESC
                break
            elif v.__contains__('start\n'):
                print("START")
                v = ''
            elif v.__contains__('stop\n'):
                print("STOP")
                v = ''
            elif v.__contains__('reset\n'):
                print("RESET")
                v = ''
            elif len(v) > 10 or c.__contains__(' ') or v.__contains__('\n'):
                v = ''
except KeyboardInterrupt:
    pass
finally:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)