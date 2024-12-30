#!/usr/bin/env python
# MFRC522
# requests

import RPi.GPIO as GPIO
from SimplerMFRC522 import *
import time
import threading

from LCD import LCD

import queue
from queue import Empty
import spidev
import requests

import config

GPIO.setmode(GPIO.BCM)

session = requests.Session()
state = {
	"bind_user": None # The id of the user to bind to the next scanned card, if not None
}

# ------------------------------------------------------------------------------

spi_lock = threading.Lock()

def card_thread(bus_id, device_id, reset_pin, lcd_queue, callback):

	spi_lock.acquire()
	reader = SimplerMFRC522(bus=bus_id, device=device_id, pin_rst=reset_pin)
	spi_lock.release()

	id_prev = None

	while True:

		spi_lock.acquire()

		id = reader.read_id_no_block()

		if id != id_prev:
			if id is not None:
				callback(id, lcd_queue)
			id_prev = id

		spi_lock.release()

		time.sleep(0.5)

def card_entry(id, lcd_queue):
	print("Entry card:", id)

	if state["bind_user"] != None:

		response = session.get(f'{config.server_ip}/card_bind/{id}')
		print("Response:", response.status_code, response.text)

		if response.status_code == 200:
			lcd_queue.put((config.lang["auth_ok_1"].format(name=response.text), config.lang["auth_ok_2"].format(name=response.text)))
			door_queue.put(None)
		elif response.status_code == 431:
			lcd_queue.put((config.lang["bind_fail_inuse_1"], config.lang["bind_fail_inuse_2"]))
		else:
			lcd_queue.put((config.lang["bind_fail_generic_1"], config.lang["bind_fail_generic_2"]))

		state["bind_user"] = None

	else:

		lcd_queue.put((config.lang["card_loading"], ""))

		response = session.get(f'{config.server_ip}/card/{id}')
		print("Response:", response.status_code, response.text)

		if response.status_code == 200:
			lcd_queue.put((config.lang["auth_ok_1"].format(name=response.text), config.lang["auth_ok_2"].format(name=response.text)))
			door_queue.put(None)
		else:
			lcd_queue.put((config.lang["card_wrong_1"], config.lang["card_wrong_2"]))


def card_exit(id, lcd_queue):
	print("Exit card:", id)


# ------------------------------------------------------------------------------

i2c_lock = threading.Lock()
LCD_queue_entry = queue.Queue()
LCD_queue_exit = queue.Queue()

def LCD_thread(i2c_addr, queue):

	i2c_lock.acquire()
	lcd = LCD(2, i2c_addr, True)
	i2c_lock.release()
	queue.put((config.lang["welcome_1"], config.lang["welcome_2"]))

	inactivity_timeout = 5

	while True:
		try:
			(top, bottom) = queue.get(block=True, timeout=inactivity_timeout)

			if top != None:
				i2c_lock.acquire()
				lcd.message(top.ljust(16, " "), 1)
				i2c_lock.release()

			if bottom != None:
				i2c_lock.acquire()
				lcd.message(bottom.ljust(16, " "), 2)
				i2c_lock.release()

		except Empty:
			# Inactivity timeout
			i2c_lock.acquire()
			lcd.message(config.lang["welcome_1"].ljust(16, " "), 1)
			lcd.message(config.lang["welcome_2"].ljust(16, " "), 2)
			i2c_lock.release()

import board
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

def OLED_display_text(oled, oled_top, oled_bottom):
	image = Image.new("1", (oled.width, oled.height))
	draw = ImageDraw.Draw(image)

	font = ImageFont.load_default()

	draw.text((10, 18), oled_top, font=font, fill=255)
	draw.text((10, 34), oled_bottom, font=font, fill=255)

	oled.image(image)
	oled.show()


def OLED_thread(i2c_addr, queue):

	i2c_lock.acquire()

	i2c = busio.I2C(board.SCL, board.SDA)
	oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=i2c_addr)
	oled_top = None
	oled_bottom = None

	oled.fill(0)
	oled.show()

	i2c_lock.release()
	queue.put((config.lang["welcome_1"], config.lang["welcome_2"]))

	inactivity_timeout = 5

	while True:
		try:
			(top, bottom) = queue.get(block=True, timeout=inactivity_timeout)

			if top != None:
				oled_top = top

			if bottom != None:
				oled_bottom = bottom

			i2c_lock.acquire()
			OLED_display_text(oled, oled_top, oled_bottom)
			i2c_lock.release()

		except Empty:
			# Inactivity timeout
			i2c_lock.acquire()
			OLED_display_text(oled, config.lang["welcome_1"], config.lang["welcome_2"])
			i2c_lock.release()

