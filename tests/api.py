from werkzeug.serving import make_server
from flask_flash.extensions import db, ma
from flask_flash import Flash
from flask import jsonify
from flask_flash import Flash, CRUD, Resource, Protected, Endpoint, \
                        CRUDEndpoint, BaseClient
import logging
import requests
import threading

log = logging.getLogger(__name__)

class ServerThread(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.srv = make_server('127.0.0.1', 5001, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        log.info('starting server')
        self.srv.serve_forever()

    def shutdown(self):
        log.info('shuting down server')
        self.srv.shutdown()

def start_server():
    global server
    app = Flash(resources=[User, Auth, Test]).app
    with app.app_context():
        db.drop_all()
        db.create_all()
    server = ServerThread(app)
    server.start()
    log.info('server started')

def stop_server():
    global server
    server.shutdown()
    log.info('server shutdown')

class UserModel(db.Model):
    username = db.Column(db.Text, primary_key=True)
    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    country = db.Column(db.Text, default=None)

class UserSchema(ma.ModelSchema):
    class Meta:
        model = UserModel
    username = ma.Field(required=True)
    first_name = ma.Field(required=True)
    last_name = ma.Field(required=True)

class User(CRUD):
    model = UserModel
    schema = UserSchema

class Auth(Protected):
    pass

class Test(Resource):
    url = '/test'
    def get(self):
        return jsonify({
            'api': 'test',
            'version': '1.0'
        })

class Client(BaseClient):
    @property
    def users(self):
        return CRUDEndpoint(self, '/user', '/users')

    @property
    def auth(self):
        return Endpoint(self, '/auth')

    @property
    def test(self):
        return Endpoint(self, '/test')
