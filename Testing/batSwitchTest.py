import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
batteryPin = 19
batState = False
GPIO.setup(batteryPin,GPIO.OUT)



def batToggle(batState, batteryPin):

        GPIO.output(batteryPin, batState)
        print("State is in: ", batState)



if __name__ == "__main__":
        while True:

                batToggle(batState, batteryPin)

                batState = not batState
                print("State is in: ", batState)

                time.sleep(10)
    