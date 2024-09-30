from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os

# Carica le variabili di ambiente dal file .env
load_dotenv()

app = Flask(__name__)

# Configurazione MQTT
MQTT_BROKER = os.getenv('MQTT_BROKER')
MQTT_PORT = int(os.getenv('MQTT_PORT'))
MQTT_TOPIC = os.getenv('MQTT_TOPIC')
MQTT_USERNAME = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')

# Stato della lampadina
lamp_status = {'is_on': False}

# Callback per la connessione MQTT
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)  # Sottoscrivi al topic

# Callback per i messaggi MQTT
def on_message(client, userdata, msg):
    global lamp_status
    print(f"Message received: {msg.topic} {msg.payload}")
    if msg.topic == MQTT_TOPIC:
        message = msg.payload.decode('utf-8')
        if message == 'on':
            lamp_status['is_on'] = True
        elif message == 'off':
            lamp_status['is_on'] = False

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

@app.route('/lamp', methods=['POST'])
def control_lamp():
    data = request.json
    status = data.get('status')
    lamp_status['is_on'] = (status == 'on')
    mqtt_client.publish(MQTT_TOPIC, status)
    return jsonify({'status': 'success'})

@app.route('/bulb', methods=['GET'])
def get_bulb_status():
    return jsonify(lamp_status)

@app.route('/bulb/on', methods=['POST'])
def turn_bulb_on():
    lamp_status['is_on'] = True
    mqtt_client.publish(MQTT_TOPIC, 'on')
    return jsonify({'status': 'success'})

@app.route('/bulb/off', methods=['POST'])
def turn_bulb_off():
    lamp_status['is_on'] = False
    mqtt_client.publish(MQTT_TOPIC, 'off')
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host=os.getenv('FLASK_RUN_HOST'), port=int(os.getenv('FLASK_RUN_PORT')))