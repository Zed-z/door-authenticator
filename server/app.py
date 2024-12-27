from flask import Flask,render_template,request,redirect,url_for,make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

import random
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)




class users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    imie_nazwisko = db.Column(db.String(100),nullable=False)
    is_admin = db.Column(db.String(1), nullable=False)
    card_id = db.Column(db.String(30), nullable=True)

    def _repr_(self):
        return '<User %r>' % self.id % "  " % self.name
    
class access_codes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    code = db.Column(db.String(6))
    bind_user = db.Column(db.String(1)) # Y/N
    expires = db.Column(db.Integer) # Unix timestamp

    def _repr_(self):
        return '<Code %r>' % self.id % " " % self.user_id % " " % self.code % " " % self.bind_user




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
        if user is None:
            return "costam costam integralność srutututu"



        return user.imie_nazwisko +" "+  self.message + " at " + str(self.time_stamp)




def generate_access_code(user, bind_user):

    while True:
        code = "".join([str(random.randint(0, 9)) for _ in range(6)])
        duplicates = access_codes.query.filter(access_codes.code == code).all()
        if len(duplicates) == 0:
            break

    expires = time.time() + 120

    bind_user_bool = "Y" if bind_user else "N"

    db.session.add(access_codes(user_id = user.id, code = code, bind_user = bind_user_bool, expires = expires))
    db.session.commit()

    return code


@app.route('/', methods=['GET','POST'])
def root():
    if request.method == 'POST':

        login = request.form['login']
        user = 0
        try:
            user = users.query.filter(users.name == login).first()

            log = logs(user_id=user.id,time_stamp=time.time(), message="logged in")

            if user.is_admin == "A":
                resp = make_response(redirect(url_for("admin")))
                resp.set_cookie('login', login)
                db.session.add(log)
                db.session.commit()
                return resp
            elif user.is_admin == "N":
                resp = make_response(redirect(url_for("user")))
                resp.set_cookie('login', login)
                db.session.add(log)
                db.session.commit()
                return resp



        except:
            resp = make_response("error")
            return resp

    return render_template('index.html')




@app.route('/admin', methods=['GET','POST'])
def admin():
    try:
        print(request.cookies.get('login'))
        u = users.query.filter(users.name == request.cookies.get('login')).filter(users.is_admin == "A").first()
        assert(u != None)
    except:
        return "nuh uh - tylko dla adminow"


    if request.method == 'POST':

        try:
            username = request.form['name']
            fullname = request.form['fullname']
            privilage = "A" if request.form.get('is_admin') else "N"
            user = users(name=username, is_admin=privilage, imie_nazwisko=fullname)

            db.session.add(user)
            db.session.commit()
        except:
            return "<h1>Something went wrong when adding user!</h1>"

    us = users.query.order_by(users.name).all()
    return render_template('admin.html',users = us, admin = request.cookies.get('login'), logs = logs.query.all())


@app.route('/user', methods=['GET','POST'])
def user():
    try:
        print(request.cookies.get('login'))
        user = users.query.filter(users.name == request.cookies.get('login')).first()
        code = generate_access_code(user, user.card_id == None)
        assert(user != None)
    except:
        return "error"

    
    return render_template('user.html', user=user, code=code)


@app.route("/delete/<int:idtifier>",methods=['POST','GET'])
def delete(idtifier):
    try:
        print(request.cookies.get('login'))
        u = users.query.filter(users.name == request.cookies.get('login')).filter(users.is_admin == "A").first()
        assert(u != None)
    except:
        return "nuh uh - tylko dla adminow"

    try:
        users.query.filter(users.id == idtifier).delete()
        db.session.commit()
        log = logs(user_id=u.id, time_stamp=time.time(), message="deleted user" + str(idtifier))
        db.session.add(log)
        db.session.commit()

        return redirect(url_for("admin"))
    except:
        return "<h1>Something went wrong when deleting user!</h1>"




@app.route("/card/<string:card_id>",methods=['POST','GET'])
def handle_card(card_id):

    try:
        user = users.query.filter(users.card_id == card_id).first()
        if user is not None:
            return user.imie_nazwisko, 200
        else:
            return "there is no user in the database",400
    except:
        return "unkonwn error occured",400

@app.route("/card_bind/<string:card_id>",methods=['POST','GET'])
def handle_card_bind(card_id):

    try:
        if request.cookies.get('bind_user') != None:

            bind_user_id = int(request.cookies.get('bind_user'))
            print("Binding user", bind_user_id, "to card", card_id)

            user_q = users.query.filter(users.id == bind_user_id)
            user = user_q.first()
            if user is not None:

                user_q.update({ "card_id": card_id })
                db.session.commit()

                resp = make_response(user.imie_nazwisko, 200)
                resp.set_cookie("bind_user", "", expires=0)

                return resp
            else:
                return "there is no user in the database",400        
        else:
            return "No user to bind!",400
    except:
        return "unkonwn error occured",400

@app.route("/code/<string:code>",methods=['POST','GET'])
def handle_code(code):

    try:
        access_codes.query.filter(access_codes.expires < time.time()).delete()
        db.session.commit()

        code_q = access_codes.query.filter(access_codes.code == code)
        code = code_q.first()
        
        if code == None:
            return "there is no user in the database",400

        user = users.query.filter(users.id == code.user_id).first()

        bind_user = code.bind_user

        code_q.delete()
        db.session.commit()

        if user is not None:
            resp = make_response(user.imie_nazwisko, 200)

            if bind_user == "Y":
                resp.set_cookie("bind_user", str(user.id), max_age=30)

            return resp
        else:
            return "there is no user in the database",400
    except Exception as e:
        print(e)
        return "unkonwn error occured",400
    

@app.route('/createdb')
def create_db():
    db.create_all()
    db.session.add(users(name="admin", imie_nazwisko="Adam Miński", is_admin="A",card_id="2222"))
    db.session.add(users(name="user1", imie_nazwisko="Biggus Dickus", is_admin="N",card_id="84928037837"))
    db.session.add(users(name="user2", imie_nazwisko="Dr. Balls", is_admin="N",card_id="728048272166"))
    db.session.commit()
    return ""



if __name__ == '__main__':
    print("Setting up...")

    with app.app_context():
        db.create_all()
        db.session.commit()

    app.run(host='0.0.0.0')
