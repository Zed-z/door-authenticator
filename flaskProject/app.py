from flask import Flask,render_template,request,redirect,url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)


class users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.String(1), nullable=False)


    def _repr_(self):
        return '<User %r>' % self.id % "  " % self.name




@app.route('/', methods=['GET','POST'])
def hello_world():  # put application's code here
    if request.method == 'POST':
        try:
            login = request.form['login']
            user = users.query.filter(users.name == login).first()

            if user.is_admin == "A":
                return redirect(url_for("admin"))
            else:
                return "nie ma jeszcze strony normalnego urzytkownika"




        except:
            return "<h1>Something went wrong</h1>"


    return render_template('index.html')


@app.route('/admin', methods=['GET','POST'])
def admin():

    if request.method == 'POST':
        try:
            username = request.form['name']
            if request.form.get('is_admin'):
                privilage = "A"
            else:
                privilage = "N"
            user = users(name=username, is_admin=privilage)

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
    print(idtifier)

    try:
        users.query.filter(users.id == idtifier).filter(users.is_admin == "N" ).delete()
        db.session.commit()
        return redirect(url_for("admin"))
    except:
        return "<h1>coudn't delete user<h1>"






if __name__ == '__main__':
    print("aaaaaaaa")

    with app.app_context():
        db.create_all()

    app.run()
    db.session.add(users(name="admin", is_admin="T"))
    db.session.commit()
