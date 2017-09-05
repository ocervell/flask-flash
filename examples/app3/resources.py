from flask_flash import CRUD
from models import *

class User(CRUD):
    model = UserModel
    schema = UserSchema

class Permission(CRUD):
    model = PermissionModel
    schema = PermissionSchema

class Tracker(CRUD):
    model = TrackerModel
    # schema = TrackerSchema
