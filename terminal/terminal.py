#region Moduły
import RPi.GPIO as GPIO
import time
import threading
import queue
from queue import Empty
import requests
from unidecode import unidecode

GPIO.setmode(GPIO.BCM)
#enregion

#region CONFIG -----------------------------------------------------------------

class Config():
	def __init__(self, lang):

		# Podstawowa konfiguracja
		self.server_ip = "http://localhost:5000"
		self.inactivity_timeout = 5
		self.buzzer_mute = False

		# Komunikaty w języku polskim, możliwość innych języków
		self.lang_pl = {
			"welcome_1":				"--System Drzwi--",
			"welcome_2":				" KARTA  //  KOD ",

			"code_controls":			"* OK    # ANULUJ",
			"code_loading":				"Czekaj...",
			"code_wrong_1":				"Zakaz wstepu!",
			"code_wrong_2":				"Niepopr. kod!",

			"code_no_user_1":			"Zakaz wstepu!",
			"code_no_user_2":			"Użyt. nie istn.!",

			"card_loading":				"Czekaj...",
			"card_wrong_1":				"Zakaz wstepu!",
			"card_wrong_2":				"Niepopr. karta!",

			"outside_hours_1":			"Zakaz wstepu!",
			"outside_hours_2":			"Poza godzinami!",

			"user_limit_1":				"Zakaz wstepu!",
			"user_limit_2":				"Przeludnienie!",

			"not_in_room_1":			"Zakaz wstepu!",
			"not_in_room_2":			"Nie jest w sali!",

			"unknown_error_1":			"Zakaz wstepu!",
			"unknown_error_2":			"Nieznany blad!",

			"card_bind_1":				"Przyloz karte,",
			"card_bind_2":				"aby przypisac...",

			"auth_ok_1":				"Witaj, {name}!",
			"auth_ok_2":				"Drzwi otwarte.",

			"bind_fail_generic_1":		"Rej. nieudana!",
			"bind_fail_generic_2":		"Sprob. ponownie!",

			"bind_fail_inuse_1":		"Rej. nieudana!",
			"bind_fail_inuse_2":		"Karta w uzyciu!",

			"bind_no_user_1":			"Rej. nieudana!",
			"bind_no_user_2":			"Użyt. nie istn.!",
		}

		# Ustawienie aktywnego języka
		if lang == "pl":
			self.lang = self.lang_pl
		else:
			self.lang = self.lang_pl

#endregion ---------------------------------------------------------------------

#region Współdzielone zmienne --------------------------------------------------

# Zamki dla magirstrali
i2c_lock = threading.Lock()
spi_lock = threading.Lock()

# Kolejki do wymiany komunikatów między wątkami
LCD_queue_entry = queue.Queue()
LCD_queue_exit = queue.Queue()
door_queue = queue.Queue()

# Obiekt konfiguracji
config = Config("pl")

# Dane sesji
session = requests.Session() # Obiekt sesji, m.in. na ciasteczka
state = {
	"bind_user": None # ID użytkownika do przypisywania karty
}

#endregion ---------------------------------------------------------------------

#region Uwierzytelnianie kartą -------------------------------------------------

from mfrc522 import *

# Wątek odczytujący kartę
def card_thread(bus_id, device_id, reset_pin, lcd_queue, callback):

	# Utworzenie obiektu czytnika
	# Uwaga: obchodzimy domyślną funkcję __init__, gdyż jest ona zbyt uproszczona
	# i nie umożliwia korzystanie z wielu czytników jednocześnie
	spi_lock.acquire()
	reader = SimpleMFRC522.__new__(SimpleMFRC522)
	reader.READER = MFRC522(bus=bus_id, device=device_id, pin_rst=reset_pin)
	spi_lock.release()

	id_prev = None

	# Główna pętla programu
	while True:
		spi_lock.acquire()
		id = reader.read_id_no_block()

		if id != id_prev:
			if id is not None:
				# Odczytano kod, wywołaj funkcję z argumentami
				callback(id, lcd_queue)
			id_prev = id

		spi_lock.release()
		time.sleep(0.5)

