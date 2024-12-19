from flask import Flask,render_template,request,redirect,url_for,make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


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




@app.route('/', methods=['GET','POST'])
def hello_world():  # put application's code here
    if request.method == 'POST':

        login = request.form['login']
        user = 0
        try:
            user = users.query.filter(users.name == login).first()

            if user.is_admin == "A":
                resp = make_response(redirect(url_for("admin")))
                resp.set_cookie('login', login)
                return resp
        except:
            resp = make_response("aaasdsadsad")
            resp.set_cookie('login', login)
            return resp




    return render_template('index.html')




@app.route('/admin', methods=['GET','POST'])
def admin():
    # try:
    #     print(request.cookies.get('login'))
    #     u = users.query.filter(users.name == request.cookies.get('login')).first()
    #     assert(u != None)
    # except:
    #     return "nuh uh - tylko dla adminow"


    if request.method == 'POST':

        try:
            #login = request.cookies.get('login')
           # u = users.query.filter(users.name == login).first()
            #print(u)
            #if u.is_admin == "A":
                username = request.form['name']
                if request.form.get('is_admin'):
                    privilage = "A"
                else:
                    privilage = "N"
                user = users(name=username, is_admin=privilage, imie_nazwisko="Jan Kowalski",card_id = "1111")

                db.session.add(user)
                db.session.commit()
        except:
            return "nuh uh"






        #except:
        #    return "<h1>Something went wrong with adding user</h1>"

    us = users.query.order_by(users.name).all()
    return render_template('admin.html',users = us)

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

@app.route("/backdoor",methods=['POST','GET'])
def backdoor():
    if request.method == 'POST':


        username = request.form['name']
        if request.form.get('is_admin'):
            privilage = "A"
        else:
            privilage = "N"
        user = users(name=username, is_admin=privilage, card_id = "1111")

        db.session.add(user)
        db.session.commit()
    us = users.query.order_by(users.name).all()
    return render_template('admin.html',users = us)




@app.route("/request/<string:card_id>",methods=['POST','GET'])
def handle_request(card_id):

    try:
        user = users.query.filter(users.card_id == card_id).first()
        if user is not None:
            return "Acces Granted"
        else:
            return "there is no user in the database",400
    except:
        return "unkonwn error occured",400

@app.route('/createdb')
def create_db():
    db.create_all()
    return ""



if __name__ == '__main__':
    print("aaaaaaaa")


    with app.app_context():

        db.create_all()
        db.session.add(users(name="admin", is_admin="T",card_id="2222"))
        db.session.commit()

    app.run()