# ------------------------------------------------------------------------------

def keyboard_thread(bus_id, i2c_addr, lcd_queue, update_callback, cancel_callback, submit_callback):
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
							cancel_callback(buffer, lcd_queue)
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

	finally:
		i2c_lock.release()

def code_entry_update(code, lcd_queue):
	lcd_queue.put((config.lang["code_controls"], "> " + "*" * len(code)))
	print("Entry code:", code)

def code_entry_submit(code, lcd_queue):
	print("Entry code submit:", code)

	lcd_queue.put((config.lang["code_loading"], None))

	response = session.get(f'{config.server_ip}/code/{code}')
	print("Response:", response.status_code, response.text)

	if response.status_code == 200:
		print("Cookies:", session.cookies.get_dict())
		state["bind_user"] = session.cookies.get_dict().get("bind_user", None)
		if state["bind_user"] != None:
			lcd_queue.put((config.lang["card_bind_1"], config.lang["card_bind_2"]))
		else:
			lcd_queue.put((config.lang["auth_ok_1"].format(name=response.text), config.lang["auth_ok_2"].format(name=response.text)))
			door_queue.put(None)
	else:
		lcd_queue.put((config.lang["code_wrong_1"], config.lang["code_wrong_2"]))

def code_exit_update(code, lcd_queue):
	lcd_queue.put((config.lang["code_controls"], "> " + "*" * len(code)))
	print("Exit code:", code)

def code_exit_submit(code, lcd_queue):
	print("Exit code submit:", code)

def code_cancel(code, lcd_queue):
	code_exit_update(code, lcd_queue)
	#lcd_queue.put((config.lang["welcome_1"], config.lang["welcome_2"]))
	print("Exit code cancel")

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
			print("Door Opened!")
			GPIO.output(door_pin, GPIO.HIGH)
			buzz(p, 3)
			GPIO.output(door_pin, GPIO.LOW)
			print("Door Closed!")
	finally:
		p.stop()
		GPIO.output(door_pin, GPIO.LOW)

def buzz(p, t=0.5):
	try:
		p.start(0)
		for dc in range(0, 101, 5):
			p.ChangeDutyCycle(dc)
			time.sleep(t/20)
	finally:
		p.stop()

# ------------------------------------------------------------------------------

try:
	thread_reader_entry = threading.Thread(target=card_thread, group=None, args=[0, 0, 23, LCD_queue_entry, card_entry])
	thread_reader_entry.start()

	thread_reader_exit = threading.Thread(target=card_thread, group=None, args=[0, 1, 24, LCD_queue_entry, card_exit])
	thread_reader_exit.start()

	thread_lcd_entry = threading.Thread(target=LCD_thread, group=None, args=[0x27, LCD_queue_entry])
	thread_lcd_entry.start()

	thread_oled_exit = threading.Thread(target=OLED_thread, group=None, args=[0x3c, LCD_queue_exit])
	thread_oled_exit.start()

	thread_door = threading.Thread(target=door_thread, group=None)
	thread_door.start()

	thread_keyboard_entry = threading.Thread(target=keyboard_thread, group=None, args=[1, 0x20, LCD_queue_entry, code_entry_update, code_cancel, code_entry_submit])
	thread_keyboard_entry.start()

	thread_keyboard_exit = threading.Thread(target=keyboard_thread, group=None, args=[1, 0x24, LCD_queue_exit, code_exit_update, code_cancel, code_exit_submit])
	thread_keyboard_exit.start()

	print("Ready!")

	thread_reader_entry.join()
	thread_reader_exit.join()
	thread_lcd_entry.join()
	thread_oled_exit.join()
	thread_door.join()
	thread_keyboard_entry.join()
	thread_keyboard_exit.join()

finally:
	GPIO.cleanup()
