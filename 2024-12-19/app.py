from flask import Flask,render_template,request,redirect,url_for,make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import random

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
    code = db.Column(db.String(6), unique=True)
    bind_user = db.Column(db.String(1)) # Y/N

    def _repr_(self):
        return '<Code %r>' % self.id % " " % self.user_id % " " % self.code % " " % self.bind_user

def generate_access_code(user, bind_user):

    while True:
        code = "".join([str(random.randint(0, 9)) for _ in range(6)])
        duplicates = access_codes.query.filter(access_codes.code == code).all()
        if len(duplicates) == 0:
            break

    db.session.add(access_codes(user_id = user.id, code = code, bind_user = bind_user))
    db.session.commit()

    return code


@app.route('/', methods=['GET','POST'])
def root():
    if request.method == 'POST':

        login = request.form['login']
        user = 0
        try:
            user = users.query.filter(users.name == login).first()

            if user.is_admin == "A":
                resp = make_response(redirect(url_for("admin")))
                resp.set_cookie('login', login)
                return resp
            elif user.is_admin == "N":
                resp = make_response(redirect(url_for("user")))
                resp.set_cookie('login', login)
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
            #login = request.cookies.get('login')
           # u = users.query.filter(users.name == login).first()
            #print(u)
            #if u.is_admin == "A":
                username = request.form['name']
                card_id = request.form['card_id']
                if request.form.get('is_admin'):
                    privilage = "A"
                else:
                    privilage = "N"
                user = users(name=username, is_admin=privilage, imie_nazwisko="Jan Kowalski",card_id = card_id)

                db.session.add(user)
                db.session.commit()
        except:
            return "nuh uh"






        #except:
        #    return "<h1>Something went wrong with adding user</h1>"

    us = users.query.order_by(users.name).all()
    return render_template('admin.html',users = us)


@app.route('/user', methods=['GET','POST'])
def user():
    try:
        print(request.cookies.get('login'))
        user = users.query.filter(users.name == request.cookies.get('login')).first()
        code = generate_access_code(user, False)
        assert(user != None)
    except:
        return "error"

    
    return render_template('user.html', user=user, code=code)


@app.route("/delete/<int:idtifier>",methods=['POST','GET'])
def delete(idtifier):



    try:
        #u =  users.querry.filter_by(login=request.cookies.get('login')).first()
        #if u.is_admin == "A":
            users.query.filter(users.id == idtifier).delete()
            db.session.commit()
            return redirect(url_for("admin"))
    except:
        return "<h1>coudn't delete user<h1>"




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
    

@app.route("/code/<string:code>",methods=['POST','GET'])
def handle_code(code):

    try:
        code_q = access_codes.query.filter(access_codes.code == code)
        code = code_q.first()
        user = users.query.filter(users.id == code.user_id).first()

        code_q.delete()
        db.session.commit()

        if user is not None:
            return user.imie_nazwisko, 200
        else:
            return "there is no user in the database",400
    except:
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
