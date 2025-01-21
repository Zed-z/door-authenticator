#region Moduły
from flask import Flask,render_template,request,redirect,url_for,make_response,flash,get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import desc

import random
import time
import bcrypt

from datetime import datetime
#endregion

# Utworzenie obiektu flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.secret_key = '!@#$%^&*()!@#$%^&*()!@#$%^&*()'

# Komunikaty z błędami
errors = {
    "post_only":                ("Ten adres przyjmuje tylko POST!",     400),
    "admin_only":               ("Dostęp tylko dla administratorów!",   499),
    "unknown_error":            ("Nieznany błąd!",                      400),
    "invalid_card":             ("Niepoprawna karta!",                  420),
    "invalid_code":             ("Niepoprawny kod!",                    424),
    "user_limit_reached":       ("Limit użytkowników osiągnięty!",      421),
    "user_not_in_room":         ("Użytkownik nie jest w środku!",       422),
    "card_already_in_use":      ("Karta w użyciu przez kogoś innego!",  431),
    "noone_to_bind":            ("Nie podano użytkownika!",             432),
    "user_doesnt_exist":        ("Nie ma takiego użytkownika!",         433),
    "outside_access_hours":     ("Poza dopuszczalnymi godzinami!",      423)
}


#region Definicja bazy danych ------------------------------------------------------------------------------------------

db = SQLAlchemy(app)

# Konfiguracja serwera
class config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_limit = db.Column(db.Integer) # Limit użytkowników w pomieszczeniu
    enforce_access_hours = db.Column(db.Integer) # Czy pilnować godzin wstępu
    require_password = db.Column(db.Integer) # Czy wymagać haseł do logowania
    generate_codes = db.Column(db.Integer) # Czy generować kody jednorazowe do logowania
    code_lifetime = db.Column(db.Integer) # Czas wygasania kodów jednorazowych

# Użytkownicy
class users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(100), nullable=False)
    password_salt = db.Column(db.String(50), nullable=False)
    display_name = db.Column(db.String(100),nullable=False)
    type = db.Column(db.String(1), nullable=False)
    card_id = db.Column(db.String(30), nullable=True)

    def _repr_(self):
        return '<User %r>' % self.id % "  " % self.name

# Funkcja do rejestracji użytkownika
def user_register(name, password, display_name, type, card_id):
    salt = bcrypt.gensalt()
    passw = password_hash(password, salt)

    user = users(name=name, password_hash=passw, password_salt=salt, display_name=display_name,  type=type, card_id=card_id)
    db.session.add(user)
    db.session.commit()

    print(f"Registered user {name}")
    return user

# Funkcja do logowania użytkownika
# Zwraca rekord użytkownika albo None
def user_login(name, password):
    user = users.query.filter(users.name == name).first()

    confi = config.query.first()
    if not confi.require_password:
        return (user)

    if user == None:
        return None

    print(password_hash(password, user.password_salt), user.password_hash)
    if password_hash(password, user.password_salt) != user.password_hash:
        return None

    return (user)

# Funkcja wyliczająca hash hasła
def password_hash(password, salt):
    p = password.encode("utf-8")
    bcrypt.hashpw(p, salt)
    return p.decode("utf-8")

# Jednorazowe kody
class access_codes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    code = db.Column(db.String(6))
    bind_user = db.Column(db.String(1)) # Y/N
    expires = db.Column(db.Integer) # Unix timestamp

    def _repr_(self):
        return '<Code %r>' % self.id % " " % self.user_id % " " % self.code % " " % self.bind_user

    def __str__(self):
        return '<Code %r>' % self.code

# Funkcja generująca kody jednorazowe
def generate_access_code(user, bind_user):

    # Usuń przestarzałe kody
    access_codes.query.filter(access_codes.expires < time.time()).delete()
    db.session.commit()

    # Generacja losowego kodu (Z gwarancją unikalności)
    while True:
        code = "".join([str(random.randint(0, 9)) for _ in range(6)])
        duplicates = access_codes.query.filter(access_codes.code == code).all()
        if len(duplicates) == 0:
            break

    # Odszukaj konfigurację
    conf = config.query.first()

    # Ustawienie czasu wygaśnięcia kodu
    expires = time.time() + conf.code_lifetime

    # Ustawienie trybu przypisania kodu
    bind_user_bool = "Y" if bind_user else "N"

    # Dodanie kodu do bazy danych
    db.session.add(access_codes(user_id = user.id, code = code, bind_user = bind_user_bool, expires = expires))
    db.session.commit()

    return code

