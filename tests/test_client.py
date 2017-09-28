import unittest
import requests
import logging
import sys
from api import start_server, stop_server, Client

logging.basicConfig(level=logging.ERROR)

class ClientTestExceptions(unittest.TestCase):
    def setUp(self):
        start_server()
        self.client = Client('localhost:5001')

    def tearDown(self):
        stop_server()

    def test_server_up(self):
        r = self.client.get('/test')
        self.assertEqual(r, {'api': 'test', 'version': '1.0'})

    def test_server_down(self):
        self.tearDown()
        with self.assertRaises(requests.exceptions.ConnectionError):
            self.client.get('/test')

    def test_GET_401(self):
        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.auth.get()

    def test_GET_404(self):
        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.get('/nopage')

    def test_GET_CRUD_ResourceNotFound(self):
        with self.assertRaisesRegexp(requests.exceptions.HTTPError, 'ResourceNotFound'):
            self.client.users.get(1)

    def test_GET_CRUD_FilterInvalid(self):
        with self.assertRaisesRegexp(requests.exceptions.HTTPError, 'FilterInvalid'):
            self.client.users.get(match=['this is an invalid filter'])

    def test_CREATE_CRUD_NoPostData(self):
        with self.assertRaisesRegexp(requests.exceptions.HTTPError, 'NoPostData: No data in POST request.'):
            self.client.users.create()

    def test_CREATE_CRUD_SchemaValidationError(self):
        with self.assertRaisesRegexp(requests.exceptions.HTTPError, 'SchemaValidationError'):
            self.client.users.create(unknown='try')
            self.client.users.create(first_name='Owen')
            self.client.users.create(first_name='Owen', last_name='MacDonalds')

    def test_CREATE_CRUD_200(self):
        self.client.users.create([
            {
                'username': 'Frankie',
                'first_name': 'Frank',
                'last_name': 'Karal'
            },
            {
                'username': 'Owie',
                'first_name': 'Owen',
                'last_name': "Mc Donald's"
            }
        ])

    def test_GET_CRUD_200(self):
        self.client.users.create([
            {
                'username': 'Frankie',
                'first_name': 'Frank',
                'last_name': 'Karal'
            },
        ])
        user = self.client.users.get('Frankie')
        self.assertEqual(user['username'], 'Frankie')
        self.assertEqual(user['first_name'], 'Frank')
        self.assertEqual(user['last_name'], 'Karal')
