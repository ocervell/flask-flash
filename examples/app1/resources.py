from flask_flash import CRUD, Resource
from models import *
from flask import jsonify

class Index(Resource):
    def get(self):
        return jsonify({
            'name': 'examples/app1',
            'message': 'It works !'
        })

class User(CRUD):
    model = UserModel
    schema = UserSchema