# Logi administracyjne
class logs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    time_stamp = db.Column(db.Integer) #unix timestamp
    message = db.Column(db.String(120))

    def _repr_(self):
        try:
            return 'user' % self.user.id % 'has "' % self.message % '" at' % self.time_stamp
        except:
            return 'could not fetch log'

    def __str__(self):
        user = users.query.filter(users.id == self.user_id).first()
        if user is None: user = users(display_name=f"deleted user ({self.user_id})")

        return f"[{str(datetime.utcfromtimestamp(self.time_stamp))}] {user.display_name} {self.message}"

# Dopuszczalne godziny wstępu
class access_hours(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    week_day = db.Column(db.Integer, nullable=False)
    start_hour = db.Column(db.Time, nullable=False)
    end_hour = db.Column(db.Time, nullable=False)

    @property
    def user_name(self):
        user = users.query.filter(users.id == self.user_id).first()
        if user is None: user = users(display_name=f"deleted user ({self.user_id})")
        return user.display_name

    @property
    def week_day_name(self):
        week_days = ["","Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
        return week_days[self.week_day]

    @property
    def start_hour_formatted(self):
        return self.start_hour.strftime("%H:%M")

    @property
    def end_hour_formatted(self):
        return self.end_hour.strftime("%H:%M")

# Funkcja sprawdzająca, czy w danym momencie użytkownik ma prawo dostępu
def check_access_hours(user, now):
    hours = access_hours.query.filter(access_hours.user_id == user.id)\
        .filter(access_hours.week_day == now.weekday() + 1)\
        .filter(access_hours.start_hour <= now.time())\
        .filter(access_hours.end_hour >= now.time())\
        .count()
    return hours > 0

# Obecność w pomieszczeniu
class user_presence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    time_stamp = db.Column(db.Integer) #unix timestamp

    @property
    def user_name(self):
        user = users.query.filter(users.id == self.user_id).first()
        if user == None:
            return "<Nieznany użytkownik>"
        return f"{user.display_name} ({user.name})"

    @property
    def date(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.time_stamp))

#endregion -------------------------------------------------------------------------------------------------------------


#region Strony ---------------------------------------------------------------------------------------------------------

# Strona główna / strona logowania
@app.route('/', methods=['GET','POST'])
def root():
    if request.method == 'POST':

        # Odczytaj formularz
        login = request.form['login']
        password = request.form['password']

        try:
            user = user_login(login, password)
            assert(user != None)

            # Odnotuj zdarzenie
            log = logs(user_id=user.id,time_stamp=time.time(), message=" zalogował się")

            # Przekieruj na stronę administratora
            if user.type == "A":
                resp = make_response(redirect(url_for("admin")))
                resp.set_cookie('login', login)
                db.session.add(log)
                db.session.commit()
                return resp

            # Przekieruj na stronę użytkownika
            elif user.type == "N":
                resp = make_response(redirect(url_for("user")))
                resp.set_cookie('login', login)
                db.session.add(log)
                db.session.commit()
                return resp

        except Exception as e:
            print(e)
            flash('Niepowodzenie logowania!', "error")
            return redirect(url_for("root"))

    # Wyszukaj konfigurację
    conf = config.query.first()

    alerts = get_flashed_messages(with_categories=True)
    return render_template('index.html', alerts=alerts, config=conf)


# Strona administratora
@app.route('/admin', methods=['GET','POST'])
def admin():
    try:
        # Znajdź rekord użytkownika
        u = users.query.filter(users.name == request.cookies.get('login')).filter(users.type == "A").first()
        assert(u != None)

        # Znajdź konfigurację
        conf = config.query.first()

        # Wygeneruj kody jednorazowe
        code = generate_access_code(u, u.card_id == None) if conf.generate_codes else None
        bind_code = generate_access_code(u, True) if u.card_id == None else None

    except Exception as e:
        print(repr(e))
        return errors["admin_only"]

    # Wyszukaj potrzebne administratorowi dane
    us = users.query.order_by(users.name).all()
    presences = user_presence.query.all()
    alerts = get_flashed_messages(with_categories=True)

    return render_template('admin.html',
        alerts=alerts,
        users=us,
        presences=presences,
        config=conf,
        code=code,
        bind_code=bind_code,
        admin=u,
        logs=logs.query.order_by(desc(logs.time_stamp)).all(),
        access_hours=access_hours.query.all()
    )


# Strona użytkownika
@app.route('/user', methods=['GET','POST'])
def user():
    try:
        # Znajdź rekord użytkownika
        print(request.cookies.get('login'))
        user = users.query.filter(users.name == request.cookies.get('login')).first()
        assert(user != None)

        # Znajdź konfigurację
        conf = config.query.first()

        # Wygeneruj kody jednorazowe
        code = generate_access_code(user, False) if conf.generate_codes else None
        bind_code = generate_access_code(user, True) if user.card_id == None else None

    except Exception as e:
        print(repr(e))
        return errors["unknown_error"]

    # Wyszukaj potrzebne użytkownikowi dane
    user_logs = logs.query.filter(logs.user_id == user.id).order_by(desc(logs.time_stamp)).all()
    hours = access_hours.query.filter(access_hours.user_id == user.id).all()
    alerts = get_flashed_messages(with_categories=True)

    return render_template('user.html',
        alerts=alerts,
        user=user,
        code=code,
        bind_code=bind_code,
        logs=user_logs,
        access_hours=hours,
        config=conf
    )


# Wylogowanie się
@app.route("/logout", methods=['POST','GET'])
def logout():
    resp = redirect(url_for("root"))
    resp.set_cookie("login", '', expires=0)
    return resp

#endregion -------------------------------------------------------------------------------------------------------------


#region Czynności administracyjne --------------------------------------------------------------------------------------

# Zmiana konfiguracji
@app.route('/config',methods=['GET','POST'])
def configure():
    if request.method != "POST":
        return errors["post_only"]

    # Dostęp tylko dla administratorów
    try:
        print(request.cookies.get('login'))
        u = users.query.filter(users.name == request.cookies.get('login')).filter(users.type == "A").first()
        assert(u != None)
    except:
        return errors["admin_only"]

    # Znajdź i zmodyfikuj rekord z konfiguracją
    configuration = config.query.first()
    configuration.require_password =  1 if request.form.get('require_password') else 0
    configuration.enforce_access_hours = 1 if request.form.get('enforce_access_hours') else 0
    configuration.user_limit = request.form['user_limit']
    configuration.code_lifetime = request.form['code_lifetime']
    configuration.generate_codes = 1 if request.form.get('generate_codes') else 0
    db.session.commit()

    flash("Zmieniono konfigurację.", "info")
    return redirect(url_for('admin'))


# Nadanie uprawnień użytkownikowi
@app.route('/permsadd', methods=['POST'])
def permsadd():

    # Dostęp tylko dla administratorów
    try:
        print(request.cookies.get('login'))
        u = users.query.filter(users.name == request.cookies.get('login')).filter(users.type == "A").first()
        assert(u != None)
    except:
        return errors["admin_only"]

    try:
        # Odczytaj formularz
        user_id = request.form["user_id"]
        week_day = request.form["week_day"]

        start_hour = datetime.strptime(request.form["start_hour"], '%H:%M').time()
        end_hour = datetime.strptime(request.form["end_hour"], '%H:%M').time()
        if start_hour >= end_hour:
            flash("Niewłaściwy przedział czasu!", "error")
            return redirect(url_for("admin"))

        # Dodaj uprawnienia
        ah = access_hours(user_id=user_id, week_day=week_day, start_hour=start_hour, end_hour=end_hour)
        db.session.add(ah)
        db.session.commit()

        # Odnotuj zdarzenie
        log = logs(user_id=u.id, time_stamp=time.time(), message=" dodał uprawnienia " + str(ah.id))
        db.session.add(log)
        db.session.commit()

        flash("Nadano uprawnienia.", "info")
        return redirect(url_for("admin"))

    except:
        flash("Nie udało się nadać uprawnień!", "error")
        return redirect(url_for("admin"))


# Odebranie uprawnień pracownikowi
@app.route('/permsdelete/<int:id>', methods=['POST', 'GET'])
def permsdelete(id):

    # Dostęp tylko dla administratorów
    try:
        print(request.cookies.get('login'))
        u = users.query.filter(users.name == request.cookies.get('login')).filter(users.type == "A").first()
        assert(u != None)
    except Exception as e:
        print(repr(e))
        return errors["admin_only"]

    try:
        # Odbierz uprawnienia
        access_hours.query.filter(access_hours.id == id).delete()
        db.session.commit()

        # Odnotuj zdarzenie
        log = logs(user_id=u.id, time_stamp=time.time(), message=" usunął uprawnienia " + str(id))
        db.session.add(log)
        db.session.commit()

        flash("Odebrano uprawnienia.", "info")
        return redirect(url_for("admin"))

    except Exception as e:
        print(repr(e))
        flash("Nie udało się odebrać uprawnień!", "error")
        return redirect(url_for("admin"))


# Dodanie użytkownika
@app.route("/useradd",methods=['POST'])
def useradd():
    if request.method != "POST":
        return errors["post_only"]

    # Dostęp tylko dla administratorów
    try:
        print(request.cookies.get('login'))
        u = users.query.filter(users.name == request.cookies.get('login')).filter(users.type == "A").first()
        assert(u != None)
    except:
        return errors["admin_only"]

    try:
        # Odczytaj formularz
        username = request.form['name']
        display_name = request.form['display_name']
        password = request.form['passwd']
        user_type = "A" if request.form.get('is_admin') else "N"

        # Dodaj użytkownika
        user = user_register(username,password,display_name,user_type,None)
        assert(user != None)

        # Odnotuj zdarzenie
        log = logs(user_id=u.id, time_stamp=time.time(), message=" dodał użytkownika " + display_name)
        db.session.add(log)
        db.session.commit()

        flash("Dodano pracownika.", "info")
        return redirect(url_for("admin"))

    except Exception as e:
        print(e)
        flash("Nie udało się dodać pracownika!", "error")
        return redirect(url_for("admin"))


# Usunięcie użytkownika
@app.route("/userdelete/<int:idtifier>",methods=['POST','GET'])
def userdelete(idtifier):

    # Dostęp tylko dla administratorów
    try:
        print(request.cookies.get('login'))
        u = users.query.filter(users.name == request.cookies.get('login')).filter(users.type == "A").first()
        assert(u != None)
    except:
        return errors["admin_only"]

    try:
        # Usuń użytkownika 
        users.query.filter(users.id == idtifier).delete()
        db.session.commit()

        # Odnotuj zdarzenie
        log = logs(user_id=u.id, time_stamp=time.time(), message=" usunął użytkownika " + str(idtifier))
        db.session.add(log)
        db.session.commit()

        flash("Usunięto pracownika.", "info")
        return redirect(url_for("admin"))

    except Exception as e:
        print(e)
        flash("Nie udało się usunąć pracownika!", "error")
        return redirect(url_for("admin"))

#endregion -------------------------------------------------------------------------------------------------------------


#region Obsługa terminala ----------------------------------------------------------------------------------------------

# Uwierzytelnianie za pomocą karty
@app.route("/card/<string:card_id>",methods=['POST','GET'])
def handle_card(card_id):

    # Typ użytego terminala - wyjściowy / wejściowy (domyślnie wejściowy)
    type = request.args.get('type', "entry") # entry / exit

    try:

        # Sprawdź, czy istnieje użytkownik z tą kartą
        user = users.query.filter(users.card_id == card_id).first()
        now = datetime.now()

        if user is None:
            return errors["invalid_card"]

        # Wejście
        if type == 'entry':

            # Wyczyść obecność w sali (w razie wcześniejszego odblokowania ale nie wejścia)
            user_presence.query.filter(user_presence.user_id == user.id).delete()
            db.session.commit()

            # Odnotuj próbę wejścia poza dopuszczalnymi godzinami, ale zawsze wpuść administratorów
            if config.query.first().enforce_access_hours:
                if not check_access_hours(user, now):
                    if user.type == 'N':
                        log = logs(user_id=user.id, time_stamp=time.time(), message=" próbował wejść poza godzinami!")
                        db.session.add(log)
                        db.session.commit()
                        return errors["outside_access_hours"]
                    else:
                        log = logs(user_id=user.id, time_stamp=time.time(), message=" wszedł poza godzinami!")
                        db.session.add(log)
                        db.session.commit()

            # Nie wpuszczaj w przypadku osiągniętego limitu osób, ale zawsze wpuść administratorów
            if user_presence.query.filter(user_presence.user_id != user.id).count() >= config.query.first().user_limit:
                if user.type == 'N':
                    return errors["user_limit_reached"]

            # Dodaj wpis o obecności użytkownika
            db.session.add(user_presence(user_id=user.id, time_stamp=time.time()))
            db.session.commit()

        # Wyjście
        elif type == 'exit':

            # Nie wypuszczaj w przypadku braku obecności w sali (podejrzana sytuacja), ale zawsze wypuść administratorów
            if user_presence.query.filter(user_presence.user_id == user.id).count() == 0:
                if user.type == 'N':
                    return errors["user_not_in_room"]

            # Sprawdź czy użytkownik wyszedł poza dopuszczalnymi godzinami i ewentualnie odnotuj
            if config.query.first().enforce_access_hours:
                if not check_access_hours(user, now):
                    log = logs(user_id=user.id, time_stamp=time.time(), message=" wyszedł poza godzinami!")
                    db.session.add(log)
                    db.session.commit()

            # Usuń wpis o obecności użytkownika
            user_presence.query.filter(user_presence.user_id == user.id).delete()
            db.session.commit()

        # Wszystko OK, prześlij terminalowi dane do wyświetlenia
        return user.display_name, 200

    # Wystąpił nieznany błąd
    except Exception as e:
        print(repr(e))
        return errors["unknown_error"]


# Uwierzytelnianie za pomocą kodu jednorazowego
@app.route("/code/<string:code>",methods=['POST','GET'])
def handle_code(code):
    type = request.args.get('type', "entry") # entry / exit

    try:
        # Wyczyść przestarzałe kody
        access_codes.query.filter(access_codes.expires < time.time()).delete()
        db.session.commit()

        # Wyszukaj kod
        code_q = access_codes.query.filter(access_codes.code == code)
        code = code_q.first()

        # Error jeśli kod nie istnieje
        if code is None:
            return errors["invalid_code"]

        # Wyszukaj dane na bazie kodu
        user = users.query.filter(users.id == code.user_id).first()
        bind_user = code.bind_user
        now = datetime.now()

        # Usuń wykorzystany kod
        code_q.delete()
        db.session.commit()

        # Error jeśli taki użytkownik nie istnieje
        if user is None:
            return errors["user_doesnt_exist"]

        # Wejście
        if type == 'entry':

            # Wyczyść obecność w sali (w razie wcześniejszego odblokowania ale nie wejścia)
            user_presence.query.filter(user_presence.user_id == user.id).delete()
            db.session.commit()

            # Nie wpuszczaj w przypadku osiągniętego limitu osób, ale zawsze wpuść administratorów
            if user_presence.query.filter(user_presence.user_id != user.id).count() >= config.query.first().user_limit:
                if user.type == 'N':
                    return errors["user_limit_reached"]

            # Odnotuj próbę wejścia poza dopuszczalnymi godzinami, ale zawsze wpuść administratorów
            if config.query.first().enforce_access_hours:
                if not check_access_hours(user, now):
                    if user.type == 'N':
                        log = logs(user_id=user.id, time_stamp=time.time(), message=" próbował wejść poza godzinami!")
                        db.session.add(log)
                        db.session.commit()
                        return errors["outside_access_hours"]
                    else:
                        log = logs(user_id=user.id, time_stamp=time.time(), message=" wszedł poza godzinami!")
                        db.session.add(log)
                        db.session.commit()

            # Dodaj wpis o obecności użytkownika
            db.session.add(user_presence(user_id=user.id, time_stamp=time.time()))
            db.session.commit()

        # Wyjście
        elif type == 'exit':

            # Nie wypuszczaj w przypadku braku obecności w sali (podejrzana sytuacja), ale zawsze wypuść administratorów
            if user_presence.query.filter(user_presence.user_id == user.id).count() == 0:
                if user.type == 'N':
                    return errors["user_not_in_room"]

            # Sprawdź czy użytkownik wyszedł poza dopuszczalnymi godzinami i ewentualnie odnotuj
            if config.query.first().enforce_access_hours:
                if not check_access_hours(user, now):
                    log = logs(user_id=user.id, time_stamp=time.time(), message=" wyszedł poza godzinami!")
                    db.session.add(log)
                    db.session.commit()

            # Usuń wpis o obecności użytkownika
            user_presence.query.filter(user_presence.user_id == user.id).delete()
            db.session.commit()

        # Utwórz odpowiedź zwrotną
        resp = make_response(user.display_name, 200)

        # Rozpocznij procedurę przypisywania karty
        # Prześlij informację do terminala za pomocą ciassteczka
        if bind_user == "Y":
            resp.set_cookie("bind_user", str(user.id), max_age=30)

        # Odnotuj zdarzenie
        log = logs(user_id=user.id, time_stamp=time.time(), message=" użył kodu " + str(code))
        db.session.add(log)
        db.session.commit()

        return resp

    except Exception as e:
        repr(e)
        return errors["unknown_error"]


# Przypisanie karty do danego użytkownika
@app.route("/card_bind/<string:card_id>",methods=['POST','GET'])
def handle_card_bind(card_id):
    try:
        # Ciasteczko z ID użytkownika do przypisania
        bind_user = request.cookies.get('bind_user')

        # Error jeśli nie podano użytkownika
        if bind_user == None:
            return errors["noone_to_bind"]

        # Error jeśli karta jest już w użyciu
        if users.query.filter(users.card_id == card_id).first() != None:
            return errors["card_already_in_use"]

        # Znajdź użytkownika do przypisania
        bind_user_id = int(bind_user)
        print("Binding user", bind_user_id, "to card", card_id)

        user_q = users.query.filter(users.id == bind_user_id)
        user = user_q.first()
        if user is None:
            return errors["user_doesnt_exist"]

        # Przypisz kartę
        user_q.update({ "card_id": card_id })
        db.session.commit()

        # Utwórz odpowiedź
        resp = make_response(user.display_name, 200)
        log = logs(user_id=user.id, time_stamp=time.time(), message=" przypisał kartę " + str(card_id))
        db.session.add(log)
        db.session.commit()

        resp.set_cookie("bind_user", "", expires=0)

        return resp

    except Exception as e:
        repr(e)
        return errors["unknown_error"]

#endregion -------------------------------------------------------------------------------------------------------------


# Jednorazowe przygotowanie bazy danych
@app.route('/createdb')
def create_db():
    # Zapewnienie jednorazowego uruchomienia
    if config.query.count() > 0:
        return redirect(url_for("root"))

    db.create_all()

    # Przykładowi użytkownicy
    user_register(name="admin", password="123", display_name="Adam Miński", type="A", card_id="713165701200")
    user_register(name="user1", password="123", display_name="Jan Kod",     type="N", card_id="84928037837")
    user_register(name="user2", password="123", display_name="Anna Karta",  type="N", card_id="728048272166")

    # Przykładowe uprawnienia
    for i in range(1, 5+1):
        db.session.add(access_hours(user_id=2, week_day=i, start_hour=datetime.strptime("9:00", '%H:%M').time(), end_hour=datetime.strptime("17:00", '%H:%M').time()))

    for i in range(2, 5+1):
        db.session.add(access_hours(user_id=3, week_day=i, start_hour=datetime.strptime("8:30", '%H:%M').time(), end_hour=datetime.strptime("12:00", '%H:%M').time()))

    # Początkowa konfiguracja
    db.session.add(config(user_limit=2, enforce_access_hours=1, require_password=1, code_lifetime=120, generate_codes=1))

    db.session.commit()
    return redirect(url_for("root"))


# Inicjalizacja serwera
if __name__ == '__main__':
    print("Setting up...")

    with app.app_context():
        db.create_all()
        db.session.commit()

        # Wyczyszczenie obecności w pomieszczeniu
        user_presence.query.delete()
        db.session.commit()

    app.run(host='0.0.0.0')
