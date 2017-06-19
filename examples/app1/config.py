from resources import *
from flask_simple_api import create_app, BaseConfig
import os

config = {
    'default': BaseConfig
}

resources = [
    (UserId, '/user/<id>'),
    (UserList, '/users'),
]

app, manager, migrate = create_app(config, resources)
