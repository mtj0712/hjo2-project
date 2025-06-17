from flask import Flask, render_template
from models.event import Base
import requests
from sqlalchemy import create_engine

app = Flask(__name__)

weatherapi_key = "721cd28a95b849ff90f32123232403"
url = "https://api.weatherapi.com/v1/current.json"
params = {
    'key': weatherapi_key,
    'q': 'Baltimore'
}

def create_table():
    engine = create_engine("mysql+mysqlconnector://hjo2:_y?03dh5ReMD@hjo2.mysql.pythonanywhere-services.com/default")
    Base.metadata.create_all(engine)

@app.route('/')
def index():
    r = requests.get(url=url, params=params)
    data = r.json()
    location = data['location']
    current = data['current']
    condition = current['condition']
    print(f'Location: {location['name']}, {location['region']}, {location['country']}')
    print(f'Current time: {location['localtime']}')
    print(f'Last updated: {current['last_updated']}')
    print(f'Temperature: {current['temp_c']} degrees Celsius')
    print('Daytime' if current['is_day'] else 'Nighttime')
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