# Funkcja wysyłająca zapytanie do serwera w celu odblokowania drzwi
def card_unlock(id, lcd_queue, type):

	# Wyświetl wiadomość o ładowaniu
	lcd_queue.put((config.lang["card_loading"], ""))

	# Wyślij zapytanie
	response = session.get(f'{config.server_ip}/card/{id}?type={type}')
	print("Response:", response.status_code, response.text)

	# Zinterpretuj zwrócony kod
	if response.status_code == 200: # Sukces
		lcd_queue.put((config.lang["auth_ok_1"].format(name=unidecode(response.text)), config.lang["auth_ok_2"].format(name=unidecode(response.text))))
		door_queue.put(None)
	else:
		if response.status_code == 423: # Poza dozwolonymi godzinami
			lcd_queue.put((config.lang["outside_hours_1"], config.lang["outside_hours_2"]))
		elif response.status_code == 421: # Za dużo osób w pomieszczeniu
			lcd_queue.put((config.lang["user_limit_1"], config.lang["user_limit_2"]))
		elif response.status_code == 422: # Próbuje wyjść, ale wcześniej nie wszedł
			lcd_queue.put((config.lang["not_in_room_1"], config.lang["not_in_room_2"]))
		elif response.status_code == 420: # Niewłaściwa karta
			lcd_queue.put((config.lang["card_wrong_1"], config.lang["card_wrong_2"]))
		else: # Nieznany błąd
			lcd_queue.put((config.lang["unknown_error_1"], config.lang["unknown_error_2"]))

# Funkcja wysyłająca zapytanie do serwera w celu przypisania karty do użytkownika
def card_bind(id, lcd_queue):

	# Wyświetl wiadomość o ładowaniu
	lcd_queue.put((config.lang["card_loading"], ""))

	# Wyślij zapytanie
	response = session.get(f'{config.server_ip}/card_bind/{id}')
	print("Response:", response.status_code, response.text)

	# Zinterpretuj zwrócony kod
	if response.status_code == 200: # Sukces
		lcd_queue.put((config.lang["auth_ok_1"].format(name=unidecode(response.text)), config.lang["auth_ok_2"].format(name=unidecode(response.text))))
	elif response.status_code == 431: # Karta jest używana przez kogoś innego
		lcd_queue.put((config.lang["bind_fail_inuse_1"], config.lang["bind_fail_inuse_2"]))
	elif response.status_code == 432: # Nie przesłano użytkownika
		lcd_queue.put((config.lang["bind_no_user_1"], config.lang["bind_no_user_2"]))
	elif response.status_code == 433: # Nie ma takiego użytkownika
		lcd_queue.put((config.lang["bind_no_user_1"], config.lang["bind_no_user_2"]))
	else: # Nieznany błąd
		lcd_queue.put((config.lang["bind_fail_generic_1"], config.lang["bind_fail_generic_2"]))

# Funkcja wywoływana przez wątek czytający karty na wejściu
def card_entry(id, lcd_queue):
	print("Entry card:", id)

	# Spróbuj przypisać kartę (jeśli jest w trybie przypisywania)
	# lub odblokować drzwi
	if state["bind_user"] != None:
		card_bind(id, lcd_queue)
		state["bind_user"] = None
	else:
		card_unlock(id, lcd_queue, "entry")

# Funkcja wywoływana przez wątek czytający karty na wyjściu
def card_exit(id, lcd_queue):
	print("Exit card:", id)

	# Spróbuj odblokować drzwi
	card_unlock(id, lcd_queue, "exit")

#endregion ---------------------------------------------------------------------

#region Zarządzanie wyświetlaczami LCD i OLED ----------------------------------

from LCD import LCD # https://github.com/sterlingbeason/LCD-1602-I2C/blob/master/LCD.py

