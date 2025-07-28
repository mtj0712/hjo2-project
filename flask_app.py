from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import hashlib
import json
import MySQLdb.cursors
import numpy as np
import onnxruntime as ort
import re
import requests
from transformers import AutoTokenizer

app = Flask(__name__, static_folder="static", static_url_path="/")

# MysQL
app.secret_key = 'edHHfH3w4L'

app.config['MYSQL_HOST'] = 'hjo2.mysql.pythonanywhere-services.com'
app.config['MYSQL_USER'] = 'hjo2'
app.config['MYSQL_PASSWORD'] = '_y?03dh5ReMD'
app.config['MYSQL_DB'] = 'hjo2$account'

mysql = MySQL(app)

# WeatherAPI
weatherapi_key = "721cd28a95b849ff90f32123232403"

realtime_url = "https://api.weatherapi.com/v1/current.json"
history_url = "https://api.weatherapi.com/v1/history.json"
forecast_url = "https://api.weatherapi.com/v1/forecast.json"
search_url = "http://api.weatherapi.com/v1/search.json"

params = {
    'key': weatherapi_key
}

# LLM ONNX
tokenizer = AutoTokenizer.from_pretrained("/home/hjo2/pythia14m-onnx")
inference_session = ort.InferenceSession("/home/hjo2/pythia14m-onnx/model.onnx")

def onnx_text_generator(prompt, max_new_tokens=20):
    inputs = tokenizer(prompt, return_tensors="np")
    input_ids = inputs["input_ids"]
    attention_mask = inputs["attention_mask"]
    position_ids = np.arange(input_ids.shape[1], dtype=np.int64).reshape(1, -1)

    for _ in range(max_new_tokens):
        ort_inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "position_ids": position_ids,
        }
        outputs = inference_session.run(None, ort_inputs)

        # Get logits of the last token
        next_token_logits = outputs[0][:, -1, :]
        next_token_id = np.argmax(next_token_logits, axis=-1).reshape(1, 1)

        # Append next token
        input_ids = np.concatenate([input_ids, next_token_id], axis=-1)

        # Update attention mask and position ids
        attention_mask = np.concatenate(
            [attention_mask, np.ones((1, 1), dtype=np.int64)], axis=1
        )
        position_ids = np.arange(input_ids.shape[1], dtype=np.int64).reshape(1, -1)

    return tokenizer.decode(input_ids[0])

@app.route('/')
def index():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    if 'title_missing' in request.args:
        alert_message = 'The event title is missing!'
    elif 'start_time_missing' in request.args:
        alert_message = 'The event start time is missing!'
    elif 'title_too_long' in request.args:
        alert_message = 'The event title is too long!'
    elif 'time_format_wrong' in request.args:
        alert_message = 'Your time format is wrong!'
    elif 'time_order_out' in request.args:
        alert_message = 'Your end time must come after your begin time!'
    else:
        alert_message = ''

    today = date.today()

    params['q'] = f'id:{session["location_id"]}'

    realtime_response = requests.get(url=realtime_url, params=params)
    realtime_data = realtime_response.json()
    current_icon = realtime_data['current']['condition']['icon']

    past_week_icons = []
    next_three_days_icons = []

    hourly_weather = []

    for i in range(1, 8):
        params['dt'] = str(today - timedelta(days=i))
        history_response = requests.get(url=history_url, params=params)
        history_data = history_response.json()
        forecastday = history_data['forecast']['forecastday'][0]
        past_week_icons.append(forecastday['day']['condition']['icon'])
        for h in forecastday['hour']:
            hourly_weather.append(h)

    params['dt'] = str(today)
    history_response = requests.get(url=history_url, params=params)
    history_data = history_response.json()

    if len(history_data['forecast']['forecastday']) != 0:
        for h in history_data['forecast']['forecastday'][0]['hour']:
            hourly_weather.append(h)
    else:
        params['dt'] = str(today)
        forecast_response = requests.get(url=forecast_url, params=params)
        forecast_data = forecast_response.json()
        for h in forecast_data['forecast']['forecastday'][0]['hour']:
            hourly_weather.append(h)

    for i in range(1, 4):
        params['dt'] = str(today + timedelta(days=i))
        forecast_response = requests.get(url=forecast_url, params=params)
        forecast_data = forecast_response.json()
        forecastday = forecast_data['forecast']['forecastday'][0]
        next_three_days_icons.append(forecastday['day']['condition']['icon'])
        for h in forecastday['hour']:
            hourly_weather.append(h)

    # predict further forecast
    # prompt = ""
    # response = onnx_text_generator(prompt, 100)

    return render_template('index.html',
                            username=session['username'],
                            current_icon=current_icon,
                            past_week_icons=past_week_icons,
                            next_three_days_icons=next_three_days_icons,
                            hourly_weather=hourly_weather,
                            alert_message=alert_message)

