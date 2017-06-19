from flask_httpauth import HTTPBasicAuth
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

auth = HTTPBasicAuth()
db = SQLAlchemy()
ma = Marshmallow()

EXTENSIONS_API = [
  ma,
  db,
  auth
]