# Wątek wyświetlający komunikaty na wyświetlaczu LCD
def LCD_thread(i2c_addr, queue):

	# Utworzenie obiektu LCD
	i2c_lock.acquire()
	lcd = LCD(2, i2c_addr, True)
	i2c_lock.release()

	# Wstępna wiadomość
	queue.put((config.lang["welcome_1"], config.lang["welcome_2"]))

	while True:
		try:
			# Czekaj na komunikaty z wiadomościami
			(top, bottom) = queue.get(block=True, timeout=config.inactivity_timeout)

			# Zaktualizuj górny wiersz
			if top != None:
				i2c_lock.acquire()
				lcd.message(top.ljust(16, " "), 1)
				i2c_lock.release()

			# Zaktualizuj dolny wiersz
			if bottom != None:
				i2c_lock.acquire()
				lcd.message(bottom.ljust(16, " "), 2)
				i2c_lock.release()

		except Empty:
			# Przy nieaktywności, wróć na ekran powitalny
			i2c_lock.acquire()
			lcd.message(config.lang["welcome_1"].ljust(16, " "), 1)
			lcd.message(config.lang["welcome_2"].ljust(16, " "), 2)
			i2c_lock.release()

import board
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

# Funkcja pomocnicza do wyświetlania tekstu na wyświetlaczu OLED
def OLED_display_text(oled, oled_top, oled_bottom):
	image = Image.new("1", (oled.width, oled.height))
	draw = ImageDraw.Draw(image)

	font = ImageFont.load_default()

	draw.text((10, 18), oled_top, font=font, fill=255)
	draw.text((10, 34), oled_bottom, font=font, fill=255)

	oled.image(image)
	oled.show()

# Wątek wyświetlający komunikaty na wyświetlaczu OLED
def OLED_thread(i2c_addr, queue):

	# Utworzenie obiektu OLED
	i2c_lock.acquire()

	i2c = busio.I2C(board.SCL, board.SDA)
	oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=i2c_addr)
	oled_top = None
	oled_bottom = None

	oled.fill(0)
	oled.show()

	i2c_lock.release()

	# Wstępna wiadomość
	queue.put((config.lang["welcome_1"], config.lang["welcome_2"]))

	try:
		while True:
			try:
				# Czekaj na komunikaty z wiadomościami
				(top, bottom) = queue.get(block=True, timeout=config.inactivity_timeout)

				# Zaktualizuj górny wiersz
				if top != None:
					oled_top = top

				# Zaktualizuj dolny wiersz
				if bottom != None:
					oled_bottom = bottom

				# Zaktualizuj tekst na wyświetlaczu
				i2c_lock.acquire()
				OLED_display_text(oled, oled_top, oled_bottom)
				i2c_lock.release()

			except Empty:
				# Przy nieaktywności, wróć na ekran powitalny
				i2c_lock.acquire()
				OLED_display_text(oled, config.lang["welcome_1"], config.lang["welcome_2"])
				i2c_lock.release()
	finally:
		# Sprzątanie po sobie
		oled.fill(0)
		oled.show()

#endregion ---------------------------------------------------------------------

#region Uwierzytelnianie kodem -------------------------------------------------

from smbus import SMBus

# Wątek czytający dane z klawiatury
def keyboard_thread(bus_id, i2c_addr, lcd_queue, update_callback, cancel_callback, submit_callback):

	# Obiekt magistrali
	bus = SMBus(bus_id)

	# Dane klawiszy klawiatury
	ROW_COUNT = 4
	COL_COUNT = 3
	KEY_MAP = ["#", "0", "*", "9", "8", "7", "6", "5", "4", "3", "2", "1"]

	# Bufor na wpisane dane
	buffer = ""

	prev_number = None

	try:
		while True:

			try:
				i2c_lock.acquire()
				number = None

				# Skanuj klawiaturę w poszukiwaniu wciśniętego klawisza
				for col in range(COL_COUNT):
					col_scan = 0xFF & ~(1 << col) # Wyślij same jedynki, z wyzerowaną kolumną sprawdzającą
					pin_vals = bus.read_byte_data(i2c_addr, col_scan) # Odczytaj aktualne dane

					# Znajdź wiersz o wartości zero, to będzie wciśnięty klawisz
					for row in range(ROW_COUNT):
						if not (pin_vals & ((1 << row) << COL_COUNT)):
							number = row * COL_COUNT + col

				# Znaleziono klawisz
				if number != prev_number:
					if number is not None:
						key = KEY_MAP[number]

						# Anuluj - wyczyszczenie wejścia
						if key == "#":
							buffer = ""
							cancel_callback(buffer, lcd_queue)

						# OK - zatwierdzenie wejścia
						elif key == "*":
							submit_callback(buffer, lcd_queue)
							buffer = ""

						# Zaktualizowanie wejścia
						else:
							buffer += key
							update_callback(buffer, lcd_queue)

					prev_number = number

			# Obsługa wyjątków
			except OSError as e:
				print("Keyboard thread error - ", e)
			finally:
				# Czyszczenie po sobie
				i2c_lock.release()

			# Opóźnienie przed kolejnym pomiarem
			time.sleep(0.02)

	finally:
		# Czyszczenie po sobie
		i2c_lock.release()

