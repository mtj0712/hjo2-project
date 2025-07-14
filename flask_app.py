from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import hashlib
import MySQLdb.cursors
import re
import requests
from sqlalchemy import create_engine

app = Flask(__name__, static_folder="static", static_url_path="/")

app.secret_key = 'edHHfH3w4L'

app.config['MYSQL_HOST'] = 'hjo2.mysql.pythonanywhere-services.com'
app.config['MYSQL_USER'] = 'hjo2'
app.config['MYSQL_PASSWORD'] = '_y?03dh5ReMD'
app.config['MYSQL_DB'] = 'hjo2$account'

mysql = MySQL(app)

weatherapi_key = "721cd28a95b849ff90f32123232403"

realtime_url = "https://api.weatherapi.com/v1/current.json"
realtime_params = {
    'key': weatherapi_key,
    'q': 'Seoul'
}

history_url = "https://api.weatherapi.com/v1/history.json"
history_params = {
    'key': weatherapi_key,
    'q': 'Seoul'
}

forecast_url = "https://api.weatherapi.com/v1/forecast.json"
forecast_params = {
    'key': weatherapi_key,
    'q': 'Seoul'
}

@app.route('/')
def index():
    if 'loggedin' in session:
        realtime_response = requests.get(url=realtime_url, params=realtime_params)
        realtime_data = realtime_response.json()
        current_icon = realtime_data['current']['condition']['icon']

        past_week_icon = []
        next_three_days_icon = []

        for i in range(1, 8):
            history_params['dt'] = str(date.today() - timedelta(days=i))
            history_response = requests.get(url=history_url, params=history_params)
            history_data = history_response.json()
            past_week_icon.append(history_data['forecast']['forecastday'][0]['day']['condition']['icon'])

        for i in range(1, 4):
            forecast_params['dt'] = str(date.today() + timedelta(days=i))
            forecast_response = requests.get(url=forecast_url, params=forecast_params)
            forecast_data = forecast_response.json()
            next_three_days_icon.append(forecast_data['forecast']['forecastday'][0]['day']['condition']['icon'])

        return render_template('index.html',
                               username=session['username'],
                               current_icon=current_icon,
                               past_week_icon=past_week_icon,
                               next_three_days_icon=next_three_days_icon)

    return redirect(url_for('login'))

@app.route('/login/', methods=['GET', 'POST'])
def login():
    error_msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']

        hash = password + app.secret_key
        hash = hashlib.sha1(hash.encode())
        password = hash.hexdigest()

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE username = %s AND password = %s', (username, password,))

        account = cursor.fetchone()

        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            return redirect(url_for('index'))
        else:
            error_msg = 'Incorrect username/password!'
    return render_template('login.html', error_msg=error_msg)

@app.route('/logout')
def logout():
   session.pop('loggedin', None)
   session.pop('id', None)
   session.pop('username', None)
   return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    error_msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE username = %s', (username,))
        account = cursor.fetchone()

        if account:
            error_msg = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            error_msg = 'Invalid email address!'
        elif not re.match(r'[A-Za-z0-9]+', username):
            error_msg = 'Username must contain only characters and numbers!'
        elif not username or not password or not email:
            error_msg = 'Please fill out the form!'
        else:
            hash = password + app.secret_key
            hash = hashlib.sha1(hash.encode())
            password = hash.hexdigest()
            cursor.execute('INSERT INTO accounts VALUES (NULL, %s, %s, %s)', (username, password, email,))
            mysql.connection.commit()
            error_msg = 'You have successfully registered!'
    elif request.method == 'POST':
        error_msg = 'Please fill out the form!'
    return render_template('register.html', error_msg=error_msg)

if __name__ == '__main__':
    app.run(debug=True)
