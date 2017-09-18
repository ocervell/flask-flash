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

    # def test_scenario_1(self):
    #     nusers = random.randint(5, 100)
    #     nperms = random.randint(5, 10)
    #     uids = []
    #     pids = []
    #     for n in range(nusers):
    #         u = self.client.users.create(
    #             first_name=faker.first_name(),
    #             last_name=faker.last_name(),
    #             country=faker.country()
    #         )
    #         uids.append(u['id'])
    #     for n in range(nperms):
    #         puids = random.sample(uids, random.randint(0, 5))
    #         p = self.client.permissions.create(
    #             name=faker.uri_path(deep=1),
    #             users=['/api/user/%s' % id for id in puids]
    #         )
    #         pids.append(p['name'])
    #
    #     print "Adding %s user... OK" % nusers
    #     self.client.permissions.delete()
    #     self.client.users.delete()
    #     self.assertEqual(self.client.users.count(), 0)
    #     self.assertEqual(self.client.permissions.count(), 0)

    def test_scenario_2(self):
        nusers = 2500
        for n in range(nusers):
            kwargs = {
                'first_name': faker.first_name(),
                'last_name': faker.last_name(),
                'country': faker.country()
            }
            self.client.users.create(**kwargs)