# Funkcja wysyłająca zapytanie do serwera z kodem
def code_unlock(code, lcd_queue, type):

	# Wyświetl wiadomość o ładowaniu
	lcd_queue.put((config.lang["code_loading"], None))

	# Wyślij zapytanie
	response = session.get(f'{config.server_ip}/code/{code}?type={type}')
	print("Response:", response.status_code, response.text)

	# Zinterpretuj zwrócony kod
	if response.status_code == 200: # Sukces

		# Odebranie i zapisanie ewentualnego ciasteczka
		print("Cookies:", session.cookies.get_dict())
		state["bind_user"] = session.cookies.get_dict().get("bind_user", None)

		# Rozpoczęcie procesu przypisania karty lub odblokowania drzwi
		# w zależności od stanu wyczytanego z ciasteczka
		if state["bind_user"] != None:
			lcd_queue.put((config.lang["card_bind_1"], config.lang["card_bind_2"]))
		else:
			# Wiadomość sukcesu, z dodaną nazwą użytkownika i usuniętymi znakami diakrytycznymi
			lcd_queue.put((config.lang["auth_ok_1"].format(name=unidecode(response.text)), config.lang["auth_ok_2"].format(name=unidecode(response.text))))
			door_queue.put(None)
	else:
		if response.status_code == 424: # Niewłaściwa karta
			lcd_queue.put((config.lang["code_wrong_1"], config.lang["code_wrong_2"]))
		elif response.status_code == 433: # Nie ma takiego użytkownika
			lcd_queue.put((config.lang["code_no_user_1"], config.lang["code_no_user_2"]))
		elif response.status_code == 421: # Za dużo osób w pomieszczeniu
			lcd_queue.put((config.lang["user_limit_1"], config.lang["user_limit_2"]))
		elif response.status_code == 423: # Poza dopuszczalnymi godzinami
			lcd_queue.put((config.lang["outside_hours_1"], config.lang["outside_hours_2"]))
		elif response.status_code == 422: # Próbuje wyjść, ale wcześniej nie wszedł
			lcd_queue.put((config.lang["not_in_room_1"], config.lang["not_in_room_2"]))
		else: # Nieznany błąd
			lcd_queue.put((config.lang["unknown_error_1"], config.lang["unknown_error_2"]))

# Funkcja wywoływana przy zaktualizowaniu kodu na wejściu
def code_entry_update(code, lcd_queue):
	lcd_queue.put((config.lang["code_controls"], "> " + "*" * len(code)))
	print("Entry code:", code)

# Funkcja wywoływana przy zatwierdzeniu kodu na wejściu
def code_entry_submit(code, lcd_queue):
	print("Entry code submit:", code)
	code_unlock(code, lcd_queue, "entry")

# Funkcja wywoływana przy anulowaniu kodu na wejściu
def code_entry_cancel(code, lcd_queue):
	code_entry_update(code, lcd_queue)
	print("Entry code cancel")

# Funkcja wywoływana przy zaktualizowaniu kodu na wyjściu
def code_exit_update(code, lcd_queue):
	lcd_queue.put((config.lang["code_controls"], "> " + "*" * len(code)))
	print("Exit code:", code)

# Funkcja wywoływana przy zatwierdzeniu kodu na wyjściu
def code_exit_submit(code, lcd_queue):
	print("Exit code submit:", code)
	code_unlock(code, lcd_queue, "exit")

