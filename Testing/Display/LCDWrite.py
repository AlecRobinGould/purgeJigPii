import displayLCD
import time
display = displayLCD.lcd()

while True:
    display.lcd_display_string("Time: %s" %time.strftime("%H:%M:%S"), 1)
    display.lcd_display_string("Date: %s" %time.strftime("%m/%d/%Y"), 2)