@app.route('/getEvents', methods=['POST'])
def getEvents():
    if 'loggedin' not in session:
        return 'ERROR: not logged in'

    if 'start' not in request.form:
        return 'ERROR: start date not provided'

    if 'end' not in request.form:
        return 'ERROR: end date not provided'

    start = request.form['start']
    end = request.form['end']

    try:
        date.fromisoformat(start)
        date.fromisoformat(end)
    except ValueError:
        return 'ERROR: invalid date format'

    if end <= start:
        return 'ERROR: end date comes after start date'

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        'SELECT * FROM events WHERE account_id = %s AND start_time < %s '
        'AND ((start_time >= %s AND end_time IS NULL) OR end_time >= %s)',
        (
            session['id'],
            end + ' 00:00:00',
            start + ' 00:00:00',
            start + ' 00:00:00'
        )
    )

    events = cursor.fetchall()
    cursor.close()

    events = list(events) if events else []
    for e in events:
        e['start_time'] = e['start_time'].isoformat()
        e['end_time'] = '' if e['end_time'] is None else e['end_time'].isoformat()
        if e['description'] is None:
            e['description'] = ''
    
    return json.dumps(events, separators=(',', ':'))

@app.route('/recommendDate', methods=['POST'])
def recommendDate():
    if 'loggedin' not in session:
        return 'not logged in'

    if 'forecast' not in request.form:
        return 'forecast not provided'

    forecast = json.loads(request.form['forecast'])

    event = request.form['event']

    prompt = (
        "Out of the following times, please recommend the best time to hold the following event.\n"
        f"Event: {event}\n"
    )
    for weather in forecast:
        prompt += (
            f"\nTime: {weather['time']}\n"
            f"Temperature (Celsius): {weather['temp']}\n"
            f"Wind (kph): {weather['wind']}\n"
            f"Humidity (%): {weather['humid']}\n"
            f"Cloud (%): {weather['cloud']}\n"
            f"Amount of rain (mm): {weather['rain']}\n"
            f"Probability that it will rain (%): {weather['rain_p']}\n"
            f"Amount of snow (cm): {weather['snow']}\n"
            f"Probability that it will snow (%): {weather['snow_p']}\n"
        )
    prompt += "Please state the time first and then briefly state your reasoning."

    response = onnx_text_generator(prompt, 100)

    return response.text

