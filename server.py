from flask import Flask, json, request, jsonify
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os
import pymongo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Carica le variabili di ambiente dal file .env
load_dotenv()

app = Flask(__name__)

# Configurazione MongoDB
MONGODB_URI = os.getenv('MONGODB_URI')
MONGODB_DBNAME = os.getenv('MONGODB_DBNAME')
client = pymongo.MongoClient(MONGODB_URI)
db = client[MONGODB_DBNAME]
users_collection = db['Users']
devices_collection = db['Devices']
audit_collection = db['Audit']

# Configurazione MQTT
MQTT_BROKER = os.getenv('MQTT_BROKER')
MQTT_PORT = int(os.getenv('MQTT_PORT'))
MQTT_USERNAME = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')

# Callback per la connessione MQTT
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe("signin")  # Sottoscrivi al topic signin

# Callback per i messaggi MQTT
def on_message(client, userdata, msg):
    print(f"Message received: {msg.topic} {msg.payload}")
    message = msg.payload.decode('utf-8')
    if msg.topic == "signin":
        data = json.loads(message)
        device_id = data['device_id']
        device = devices_collection.find_one({'device_id': device_id})
        if device:
            status = device['status']
        else:
            status = {'is_on': False}
            devices_collection.insert_one({'device_id': device_id, 'status': status})
        mqtt_client.publish(f"device/{device_id}", json.dumps(status))
    else:
        device_id = msg.topic.split('/')[1]
        status = json.loads(message)
        devices_collection.update_one(
            {'device_id': device_id},
            {'$set': {'status': status}},
            upsert=True
        )
        audit_collection.insert_one({
            'device_id': device_id,
            'status': status,
            'timestamp': datetime.utcnow(),
            'username': data['user']  
        })

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Configura il client MQTT con nome utente e password
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
except ConnectionRefusedError:
    print("Connection to MQTT broker failed. Please ensure the broker is running and accessible.")

@app.route('/devices', methods=['GET'])
def get_devices():
    devices = list(devices_collection.find({}, {'_id': 0}))
    return jsonify(devices)

@app.route('/device/<device_id>', methods=['GET'])
def get_device(device_id):
    device = devices_collection.find_one({'device_id': device_id}, {'_id': 0})
    if device:
        return jsonify(device)
    return jsonify({'status': 'error', 'message': 'Device not found'}), 404

@app.route('/device/<device_id>', methods=['POST'])
def update_device(device_id):
    data = request.json
    status = data.get('status')
    user = data.get('user')
    devices_collection.update_one(
        {'device_id': device_id},
        {'$set': {'status': status}},
        upsert=True
    )
    audit_collection.insert_one({
        'device_id': device_id,
        'status': status,
        'timestamp': datetime.utcnow(),
        'username': user  # get the user from the request
    })
    mqtt_client.publish(f"device/{device_id}", json.dumps(status))
    return jsonify({'status': 'success'})

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if users_collection.find_one({'username': username}):
        return jsonify({'status': 'error', 'message': 'User already exists'}), 400
    hashed_password = generate_password_hash(password)
    users_collection.insert_one({'username': username, 'password': hashed_password})
    return jsonify({'status': 'success'})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = users_collection.find_one({'username': username})
    if user and check_password_hash(user['password'], password):
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

if __name__ == '__main__':
    app.run(host=os.getenv('FLASK_RUN_HOST'), port=int(os.getenv('FLASK_RUN_PORT')))