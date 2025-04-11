# door-authenticator - door authentication system

Door-authenticator is an example of an integrated system, built to authenticate users and authorize access to a protected room.
Supported authentication methods: RFID cards, one-time codes.
Users and Administrators can log into a web interface, where they can manage information and view events related to their accounts.


## Technologies used:

- **Python** - entry teminals running on a Raspberry Pi Zero 2
- **Flask** - web interface, request handlign
- **Flask-SQLAlchemy** - database management, storing system and user data
- **bcrypt** - used for encrypting login information

## Required packages:

﻿  Required python packages are in `requirements.txt`

  


# door-authenticator - system kontroli dostępu

Door-authenticator to stworzony w ramach zajęć z systmów wbudowanych prosty system umożliwiający uwierzytelnianie użutkowników i kontrolę dostępu do pomieszczenia.
Wspierane metody uwierzytelniania: karty RFID, kody jednorazowe.
Użytkownicy i Administratorzy mogą logować się do systemu poprzez witrynę internetową, gdzie mają dostęp do przyznanych im funkcji administracyjnych oraz podgląd dotyczących ich informacji.


## Technologie:

- **Python** - obsługa terminali wejściowych z wykorzystaniem Raspberry Pi Zero 2
- **Flask** - witryna internetowa, obsługa żądań użytkowników
- **Flask-SQLAlchemy** - używany do zarządzania bazą danych przechowującą aktualne informacje o stanie systemu i użytkownikach
- **bcrypt** - używany do szyfrowania danych logowania użytkowników

## Wymagane Biblioteki

﻿  Opisane w pliku `requirements.txt`
