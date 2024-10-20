# iot-device-server
Server side of the smart city project

This is an IoT device server that handles device status, user authentication, and communication with MQTT and MongoDB. It exposes a REST API and WebSocket for real-time updates.

It's built for AWS deploy but it can also run in a local environment.

## Prerequisites
Python 3.8+
MongoDB
MQTT Broker (e.g., AWS IoT Core, Mosquitto)
Docker (optional for containerization)

## Installation
### Clone the Repository

### Run the server without Docker

#### Install dependencies

First, create a virtual environment and activate it:

python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

#### Then, install the required Python packages:

pip install -r requirements.txt

#### Set up environment variables

Create a .env file in the root of the project and add the required environment variables:

AWS_REGION_NAME=eu-north-1 #only for AWS deploy

MONGODB_URI=your-mongodb-uri

MONGODB_DBNAME=your-database-name

JWT_SECRET_KEY=your-jwt-secret-key

MQTT_BROKER=your-mqtt-broker-url

MQTT_PORT=your-mqtt-port

MQTT_USERNAME=your-mqtt-username  # If applicable

MQTT_PASSWORD=your-mqtt-password  # If applicable

#### Run the server
Once the dependencies are installed, you can start the server:


python app.py  # Or python -m flask run

The server will start on the default Flask host (0.0.0.0:5000). You can change the port and host by modifying the .env file.

#### Verify the server
To verify that the server is running:

curl http://localhost:5000/ping

You should receive a response like:
"""
{
    "status": "success",
    "message": "Server is running"
}
"""
### Run the server with Docker
#### Build the Docker image

First, build the Docker image for the server:

docker build -t iot-device-server .

#### Run the container
After building the image, you can run the server in a Docker container:

docker run -d --name iot-server -p 5000:5000 --env-file .env iot-device-server

#### Verify the server
To verify that the server is running in Docker, use the same curl command:

curl http://localhost:5000/ping

## Check Server Status
To check the status of the server, including MongoDB and MQTT connection, you can visit:

http://localhost:5000/status

This will return a JSON with the status of the server and its connections to MQTT and MongoDB.

## API Endpoints
POST /signup: Create a new user

POST /login: Authenticate a user

GET /devices: Get the list of devices (JWT required)

POST /device/<device_id>: Update device status (JWT required)


## License
This project is licensed under the MIT License.
