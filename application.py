from flask import Flask, json, request, jsonify, render_template
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os
import pymongo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import boto3  # AWS SDK for Python
import json as js
import tempfile

load_dotenv(override=True)

application = Flask(__name__) 
socketio = SocketIO(application, cors_allowed_origins="*")

# Retrieve secrets from AWS Secrets Manager
def get_secrets(secret_name, region_name="eu-north-1"):
    try:
        client = boto3.client('secretsmanager', region_name=region_name)
        response = client.get_secret_value(SecretId=secret_name)
        secrets = js.loads(response['SecretString'])
        return secrets
    except Exception as e:
        print(f"Error retrieving secrets: {e}")
        return {}

region_name = os.getenv('AWS_REGION_NAME', 'eu-north-1')
secrets = get_secrets("MyIoTDeviceKeysSC", region_name)

# MongoDB
MONGODB_URI = secrets.get('MONGODB_URI', os.getenv('MONGODB_URI'))
MONGODB_DBNAME = secrets.get('MONGODB_DBNAME', os.getenv('MONGODB_DBNAME'))
client = pymongo.MongoClient(MONGODB_URI)
db = client[MONGODB_DBNAME]
users_collection = db['Users']
devices_collection = db['Devices']
audit_collection = db['Audit']

# JWT
application.config['JWT_SECRET_KEY'] = secrets.get('JWT_SECRET_KEY', os.getenv('JWT_SECRET_KEY', 'default_secret_key'))
application.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(seconds=int(secrets.get('JWT_ACCESS_TOKEN_EXPIRES', os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))))
jwt = JWTManager(application)

# MQTT settings
MQTT_BROKER = secrets.get('MQTT_BROKER', os.getenv('MQTT_BROKER'))
MQTT_PORT = int(secrets.get('MQTT_PORT', os.getenv('MQTT_PORT', 8883)))  # Default MQTT port for SSL/TLS

print(f"MQTT_BROKER : {MQTT_BROKER}:{MQTT_PORT}")

# Get username and password from environment variables
MQTT_USERNAME = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')

# Initialize MQTT client
mqtt_client = mqtt.Client()

# If username and password are provided, use them for authentication
if MQTT_USERNAME and MQTT_PASSWORD:
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
else:
    local_private_key_path = os.getenv('MQTT_PRIVATE_KEY_PATH')
    local_cert_path = os.getenv('MQTT_CERT_PATH')
    local_ca_path = os.getenv('MQTT_CA_PATH')
    if not local_private_key_path or not local_cert_path or not local_ca_path:
        try:
            # Extract MQTT credentials from the secret
            mqtt_private_key = secrets['mqtt_private_key']
            mqtt_cert = secrets['mqtt_cert']
            mqtt_root_ca = secrets['mqtt_root_ca']

            # Load certificates for MQTT connection
            def clean_key_or_cert(key_or_cert, begin_marker, end_marker):
                key_or_cert = key_or_cert.replace(f"-----BEGIN {begin_marker}-----", f"-----BEGIN_{begin_marker.replace(' ', '_')}-----")
                key_or_cert = key_or_cert.replace(f"-----END {end_marker}-----", f"-----END_{end_marker.replace(' ', '_')}-----")
                key_or_cert = key_or_cert.replace(" ", "\r\n")
                key_or_cert = key_or_cert.replace(f"-----BEGIN_{begin_marker.replace(' ', '_')}-----", f"-----BEGIN {begin_marker}-----")
                key_or_cert = key_or_cert.replace(f"-----END_{end_marker.replace(' ', '_')}-----", f"-----END {end_marker}-----\r\n")
                return key_or_cert

            # Ensure the private key is correctly formatted
            mqtt_private_key = clean_key_or_cert(mqtt_private_key, "RSA PRIVATE KEY", "RSA PRIVATE KEY")
            mqtt_cert = clean_key_or_cert(mqtt_cert, "CERTIFICATE", "CERTIFICATE")
            mqtt_root_ca = clean_key_or_cert(mqtt_root_ca, "CERTIFICATE", "CERTIFICATE")

            # Save the certificates to temporary files
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as key_file:
                key_file.write(mqtt_private_key.encode())
                key_file_path = key_file.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cert_file:
                cert_file.write(mqtt_cert.encode())
                cert_file_path = cert_file.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as ca_file:
                ca_file.write(mqtt_root_ca.encode())
                ca_file_path = ca_file.name

        except Exception as e:
            print(f"Error retrieving secrets: {e}")
    else:
        key_file_path = local_private_key_path
        cert_file_path = local_cert_path
        ca_file_path = local_ca_path

    try:
        # Load certificates for MQTT connection
        mqtt_client.tls_set(ca_certs=ca_file_path, certfile=cert_file_path, keyfile=key_file_path)
    except Exception as e:
        print(f"Error creating tls mqtt client: {e}")

