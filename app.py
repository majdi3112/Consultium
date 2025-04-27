import os
from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import bcrypt
from flask_session import Session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'geheime-sleutel'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
Session(app)

# ➔ Standaardroute = loginpagina
@app.route('/')
def index():
    return redirect('/login')

# Database setup
def init_db():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                password TEXT NOT NULL,
                profile_picture TEXT,
                subscription TEXT,
                payment_method TEXT
            )
        ''')
        conn.commit()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name']
        email    = request.form['email']
        phone    = request.form['phone']
        password = request.form['password']
        subscription = request.form['subscription']
        payment_method = request.form['payment_method']

        # Wachtwoord hashen
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Profielfoto verwerken
        profile_picture = request.files.get('profile_picture')
        if profile_picture and profile_picture.filename != '':
            filename = secure_filename(profile_picture.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_picture.save(filepath)
            profile_picture_url = f'uploads/{filename}'
        else:
            profile_picture_url = 'uploads/default.png'

        try:
            with sqlite3.connect('users.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (name, email, phone, password, profile_picture, subscription, payment_method)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, email, phone, hashed_password, profile_picture_url, subscription, payment_method))
                conn.commit()
            return redirect('/login')
        except sqlite3.IntegrityError:
            return "❌ Dit e-mailadres is al geregistreerd!"

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']

        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, password FROM users WHERE email = ?', (email,))
            user = cursor.fetchone()

            if user and bcrypt.checkpw(password.encode('utf-8'), user[1]):
                session['user_id'] = user[0]
                return redirect('/home')
            else:
                return "❌ Foutieve logingegevens."

    return render_template('login.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('home.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