# Funkcja wywoływana przy anulowaniu kodu na wyjściu
def code_exit_cancel(code, lcd_queue):
	code_exit_update(code, lcd_queue)
	print("Exit code cancel")

#endregion ---------------------------------------------------------------------

#region Zarządzanie drzwiami i brzęczykiem -------------------------------------

# Wątek zarządzający drzwiami i brzęczykiem
def door_thread():

	# Przygotowanie wyprowadzeń
	buzzer_pin = 19
	GPIO.setup(buzzer_pin, GPIO.OUT)
	buzzer_pwm = GPIO.PWM(buzzer_pin, 500)

	door_pin = 21
	GPIO.setup(door_pin, GPIO.OUT)

	try:
		# Dźwięk przy pomyślnej inicjalizacji
		buzz(buzzer_pwm, 0.1)

		while True:

			# Czekaj na komunikat otwarcia drzwi
			door_queue.get()

			# Otwórz drzwi i zagraj dźwięk
			print("Door Opened!")
			GPIO.output(door_pin, GPIO.HIGH)
			buzz(buzzer_pwm, 3)
			GPIO.output(door_pin, GPIO.LOW)
			print("Door Closed!")

			# Wyczyść kolejkę komunikatów w celu uniknięcia ciągłego
			# otwierania i zamykanie drzwi przy nadmiernej liczbie
			# wysłanych komunikatów
			with door_queue.mutex:
				door_queue.queue.clear()

	finally:
		# Czyszczenie po sobie
		buzzer_pwm.stop()
		GPIO.output(door_pin, GPIO.LOW)

# Funkcja grająca dźwięk na brzęczyku
def buzz(buzzer_pwm, t=0.5):

	# Pominięcie wykonywaniu przy ustawionym wyciszeniu
	if config.buzzer_mute:
		time.sleep(t)
		return

	# Zagranie dźwięku za pomocą pwm
	buzzer_pwm.start(0)

	for dc in range(0, 101, 5):
		buzzer_pwm.ChangeDutyCycle(dc)
		time.sleep(t/20)

	buzzer_pwm.stop()

#endregion ---------------------------------------------------------------------

#region Inicjalizacja ----------------------------------------------------------

try:

	# Wątek czytnika wejściowego
	thread_reader_entry = threading.Thread(target=card_thread, group=None, args=[0, 0, 23, LCD_queue_entry, card_entry])
	thread_reader_entry.start()

	# Wątek czytnika wyjściowego
	thread_reader_exit = threading.Thread(target=card_thread, group=None, args=[0, 1, 24, LCD_queue_exit, card_exit])
	thread_reader_exit.start()

	# Wątek wyświetlacza wejściowego
	thread_lcd_entry = threading.Thread(target=LCD_thread, group=None, args=[0x27, LCD_queue_entry])
	thread_lcd_entry.start()

	# Wątek wyświetlacza wyjściowego
	thread_oled_exit = threading.Thread(target=OLED_thread, group=None, args=[0x3c, LCD_queue_exit])
	thread_oled_exit.start()

	# Wątek drzwi
	thread_door = threading.Thread(target=door_thread, group=None)
	thread_door.start()

	# Wątek klawiatury wejściowej
	thread_keyboard_entry = threading.Thread(target=keyboard_thread, group=None, args=[1, 0x20, LCD_queue_entry, code_entry_update, code_entry_cancel, code_entry_submit])
	thread_keyboard_entry.start()

	# Wątek klawiatury wyjściowej
	thread_keyboard_exit = threading.Thread(target=keyboard_thread, group=None, args=[1, 0x24, LCD_queue_exit, code_exit_update, code_exit_cancel, code_exit_submit])
	thread_keyboard_exit.start()

	# Komunikat o gotowości
	print("Ready!")

	# Oczekiwanie na zakończenie wszystkich wątków
	thread_reader_entry.join()
	thread_reader_exit.join()
	thread_lcd_entry.join()
	thread_oled_exit.join()
	thread_door.join()
	thread_keyboard_entry.join()
	thread_keyboard_exit.join()

finally:
	# Czyszczenie po sobie
	GPIO.cleanup()
	exit(0)
