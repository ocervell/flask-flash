from flask_flash import CRUD
from models import *

class User(CRUD):
    model = UserModel
    schema = UserSchema
