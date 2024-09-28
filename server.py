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

# Stato della lampadina
lamp_status = {'is_on': False}

# Callback per la connessione MQTT
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")

# Callback per i messaggi MQTT
def on_message(client, userdata, msg):
    print(f"Message received: {msg.topic} {msg.payload}")

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

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