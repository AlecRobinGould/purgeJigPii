"""
The purpose of this module of code is to use the same format of my old code, but use the new display library for the new sparkfun display we bought
The function names will be of the old code, and the new code functions get called from the old ones.
"""

try: 
    import newDisplayLCD
    import sys, time, smbus2
except ImportError:
    from Display import newDisplayLCD

ADDRESS = 0x72 # Apparently default address

class lcd:
    def __init__(self):
        self.newDisplay = newDisplayLCD.QwiicSerlcd(ADDRESS)
        if self.newDisplay.begin():
            pass
        else:
            pass

        self.newDisplay.setBacklight(0,255,0)

    def lcd_display_string(self, string, line=0, pos=0):
        try:
            self.newDisplay.setCursor((pos - 0), (line -1))
            self.newDisplay.print(string)
        except IOError:
            try:
                self.newDisplay.setCursor((pos - 0), (line -1))
                self.newDisplay.print(string)
            except:
                pass


    def lcd_clear(self):
        try:
            self.newDisplay.clearScreen()
        except Exception:
            pass

    def backlight(self, state): # for state, 1 = on, 0 = off
        try:
            # pass
            if state == 0:
                # pass
                self.newDisplay.setFastBacklight(255,0,0) # green?
            else:
                # pass
                self.newDisplay.setFastBacklight(0,255,0) # red?
        except Exception:
            pass

""" 
main is not apart of this project repository.
This main function is the inital test of the new display.
The code aims to set the EMSS logo (Name) as the splash screen.
"""
def main():
    myLCD = lcd()
    if myLCD.newDisplay.connected == False:
        print("The Qwiic SerLCD device isn't connected to the system.",file=sys.stderr)
        myLCD.newDisplay.clearScreen()
    myLCD.lcd_clear()
    time.sleep(1)
    myLCD.newDisplay.disableSystemMessages()
    myLCD.newDisplay.noCursor()
    myLCD.newDisplay.noBlink()
    myLCD.newDisplay.leftToRight()
    myLCD.newDisplay.setContrast(contrast=0)
    myLCD.newDisplay.setBacklight(0,0,255)
    # myLCD.lcd_display_string("EMSS", 2, 8)
    # myLCD.lcd_display_string("Antennas", 3, 6)
    # myLCD.newDisplay.setCursor(8, 2)
    myLCD.newDisplay.print("                           ")
    myLCD.newDisplay.print("EMSS")
    myLCD.newDisplay.print("              ")
    # myLCD.newDisplay.setCursor(6, 3)
    myLCD.newDisplay.print("Antennas")
    myLCD.newDisplay.disableSplash()
    time.sleep(5)
    myLCD.newDisplay.saveSplash()
    myLCD.newDisplay.enableSplash()

    # try:
    #     while True:
    #        myLCD.newDisplay.setBacklight(0,0,255)
    #        time.sleep(1)
    #        myLCD.newDisplay.setBacklight(255,0,0)
    #        time.sleep(0.5)

    # except (KeyboardInterrupt, SystemExit) as exErr:
    #     print("\nEnding test through: {}".format(exErr))
    #     sys.exit(0)    

if __name__ == '__main__':
	try:
		main()
	except (KeyboardInterrupt, SystemExit) as exErr:
		print("\nEnding test through: {}".format(exErr))
		sys.exit(0)