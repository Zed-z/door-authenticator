#!/usr/bin/env python

import RPi.GPIO as GPIO
from aaaMFRC522 import *
import time
import threading
from LCD import LCD
import queue
import spidev

GPIO.setmode(GPIO.BCM)

def card_thread():

	reader1 = SimpleMFRC522(bus=0, device=0, pin_rst=23)
	reader2 = SimpleMFRC522(bus=0, device=1, pin_rst=24)

	id_prev_1 = None
	id_prev_2 = None

	while True:
		#print("Reading 1...")
		id = reader1.read_id_no_block()
		if id != None and id != id_prev_1:
			print("id 1 ", id)
			LCD_queue.put((str(id), "Wejście"))
			door_queue.put(None)
		id_prev_1 = id

		#print("Reading 2...")
		id = reader2.read_id_no_block()
		if id != None and id != id_prev_2:
			print("id 2", id)
			LCD_queue.put((str(id), "Wyjście"))
			door_queue.put(None)
		id_prev_2 = id

		time.sleep(0.5)

LCD_queue = queue.Queue()
def LCD_thread():

	lcd = LCD(2, 0x27, True)
	LCD_queue.put(("Przyloz karte...", "h"))

	while True:
		(top, bottom) = LCD_queue.get()
		if top != None:
			lcd.message(top.ljust(16, " "), 1)
		if bottom != None:
			lcd.message(bottom.ljust(16, " "), 2)


door_queue = queue.Queue()
def door_thread():
	buzzer_pin = 19
	GPIO.setup(buzzer_pin, GPIO.OUT)
	p = GPIO.PWM(buzzer_pin, 500)

	door_pin = 4
	GPIO.setup(door_pin, GPIO.OUT)

	# Init sound
	buzz(p, 0.1)

	try:
		while True:
			door_queue.get()
			GPIO.output(door_pin, GPIO.HIGH)
			buzz(p, 3)
			GPIO.output(door_pin, GPIO.LOW)
	finally:
		p.stop()

def buzz(p, t=0.5):
	print("Buzz")
	try:
		p.start(0)
		for dc in range(0, 101, 5):
			p.ChangeDutyCycle(dc)
			time.sleep(t/20)
		#p.ChangeDutyCycle(50)
		#time.sleep(t/2)
		#p.ChangeDutyCycle(75)
		#time.sleep(t/2)
		#p.ChangeDutyCycle(0)
	finally:
		p.stop()



try:
	t1 = threading.Thread(target=card_thread, group=None)
	t1.start()

	t2 = threading.Thread(target=LCD_thread, group=None)
	t2.start()

	t3 = threading.Thread(target=door_thread, group=None)
	t3.start()

	t1.join()
	t2.join()
	t3.join()

finally:
	GPIO.cleanup()
