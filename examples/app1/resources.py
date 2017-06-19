from flask_simple_api.core import CRUD
from models import *

class UserId(CRUD):
    model = User
    schema = UserSchema

class UserList(CRUD):
    model = User
    schema = UserSchema
