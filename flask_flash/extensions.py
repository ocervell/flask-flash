"""
extensions.py
~
Maintainer: Olivier Cervello.
Description: Base `Flask` extensions to register with `Flask-Flash` apis.
"""
from flask_httpauth import HTTPBasicAuth
from flask_sqlalchemy_patch import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_caching import Cache

cache = Cache()
auth = HTTPBasicAuth()
db = SQLAlchemy()
ma = Marshmallow()

EXTENSIONS_API = [
  (cache, 'cache'),
  ma,
  db,
  auth
]
