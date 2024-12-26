#!/usr/bin/env python
# MFRC522
# requests

import RPi.GPIO as GPIO
from SimplerMFRC522 import *
import time
import threading
from LCD import LCD
import queue
import spidev
import requests

GPIO.setmode(GPIO.BCM)

session = requests.Session()
state = {
	"bind_user": None # The id of the user to bind to the next scanned card, if not None
}

# ------------------------------------------------------------------------------

spi_lock = threading.Lock()

def card_thread(bus_id, device_id, reset_pin, callback):

	spi_lock.acquire()
	reader = SimplerMFRC522(bus=bus_id, device=device_id, pin_rst=reset_pin)
	spi_lock.release()

	id_prev = None

	while True:

		spi_lock.acquire()

		id = reader.read_id_no_block()

		if id != id_prev:
			if id is not None:
				callback(id)
			id_prev = id

		spi_lock.release()

		time.sleep(0.5)

def card_entry(id):
	print("Wej", id)

	if state["bind_user"] != None:

		response = session.get(f'http://localhost:5000/card_bind/{id}')
		print(response.status_code)
		if response.status_code == 200:
			LCD_queue_entry.put(("Witaj,", response.text))
			door_queue.put(None)
		else:
			LCD_queue_entry.put(("Zakaz wstepu!", "Zla karta!"))

		state["bind_user"] = None
		
	else:

		response = session.get(f'http://localhost:5000/card/{id}')
		print(response.status_code)
		if response.status_code == 200:
			LCD_queue_entry.put(("Witaj,", response.text))
			door_queue.put(None)
		else:
			LCD_queue_entry.put(("Zakaz wstepu!", "Zla karta!"))


def card_exit(id):
	print("Wyj", id)


# ------------------------------------------------------------------------------

i2c_lock = threading.Lock()
LCD_queue_entry = queue.Queue()
LCD_queue_exit = queue.Queue()

def LCD_thread(i2c_addr, queue):

	i2c_lock.acquire()
	lcd = LCD(2, i2c_addr, True)
	i2c_lock.release()
	queue.put(("Przyloz karte...", "h"))

	while True:
		(top, bottom) = queue.get()

		if top != None:
			i2c_lock.acquire()
			lcd.message(top.ljust(16, " "), 1)
			i2c_lock.release()

		if bottom != None:
			i2c_lock.acquire()
			lcd.message(bottom.ljust(16, " "), 2)
			i2c_lock.release()

# ------------------------------------------------------------------------------

def keyboard_thread(bus_id, i2c_addr, lcd_queue, update_callback, submit_callback):
	from smbus import SMBus
	bus = SMBus(bus_id)

	ROW_COUNT = 4
	COL_COUNT = 3
	KEY_MAP = ["#", "0", "*", "9", "8", "7", "6", "5", "4", "3", "2", "1"]

	buffer = ""

	prev_number = None

	try:
		while True:

			try:
				i2c_lock.acquire()
				number = None

				for col in range(COL_COUNT):
					col_scan = 0xFF & ~(1 << col)
					pin_vals = bus.read_byte_data(i2c_addr, col_scan)

					for row in range(ROW_COUNT):
						if not (pin_vals & ((1 << row) << COL_COUNT)):
							number = row * COL_COUNT + col

				if number != prev_number:
					if number is not None:
						key = KEY_MAP[number]
						if key == "#":
							buffer = ""
							update_callback(buffer, lcd_queue)
						elif key == "*":
							submit_callback(buffer, lcd_queue)
							buffer = ""
						else:
							buffer += key
							update_callback(buffer, lcd_queue)

					prev_number = number
			except OSError as e:
				print("Keyboard thread error - ", e)
			finally:
				i2c_lock.release()

			time.sleep(0.02)

	except KeyboardInterrupt:
		print("Exiting gracefully.")
	finally:
		i2c_lock.release()

def code_entry_update(code, lcd_queue):
	lcd_queue.put(("* OK   # CANCEL", "> " + "*" * len(code)))
	print("Wej:", code)

def code_entry_submit(code, lcd_queue):
	print("!!! Wej:", code)

	response = session.get(f'http://localhost:5000/code/{code}')
	print(response.status_code)
	if response.status_code == 200:
		print("Cookies:", session.cookies.get_dict())
		state["bind_user"] = session.cookies.get_dict().get("bind_user", None)
		if state["bind_user"] != None:
			LCD_queue_entry.put(("Przyloz karte,", "aby przypisac."))
		else:
			LCD_queue_entry.put(("Witaj,", response.text))
			door_queue.put(None)
	else:
		LCD_queue_entry.put(("Zakaz wstepu!", "Zly kod!"))

def code_exit_update(code, lcd_queue):
	lcd_queue.put(("* OK   # CANCEL", "> " + "*" * len(code)))
	print("Wyj:", code)

def code_exit_submit(code, lcd_queue):
	print("!!! Wyj:", code)

# ------------------------------------------------------------------------------

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
	finally:
		p.stop()

# ------------------------------------------------------------------------------

try:
	thread_reader_entry = threading.Thread(target=card_thread, group=None, args=[0, 0, 23, card_entry])
	thread_reader_entry.start()

	thread_reader_exit = threading.Thread(target=card_thread, group=None, args=[0, 1, 24, card_exit])
	thread_reader_exit.start()

	thread_lcd_entry = threading.Thread(target=LCD_thread, group=None, args=[0x27, LCD_queue_entry])
	thread_lcd_entry.start()

	thread_door = threading.Thread(target=door_thread, group=None)
	thread_door.start()

	thread_keyboard_entry = threading.Thread(target=keyboard_thread, group=None, args=[1, 0x20, LCD_queue_entry, code_entry_update, code_entry_submit])
	thread_keyboard_entry.start()

	thread_keyboard_exit = threading.Thread(target=keyboard_thread, group=None, args=[1, 0x24, LCD_queue_exit, code_exit_update, code_exit_submit])
	thread_keyboard_exit.start()

	thread_reader_entry.join()
	thread_reader_exit.join()
	thread_lcd_entry.join()
	thread_door.join()
	thread_keyboard_entry.join()
	thread_keyboard_exit.join()

finally:
	GPIO.cleanup()
