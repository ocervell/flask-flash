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
            self.db.session.remove()

    def test_index(self):
        self.assertDictEqual(
            self.client.get('/index'),
            {
                'name': 'examples/app1',
                'message': 'It works !'
            }
        )

    def test_scenario_1(self):
        nusers = random.randint(0, 100)
        pks = []
        for n in range(nusers):
            r = self.client.users.create(
                first_name=faker.first_name(),
                last_name=faker.last_name(),
                country=faker.country()
            )
            pks.append(r['id'])

        print "Adding %s user... OK" % nusers

        # Check pagination
        self.assertEqual(len(self.client.users.get()), 10)
        self.assertGreaterEqual(len(self.client.users.get(paginate=False)), nusers)

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

        # Update all users first name
        for pk in pks:
            self.client.users.update(pk, first_name=faker.first_name())

        # Update all users first name to same name
        name = faker.first_name()
        users = self.client.users.get(paginate=False)
        ids = [u['id'] for u in users]
        self.client.users.update(ids, first_name=name)
        self.assertTrue(all(u['first_name'] == name for u in self.client.users.get(paginate=False)))

        # Delete all users
        self.client.users.delete(ids)
        self.assertEqual(self.client.users.count(paginate=False, use_cache=False), 0)