@app.route('/addEvent', methods=['POST'])
def addEvent():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    title = request.form['title']
    description = request.form['description']
    startTime = request.form['startTime']
    endTime = request.form['endTime']

    if not title:
        return redirect(url_for('index', title_missing=True))

    if not startTime:
        return redirect(url_for('index', start_time_missing=True))

    # make sure the byte size of the title is between 1 and 255, inclusive
    if len(title.encode('utf-8')) > 255:
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
                'INSERT INTO events (account_id, title, start_time, end_time, description) VALUES (%s, %s, %s, %s, %s)',
                (session['id'], title, startTime, endTime, description)
            )
        else:
            cursor.execute(
                'INSERT INTO events (account_id, title, start_time, end_time) VALUES (%s, %s, %s, %s)',
                (session['id'], title, startTime, endTime)
            )
    else:
        startTime = startTime.isoformat().replace('T', ' ', 1)

        if description:
            cursor.execute(
                'INSERT INTO events (account_id, title, start_time, description) VALUES (%s, %s, %s, %s)',
                (session['id'], title, startTime, description)
            )
        else:
            cursor.execute(
                'INSERT INTO events (account_id, title, start_time) VALUES (%s, %s, %s)',
                (session['id'], title, startTime)
            )

    mysql.connection.commit()

    cursor.close()

    return redirect(url_for('index'))

@app.route('/removeEvent', methods=['POST'])
def removeEvent():
    if 'loggedin' not in session:
        return 'Not logged in'
    
    if 'id' not in request.form:
        return 'No id given'

    eventId = request.form['id']

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('DELETE FROM events WHERE id = %s', (eventId,))
    mysql.connection.commit()
    cursor.close()

    return ''

@app.route('/setting')
def setting():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT email, location_id FROM accounts WHERE id = %s', (session['id'],))

    account = cursor.fetchone()

    cursor.close()

    if not account:
        return redirect(url_for('logout'))

    username = session['username']
    email = account['email']

    params['q'] = f'id:{account["location_id"]}'

    search_response = requests.get(url=search_url, params=params)
    search_data = search_response.json()

    name = search_data[0]['name']
    region = search_data[0]['region']
    country = search_data[0]['country']

    location = f'{name}, {region}, {country}' if region else f'{name}, {country}'

    return render_template('setting.html', email=email, location=location, username=username)

@app.route('/searchLocations', methods=['POST'])
def searchLocations():
    if 'loggedin' not in session:
        return 'Not logged in'

    if 'q' not in request.form:
        return 'No query given'

    q = request.form['q']

    params['q'] = q

    search_response = requests.get(url=search_url, params=params)
    search_data = search_response.json()

    return_objs = []
    for location_obj in search_data:
        new_obj = { 'id': location_obj['id'] }
        name = location_obj['name']
        region = location_obj['region']
        country = location_obj['country']
        new_obj['name'] = f'{name}, {region}, {country}' if region else f'{name}, {country}'
        return_objs.append(new_obj)

    return json.dumps(return_objs, separators=(',', ':'))

@app.route('/changeLocation')
def changeLocation():
    if 'loggedin' not in session:
        return 'Not logged in'

    if 'location_id' not in request.args:
        return 'No location ID given'

    location_id = request.args.get('location_id')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('UPDATE accounts SET location_id = %s WHERE id = %s', (location_id, session['id']))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('setting'))

@app.route('/deleteAccount')
def deleteAccount():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('DELETE FROM accounts WHERE id = %s', (session['id'],))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('logout'))

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

        cursor.close()

        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['location_id'] = account['location_id']
            return redirect(url_for('index'))
        else:
            error_msg = 'Incorrect username/password!'

    return render_template('login.html', error_msg=error_msg)

@app.route('/logout')
def logout():
    if 'loggedin' in session:
        session.pop('loggedin', None)
    if 'id' in session:
        session.pop('id', None)
    if 'username' in session:
        session.pop('username', None)
    if 'location_id' in session:
        session.pop('location_id', None)

    return redirect(url_for('login'))

# TODO: enable location setting in register
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
            cursor.execute('INSERT INTO accounts VALUES (NULL, %s, %s, %s, %s)', (username, password, email, 1377353))
            mysql.connection.commit()
            error_msg = 'You have successfully registered!'

        cursor.close()
    elif request.method == 'POST':
        error_msg = 'Please fill out the form!'

    return render_template('register.html', error_msg=error_msg)

if __name__ == '__main__':
    app.run(debug=True)