# Callback for MQTT connection
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe("device/+/signin")  # signin topic
    client.subscribe("device/+/stateChange")  # device state changes topic

# Callback for MQTT messages
def on_message(client, userdata, msg):
    try:
        print(f"Message received: {msg.topic} {msg.payload}")
        message = msg.payload.decode('utf-8')
        data = json.loads(message)
        device_id = msg.topic.split('/')[1]
        if msg.topic.endswith("signin"):
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
    except Exception as e:
        print(f"Error processing message: {e}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connect to the MQTT broker
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
except ConnectionRefusedError:
    print("Connection to MQTT broker failed. Please ensure the broker is running and accessible.")

# Check MQTT connection status
def is_mqtt_connected():
    try:
        # Check if the MQTT client is connected
        return mqtt_client.is_connected()
    except Exception as e:
        print(f"Error checking MQTT connection: {e}")
        return False

# Check MongoDB connection status
def is_mongo_connected():
    try:
        # Check if the MongoDB client is connected
        client.admin.command('ping')
        return True
    except Exception as e:
        print(f"Error checking MongoDB connection: {e}")
        return False

# API Rest

@application.route('/devices', methods=['GET'])
@jwt_required()
def get_devices():
    devices = list(devices_collection.find({}, {'_id': 0}))
    return jsonify(devices)

@application.route('/device/<device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    device = devices_collection.find_one({'device_id': device_id}, {'_id': 0})
    if device:
        return jsonify(device)
    return jsonify({'status': 'error', 'message': 'Device not found'}), 404

@application.route('/device/<device_id>', methods=['POST'])
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
    mqtt_client.publish(f"device/{device_id}/stateChange", json.dumps({'status': status}))
    socketio.emit('device_status_update', {'device_id': device_id, 'status': status})
    return jsonify({'status': 'success'})

@application.route('/signup', methods=['POST'])
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

@application.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = users_collection.find_one({'username': username})
    if user and check_password_hash(user['password'], password):
        access_token = create_access_token(identity=username)
        return jsonify({'status': 'success', 'access_token': access_token})
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

@application.route('/ping', methods=['GET'])
def ping():
    return jsonify({'status': 'success', 'message': 'Server is running'}), 200

# Status endpoint

@application.route('/status', methods=['GET'])
def status():
    try:
        mqtt_status = is_mqtt_connected()
    except Exception as e:
        print(f"Error checking MQTT connection: {e}")
        mqtt_status = False

    try:
        mongo_status = is_mongo_connected()
    except Exception as e:
        print(f"Error checking MongoDB connection: {e}")
        mongo_status = False

    return jsonify({
        'server': 'Running',
        'mqtt_connected': mqtt_status,
        'mongo_connected': mongo_status
    })

@application.route('/status_page', methods=['GET'])
def status_page():
    return render_template('status.html')

if __name__ == '__main__':
    socketio.run(application, host=os.getenv('FLASK_RUN_HOST', '0.0.0.0'), port=int(os.getenv('FLASK_RUN_PORT', 5000)))