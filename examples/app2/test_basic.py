import unittest
from flask import url_for
from faker import Factory
from faker.providers import person, internet
from manage import flash
import logging
import random
from models import UserModel

faker = Factory.create()
faker.add_provider(person)
faker.add_provider(internet)

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
            self.db.drop_all()

    def test_scenario_1(self):
        nusers = random.randint(10, 100)
        nperms = random.randint(5, 10)
        uids = []
        pids = []
        for n in range(nusers):
            u = self.client.users.create(
                first_name=faker.first_name(),
                last_name=faker.last_name(),
                country=faker.country()
            )
            uids.append(u['id'])
        for n in range(nperms):
            puids = random.sample(uids, random.randint(1, 5))
            perm = {'name': faker.uri_path(deep=1), 'users': ['/api/user/%s' % id for id in puids]}
            p = self.client.permissions.create(**perm)
            pids.append(p['name'])

        print "Adding %s user... OK" % nusers
        all_uids = [u['id'] for u in self.client.users.get(paginate=False)]
        all_pids = [p['name'] for p in self.client.permissions.get(paginate=False)]
        self.client.users.delete(all_uids)
        self.client.users.delete(all_pids)
        self.assertEqual(self.client.users.count(), 0)
        self.assertEqual(self.client.permissions.count(), 0)
