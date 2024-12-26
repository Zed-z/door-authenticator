# Adapted code from Simon Monk's (https://github.com/simonmonk/) SimpleMFRC522

from mfrc522 import *
import RPi.GPIO as GPIO

class SimplerMFRC522:

  READER = None

  def __init__(self, bus=0, device=0, pin_rst=-1):
    self.READER = MFRC522(bus=bus, device=device, pin_rst=pin_rst)

  def read_id_no_block(self):
      (status, TagType) = self.READER.MFRC522_Request(self.READER.PICC_REQIDL)
      if status != self.READER.MI_OK:
          return None
      (status, uid) = self.READER.MFRC522_Anticoll()
      if status != self.READER.MI_OK:
          return None
      return self.uid_to_num(uid)

  def uid_to_num(self, uid):
      n = 0
      for i in range(0, 5):
          n = n * 256 + uid[i]
      return n