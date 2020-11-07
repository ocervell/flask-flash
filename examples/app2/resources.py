from flask_flash import CRUD
from models import *

class User(CRUD):
    model = UserModel
    schema = UserSchema
    post_preprocessors = [
        lambda data: [{k: v.lower() for k, v in i.items()} for i in data],
        lambda data: [{k: v.capitalize() for k, v in i.items()} for i in data]
    ]

class Permission(CRUD):
    model = PermissionModel
    schema = PermissionSchema
