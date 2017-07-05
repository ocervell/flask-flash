import unittest
from flask import url_for
from faker import Factory
from faker.providers import person
from manage import flash
import logging
import random
from models import UserModel

faker = Factory.create()
faker.add_provider(person)

log = logging.getLogger('tests')
import subprocess

class FlaskTestCase(unittest.TestCase):
    def setUp(self):
        self.client = flash.client
        self.db = flash.db
        self.app = flash.app
        with self.app.app_context():
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            nusers = self.client.users.count()
            for i in range(nusers):
                self.client.users.delete(i)
            self.db.session.remove()

    def test_scenario_1(self):
        nusers = random.randint(0, 100)
        for n in range(nusers):
            r = self.client.users.create(
                first_name=faker.first_name(),
                last_name=faker.last_name(),
                country=faker.country()
            )
        print "Adding %s user... OK" % nusers

        # Check pagination
        self.assertEqual(len(self.client.users.get()), 10)
        self.assertGreaterEqual(len(self.client.users.get(paginate=False)), nusers)
        self.assertEqual(len(self.client.users.get(per_page=20, page=2)), 20)

        # Check descending sorting
        data = self.client.users.get(order_by='first_name', sort='desc')
        first = data[0]['first_name']
        for d in data:
            self.assertLessEqual(d['first_name'], first)
        print "Testing order_by 'first_name' with descending order... OK"

        # Check ascending sorting
        data = self.client.users.get(order_by='country', sort='asc')
        first = data[0]['country']
        for d in data:
            self.assertGreaterEqual(d['country'], first)
        print "Testing order_by 'country' with ascending order... OK"
