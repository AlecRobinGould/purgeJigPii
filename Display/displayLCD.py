#!/usr/bin/env python

import platform
import re

# LCD Address
ADDRESS = 0x27

# import smbus
from smbus2 import SMBus
from time import sleep

class i2c_device:
   def __init__(self, addr):
      self.addr = addr
      bus = 1
      I2CBUS = bus # defualt?

      if bus is not None:
          I2CBUS = bus
      else:
          # detect the device that is being used
          device = platform.uname()[1]
          if device == "orangepione":  # orange pi one
              I2CBUS = 0
          elif device == "orangepiplus":  # orange pi plus
              I2CBUS = 0
          elif device == "orangepipcplus":  # orange pi pc plus
              I2CBUS = 0
          elif device == "linaro-alip":  # Asus Tinker Board
              I2CBUS = 1
          elif device == "bpi-m2z":  # Banana Pi BPI M2 Zero Ubuntu
              I2CBUS = 0
          elif device == "bpi-iot-ros-ai":  # Banana Pi BPI M2 Zero Raspbian
              I2CBUS = 0
          elif device == "raspberrypi":  # running on raspberry pi
              # detect i2C port number and assign to I2CBUS
              for line in open('/proc/cpuinfo').readlines():
                  model = re.match('(.*?)\\s*:\\s*(.*)', line)
                  if model:
                      (name, value) = (model.group(1), model.group(2))
                      if name == "Revision":
                          if value[-4:] in ('0002', '0003'):
                              I2CBUS = 0  # original model A or B
                          else:
                              I2CBUS = 1  # later models
                          break
      
      try:
          self.bus = SMBus(I2CBUS)
      except IOError:
          print("You likely didnt enable I2C yet")
          raise 'Could not open the I2C bus'

      

# Write a single command
   def write_cmd(self, cmd):
      self.bus.write_byte(self.addr, cmd)
      # sleep(0.00015)
      sleep(0.0002)

# Write a command and argument
   def write_cmd_arg(self, cmd, data):
      self.bus.write_byte_data(self.addr, cmd, data)
      sleep(0.0001)

# Write a block of data
   def write_block_data(self, cmd, data):
      self.bus.write_block_data(self.addr, cmd, data)
      sleep(0.0001)

# Read a single byte
   def read(self):
      return self.bus.read_byte(self.addr)

# Read
   def read_data(self, cmd):
      return self.bus.read_byte_data(self.addr, cmd)

# Read a block of data
   def read_block_data(self, cmd):
      return self.bus.read_block_data(self.addr, cmd)


# commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

# flags for display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

# flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

# flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

# flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10DOTS = 0x04
LCD_5x8DOTS = 0x00

# flags for backlight control
LCD_BACKLIGHT = 0x08
LCD_NOBACKLIGHT = 0x00

En = 0b00000100 # Enable bit
Rw = 0b00000010 # Read/Write bit
Rs = 0b00000001 # Register select bit

class lcd:
   #initializes objects and lcd
   def __init__(self):
      self.lcd_device = i2c_device(ADDRESS)

      self.lcd_write(0x03)
      self.lcd_write(0x03)
      self.lcd_write(0x03)
      self.lcd_write(0x02)

      self.lcd_write(LCD_FUNCTIONSET | LCD_2LINE | LCD_5x8DOTS | LCD_4BITMODE)
      self.lcd_write(LCD_DISPLAYCONTROL | LCD_DISPLAYON)
      self.lcd_write(LCD_CLEARDISPLAY)
      self.lcd_write(LCD_ENTRYMODESET | LCD_ENTRYLEFT)
      sleep(0.2)

   #  clocks EN to latch command
   def lcd_strobe(self, data):
      self.lcd_device.write_cmd(((data & ~En) | LCD_BACKLIGHT))
      sleep(0.00005)
      self.lcd_device.write_cmd(data | En | LCD_BACKLIGHT)
      sleep(0.00005)
      self.lcd_device.write_cmd(((data & ~En) | LCD_BACKLIGHT))
      sleep(0.0001)

   def lcd_write_four_bits(self, data):
      self.lcd_device.write_cmd(data | LCD_BACKLIGHT)
      self.lcd_strobe(data)

   # write a command to lcd
   def lcd_write(self, cmd, mode=0):
      self.lcd_write_four_bits(mode | (cmd & 0xF0))
      self.lcd_write_four_bits(mode | ((cmd << 4) & 0xF0))

   # write a character to lcd (or character rom) 0x09: backlight | RS=DR<
   # works!
   def lcd_write_char(self, charvalue, mode=1):
      self.lcd_write_four_bits(mode | (charvalue & 0xF0))
      self.lcd_write_four_bits(mode | ((charvalue << 4) & 0xF0))
  
   # put string function with optional char positioning
   def lcd_display_string(self, string, line=1, pos=0):
      pos_new = pos
      if line == 1:
         pos_new = pos
      elif line == 2:
         pos_new = 0x40 + pos
      elif line == 3:
         pos_new = 0x14 + pos
      elif line == 4:
         pos_new = 0x54 + pos
      try:
         self.lcd_write(0x80 + pos_new)

         for char in string:
           self.lcd_write(ord(char), Rs)
      except Exception as e:
         # Failed to write to display. Keep on trying, dont exit
         # When main program is reset, the display will work as normal
         pass

   # clear lcd and set to home
   def lcd_clear(self):
      self.lcd_write(LCD_CLEARDISPLAY)
      self.lcd_write(LCD_RETURNHOME)

   # define backlight on/off (lcd.backlight(1); off= lcd.backlight(0)
   def backlight(self, state): # for state, 1 = on, 0 = off
      """
      for state, 1 = on, 0 = off
      """
      if state == 1:
         self.lcd_device.write_cmd(LCD_BACKLIGHT)
      elif state == 0:
         self.lcd_device.write_cmd(LCD_NOBACKLIGHT)
         self.lcd_device.write_cmd(LCD_DISPLAYOFF)

   # add custom characters (0 - 7)
   def lcd_load_custom_chars(self, fontdata):
      self.lcd_write(0x40);
      for char in fontdata:
         for line in char:
            self.lcd_write_char(line)         # i2c bus (0 -- original Pi, 1 -- Rev 2 Pi)