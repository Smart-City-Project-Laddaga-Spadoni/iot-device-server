import json
import unittest
from unittest.mock import patch, MagicMock
from application import application, users_collection  # Usa direttamente `application`

from werkzeug.security import generate_password_hash

class TestServer(unittest.TestCase):
    def setUp(self):
        self.app = application.test_client()  # Corretto: usa `application` direttamente
        self.app.testing = True

        # Creazione di un utente di test nel mock del database
        self.test_username = 'testuser'
        self.test_password = 'password'
        self.hashed_password = generate_password_hash(self.test_password)

        # Patch del users_collection per includere l'utente di test
        self.users_patch = patch('application.users_collection')
        self.mock_users_collection = self.users_patch.start()
        self.mock_users_collection.find_one.return_value = {'username': self.test_username, 'password': self.hashed_password}

    def tearDown(self):
        self.users_patch.stop()

    @patch('application.users_collection')
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

    @patch('application.users_collection')
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

    # Continua con il resto dei test come sopra...
