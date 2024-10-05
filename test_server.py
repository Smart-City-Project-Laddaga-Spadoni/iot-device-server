import json
import unittest
from unittest.mock import patch, MagicMock
from server import app, users_collection
from werkzeug.security import generate_password_hash

class TestServer(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Create a test user in the mock database
        self.test_username = 'testuser'
        self.test_password = 'password'
        self.hashed_password = generate_password_hash(self.test_password)

        # Patch the users_collection to include the test user
        self.users_patch = patch('server.users_collection')
        self.mock_users_collection = self.users_patch.start()
        self.mock_users_collection.find_one.return_value = {'username': self.test_username, 'password': self.hashed_password}

    def tearDown(self):
        self.users_patch.stop()

    @patch('server.users_collection')
    def test_signup_first_user(self, mock_users_collection):
        mock_users_collection.count_documents.return_value = 0
        mock_users_collection.insert_one.return_value = MagicMock()

        response = self.app.post('/signup', data=json.dumps({
            'username': 'newuser',
            'password': 'password'
        }), content_type='application/json')

        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['message'], 'First user created')

    @patch('server.users_collection')
    def test_signup_existing_user(self, mock_users_collection):
        mock_users_collection.count_documents.return_value = 1
        mock_users_collection.find_one.return_value = {'username': 'existinguser'}

        response = self.app.post('/signup', data=json.dumps({
            'username': 'existinguser',
            'password': 'password'
        }), content_type='application/json')

        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'User already exists')

    @patch('server.users_collection')
    def test_login_user(self, mock_users_collection):
        hashed_password = generate_password_hash('password')
        mock_users_collection.find_one.return_value = {'username': 'testuser', 'password': hashed_password}

        response = self.app.post('/login', data=json.dumps({
            'username': 'testuser',
            'password': 'password'
        }), content_type='application/json')

        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'success')
        self.assertIn('access_token', data)

    @patch('server.users_collection')
    def test_login_invalid_user(self, mock_users_collection):
        mock_users_collection.find_one.return_value = None

        response = self.app.post('/login', data=json.dumps({
            'username': 'invaliduser',
            'password': 'password'
        }), content_type='application/json')

        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Invalid credentials')

    @patch('server.devices_collection')
    def test_get_devices(self, mock_devices_collection):
        mock_devices_collection.find.return_value = [
            {'device_id': 'device1', 'status': {'is_on': False}},
            {'device_id': 'device2', 'status': {'is_on': True}}
        ]

        response = self.app.get('/devices', headers=self.get_auth_headers())

        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['device_id'], 'device1')
        self.assertEqual(data[1]['device_id'], 'device2')

    @patch('server.devices_collection')
    def test_get_device(self, mock_devices_collection):
        mock_devices_collection.find_one.return_value = {'device_id': 'device1', 'status': {'is_on': False}}

        response = self.app.get('/device/device1', headers=self.get_auth_headers())

        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['device_id'], 'device1')

    @patch('server.devices_collection')
    def test_get_device_not_found(self, mock_devices_collection):
        mock_devices_collection.find_one.return_value = None

        response = self.app.get('/device/device1', headers=self.get_auth_headers())

        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Device not found')

    @patch('server.devices_collection')
    @patch('server.audit_collection')
    @patch('server.mqtt_client')
    def test_update_device(self, mock_mqtt_client, mock_audit_collection, mock_devices_collection):
        mock_devices_collection.update_one.return_value.matched_count = 1

        response = self.app.post('/device/device1', data=json.dumps({
            'status': {'is_on': True}
        }), headers=self.get_auth_headers(), content_type='application/json')

        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'success')

    @patch('server.devices_collection')
    def test_update_device_not_found(self, mock_devices_collection):
        mock_devices_collection.update_one.return_value.matched_count = 0

        response = self.app.post('/device/device1', data=json.dumps({
            'status': {'is_on': True}
        }), headers=self.get_auth_headers(), content_type='application/json')

        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Device not found')

    def get_auth_headers(self):
        response = self.app.post('/login', data=json.dumps({
            'username': self.test_username,
            'password': self.test_password
        }), content_type='application/json')
        data = json.loads(response.data.decode())
        token = data.get('access_token')
        if not token:
            raise ValueError("Failed to obtain access token")
        return {'Authorization': f'Bearer {token}'}

if __name__ == '__main__':
    unittest.main()