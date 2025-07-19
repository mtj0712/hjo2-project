from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import hashlib
import MySQLdb.cursors
import re
import requests
from sqlalchemy import create_engine
import sys

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
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    today = date.today()

    realtime_response = requests.get(url=realtime_url, params=realtime_params)
    realtime_data = realtime_response.json()
    current_icon = realtime_data['current']['condition']['icon']

    past_week_icon = []
    next_three_days_icon = []

    for i in range(1, 8):
        history_params['dt'] = str(today - timedelta(days=i))
        history_response = requests.get(url=history_url, params=history_params)
        history_data = history_response.json()
        past_week_icon.append(history_data['forecast']['forecastday'][0]['day']['condition']['icon'])

    for i in range(1, 4):
        forecast_params['dt'] = str(today + timedelta(days=i))
        forecast_response = requests.get(url=forecast_url, params=forecast_params)
        forecast_data = forecast_response.json()
        next_three_days_icon.append(forecast_data['forecast']['forecastday'][0]['day']['condition']['icon'])

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        'SELECT * FROM events WHERE account_id = %s AND start_time < %s '
        'AND ((start_time >= %s AND end_time IS NULL) OR end_time >= %s)',
        (
            session['id'],
            str((today.replace(day=1) + timedelta(days=31)).replace(day=1)) + ' 00:00:00',
            str(today.replace(day=1)) + ' 00:00:00',
            str(today.replace(day=1)) + ' 00:00:00'
        )
    )

    events = cursor.fetchall()
    events = list(events) if events else []
    for e in events:
        e['start_time'] = e['start_time'].isoformat()
        e['end_time'] = 'null' if e['end_time'] is None else e['end_time'].isoformat()
        if e['description'] is None:
            e['description'] = 'null'

    return render_template('index.html',
                            username=session['username'],
                            current_icon=current_icon,
                            past_week_icon=past_week_icon,
                            next_three_days_icon=next_three_days_icon,
                            events=events)

@app.route('/addEvent', methods=['POST'])
def addEvent():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    title = request.form['title']
    description = request.form['description'] if 'description' in request.form else None
    startTime = request.form['startTime']
    endTime = request.form['endTime'] if 'endTime' in request.form else None

    # make sure the byte size of the title is between 1 and 255, inclusive
    if len(title.encode('utf-8')) > 255 or len(title) == 0:
        return redirect(url_for('index', title_too_long=True))

    # make sure the time strings are in proper format
    try:
        startTime = datetime.fromisoformat(startTime)
        if endTime:
            endTime = datetime.fromisoformat(endTime)
    except ValueError:
        return redirect(url_for('index', time_format_wrong=True))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if endTime:
        # make sure the end time comes after the start time
        if endTime <= startTime:
            return redirect(url_for('index', time_order_out=True))

        startTime = startTime.isoformat().replace('T', ' ', 1)
        endTime = endTime.isoformat().replace('T', ' ', 1)

        if description:
            cursor.execute(
                'INSERT INTO events (account_id, title, start_time, end_time, description) VALUES (%s, %s, \'%s\', \'%s\', %s)',
                (session['id'], title, startTime, endTime, description)
            )
        else:
            cursor.execute(
                'INSERT INTO events (account_id, title, start_time, end_time) VALUES (%s, %s, \'%s\', \'%s\')',
                (session['id'], title, startTime, endTime)
            )
    else:
        startTime = startTime.isoformat().replace('T', ' ', 1)

        if description:
            cursor.execute(
                'INSERT INTO events (account_id, title, start_time, description) VALUES (%s, %s, \'%s\', %s)',
                (session['id'], title, startTime, description)
            )
        else:
            cursor.execute(
                'INSERT INTO events (account_id, title, start_time) VALUES (%s, %s, \'%s\')',
                (session['id'], title, startTime)
            )

    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
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
