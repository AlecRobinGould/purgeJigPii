try:
    import purge
    from purge import time, GPIO, os
    import sys
    # import RPi.GPIO as GPIO
except ImportError:
    try:
        import sys
        sys.path.append('.')
        import purge
    except ImportError:
        raise ImportError(
            "Failed to import library from parent folder")

# This is the usage method. Take note of the error handling
def main():
    '''
    Main program function
    '''
    f = sys.stdin
    test = None
    try:
        test = purge.purge(5,'idle', f)
    except Exception as k:
        print(k)
        if k == '[Errno 110] Connection timed out':
            os.system("sudo shutdown now -h")
        else:
            # test.runrun.purgeLog.logger('error', 'Error: {}'.format(e))
            # shutDownText1 = "SHUTTING DOWN DEVICE"
            # shutDownText2 = "GOODBYE!"
            # test.runrun.display.lcd_display_string(shutDownText1, 2, test.runrun.centreText(shutDownText1))
            # test.runrun.display.lcd_display_string(shutDownText2, 3, test.runrun.centreText(shutDownText2))
            # time.sleep(2)
            # shutDownText3 = "SHUTDOWN SUCCESS!"
            # test.runrun.display.lcd_clear()
            # test.runrun.display.lcd_display_string(shutDownText3, 2, test.runrun.centreText(shutDownText3))
            # time.sleep(2)
            os.system("sudo shutdown now -h")

    try:
        test.runPurge()
        time.sleep(1)
        print("program has ended")
        
    except KeyboardInterrupt:
        test.runrun.setIdle()
        test.runrun.display.lcd_clear()
        test.runrun.display.lcd_display_string("Error! Program",1)
        test.runrun.display.lcd_display_string("exited externally.",2)
        test.runrun.display.lcd_display_string("Perform a full power",3)
        test.runrun.display.lcd_display_string("cycle to continue.",4)
        time.sleep(1)
        # GPIO.cleanup()
        # time.sleep(1)

    except purge.faultErrorException as e:
        test.runrun.setIdle()
        test.runrun.purgeLog.logger('error','fault error: {}.'.format(e))
        test.runrun.display.lcd_clear()
        test.runrun.display.lcd_display_string("Error 11! Bat mon",1, 1)
        test.runrun.display.lcd_display_string("major fault.",2, 4)
        test.runrun.display.lcd_display_string("Perform shutdown,",3, 1)
        test.runrun.display.lcd_display_string("and view logs.",4 ,3)
        test.runrun.toggleBeep(1)
        time.sleep(10)
        # GPIO.cleanup()
        
    # Catch any uncaught exceptions
    except Exception as e:
        test.runrun.setIdle()
        test.runrun.purgeLog.logger('error','Uncaught exception crept through: {}.'.format(e))
        test.runrun.display.lcd_clear()
        test.runrun.display.lcd_display_string("Error! Program",1)
        test.runrun.display.lcd_display_string("exited externally.",2)
        test.runrun.display.lcd_display_string("Perform a full power",3)
        test.runrun.display.lcd_display_string("cycle to continue.",4)
        test.runrun.toggleBeep(1)
        time.sleep(10)
        # GPIO.cleanup()
        
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()