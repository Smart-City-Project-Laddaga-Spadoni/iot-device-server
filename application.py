from flask import Flask, json, request, jsonify
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os
import pymongo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import boto3  # AWS SDK for Python
import json as js  # To handle JSON data

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Recupera i segreti da AWS Secrets Manager
def get_secrets(secret_name, region_name="eu-north-1"):
    client = boto3.client('secretsmanager', region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        secrets = js.loads(response['SecretString'])
        return secrets
    except Exception as e:
        print(f"Error retrieving secrets: {e}")
        return {}

# Recupera i segreti
secrets = get_secrets("MyAppSecrets")

# MongoDB
MONGODB_URI = os.getenv('MONGODB_URI', secrets.get('MONGODB_URI'))
MONGODB_DBNAME = os.getenv('MONGODB_DBNAME')
client = pymongo.MongoClient(MONGODB_URI)
db = client[MONGODB_DBNAME]
users_collection = db['Users']
devices_collection = db['Devices']
audit_collection = db['Audit']

# JWT
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', secrets.get('JWT_SECRET_KEY', 'default_secret_key'))
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600)))
jwt = JWTManager(app)

# MQTT settings
MQTT_BROKER = os.getenv('MQTT_BROKER')
MQTT_PORT = int(os.getenv('MQTT_PORT', 8883))  # Default MQTT port for SSL/TLS

# Get username and password from environment variables
MQTT_USERNAME = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')

# Initialize MQTT client
mqtt_client = mqtt.Client()

# If username and password are provided, use them for authentication
if MQTT_USERNAME and MQTT_PASSWORD:
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
else:
    # If not present, retrieve the secret from AWS Secrets Manager
    secret_name = "MyIoTDeviceKeysSC"
    region_name = "eu-north-1"

    # Create a Secrets Manager client
    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        # Retrieve the secret
        response = client.get_secret_value(SecretId=secret_name)
        secrets = js.loads(response['SecretString'])  # Load the secret as JSON

        # Extract MQTT credentials from the secret
        # You might have to adjust the keys based on your secret structure
        mqtt_private_key = secrets['mqtt_private_key']  # Path to your private key
        mqtt_cert = secrets['mqtt_cert']  # Path to your certificate
        mqtt_root_ca = secrets['mqtt_root_ca']  # Path to your CA root certificate

        # Load certificates for MQTT connection
        mqtt_client.tls_set(ca_certs=mqtt_root_ca, certfile=mqtt_cert, keyfile=mqtt_private_key)

    except Exception as e:
        print(f"Error retrieving secrets: {e}")

# Callback for MQTT connection
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe("device/+/signin")  # signin topic
    client.subscribe("device/+/stateChange")  # device state changes topic

# Callback for MQTT messages
def on_message(client, userdata, msg):
    print(f"Message received: {msg.topic} {msg.payload}")
    message = msg.payload.decode('utf-8')
    data = json.loads(message)
    device_id = msg.topic.split('/')[1]
    if msg.topic.endswith("signin"): # qui devo prendere lo stato che arriva dal client
        device = devices_collection.find_one({'device_id': device_id})
        if device:
            status = device['status']
        else:
            status = data.get('status', None)
            if status is not None:
                devices_collection.insert_one({'device_id': device_id, 'status': status})
        mqtt_client.publish(f"device/{device_id}/stateChange", json.dumps({'status': status}))
    else:
        status = data.get('status', None)
        if status is not None:
            devices_collection.update_one(
                {'device_id': device_id},
                {'$set': {'status': status}},
                upsert=True
            )
            audit_collection.insert_one({
                'device_id': device_id,
                'status': status,
                'timestamp': datetime.now(timezone.utc),
                'username': f"Bulbs simulator app"
            })
            socketio.emit('device_status_update', {'device_id': device_id, 'status': status})

# Connect to the MQTT broker
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
except ConnectionRefusedError:
    print("Connection to MQTT broker failed. Please ensure the broker is running and accessible.")

# API Rest

@app.route('/devices', methods=['GET'])
@jwt_required()
def get_devices():
    devices = list(devices_collection.find({}, {'_id': 0}))
    return jsonify(devices)

@app.route('/device/<device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    device = devices_collection.find_one({'device_id': device_id}, {'_id': 0})
    if device:
        return jsonify(device)
    return jsonify({'status': 'error', 'message': 'Device not found'}), 404

@app.route('/device/<device_id>', methods=['POST'])
@jwt_required()
def update_device(device_id):
    data = request.json
    status = data.get('status')
    result = devices_collection.update_one(
        {'device_id': device_id},
        {'$set': {'status': status}},
        upsert=True
    )
    if result.matched_count == 0:
        return jsonify({'status': 'error', 'message': 'Device not found'}), 404
    audit_collection.insert_one({
        'device_id': device_id,
        'status': status,
        'timestamp': datetime.now(timezone.utc),
        'username': get_jwt_identity()  # JWT Get user from JWT token
    })
    mqtt_client.publish(f"device/{device_id}/stateChange", json.dumps(status))
    socketio.emit('device_status_update', {'device_id': device_id, 'status': status})
    return jsonify({'status': 'success'})

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    # Check if there are users in the database
    if users_collection.count_documents({}) == 0:
        # First user, don't check permissions
        hashed_password = generate_password_hash(password)
        users_collection.insert_one({'username': username, 'password': hashed_password})
        return jsonify({'status': 'success', 'message': 'First user created'})
    
    # Check if the user already exists
    if users_collection.find_one({'username': username}):
        return jsonify({'status': 'error', 'message': 'User already exists'}), 400
    
    # Create user with hashed password
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
        access_token = create_access_token(identity=username)
        return jsonify({'status': 'success', 'access_token': access_token})
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'status': 'success', 'message': 'Server is running'}), 200

if __name__ == '__main__':
    socketio.run(app, host=os.getenv('FLASK_RUN_HOST', '0.0.0.0'), port=int(os.getenv('FLASK_RUN_PORT', 5000)))