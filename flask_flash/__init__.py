"""
__init__.py
~
Maintainer: Olivier Cervello.
Description: Flask-Flash API constructor and default config.
"""
from resources import *
from extensions import *
from exceptions import *
from client import *
from utils import *
from flask import Blueprint, Flask, session
from flask_restful import Api
from flask_script import Manager, Shell, Server, prompt_bool
from flask_migrate import Migrate, MigrateCommand
import inspect
import os, logging
import inflect

log = logging.getLogger(__name__)
DEFAULT_PROFILE = os.environ.get('PROFILE', 'default')
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5001

class Flash(object):
    """Create a Flask-Flash API.

    Attributes:
        api: The Flask-Restful api object of class `flask_restful.Api`.
        app: The Flask app object of class `flask.Flask`.
        config: The Flask app config.
        db: The Flask-Flash database object.
        routes: The Flask-Flash routes registered with the api.

    Example:
        >>> from flask_flash import Flash
        >>> from models import Auth, User, Other
        >>> flash = Flash([Auth, User, Other])
    """
    def __init__(self, resources, **kwargs):
        self.config = kwargs.get('config', {'default': BaseConfig})
        self.profile = kwargs.get('profile', DEFAULT_PROFILE)
        self.app = kwargs.get('app', Flask(__name__))
        self.db = db
        self.resources = resources
        self.routes = []
        self.create_api(resources, **kwargs)

    def create_api(self, resources, **kwargs):
        """Create the main Flash API.

        Kwargs:
            app: An existing Flask application (default: Flask(__name__))
            extensions: A list of extensions to register with the Api
            url_prefix: The API url prefix (default: /api)
            host: The API host (default: localhost)
            port: The API port (default: 5001)
        """
        # Init app config
        cfg = self.config[self.profile]
        self.app.config.from_object(cfg)
        try:
            cfg.init_app(self.app)
        except AttributeError:
            log.info("`init_app` is not a method of the config class. Skipping.")

        # Create Flask-Restful API
        bp = Blueprint('api', __name__)
        self.api = Api(bp, catch_all_404s=True)

        # Add API resources to API
        self.register_resources()

        # Register extensions required by Flask-Flash to our Flask app
        self.register_extensions(extensions=kwargs.get('extensions', []))

        # Register Flask-Restful API blueprint to our Flask app
        self.app.register_blueprint(bp, url_prefix=kwargs.get('url_prefix', '/api'))

        # Create Flask-Script Server
        host = kwargs.get('host', DEFAULT_HOST)
        port = kwargs.get('port', DEFAULT_PORT)
        self.server = Server(host, port)

        # Create Flask-Flash API client
        self.client = self.create_api_client(host + ':' + str(port))

        # Create Flask-Migrate migrator
        migrate = Migrate(self.app, db)

        # Create Flask-Script manager
        self.manager = Manager(self.app)
        self.shell = Shell(make_context=lambda: dict(app=self.app, db=self.db, c=self.client))
        self.manager.add_command("runserver", self.server)
        self.manager.add_command("shell", self.shell)
        self.manager.add_command("db", MigrateCommand)

    def create_api_client(self, url='localhost:5001', **kwargs):
        """Create an API client from the API routes definitions."""
        c = BaseClient(url, **kwargs)
        from itertools import groupby
        from operator import itemgetter
        routes = [list(group) for key, group in groupby(self.routes, itemgetter(0))]
        endpoints = {}
        for group in routes:
            for route in group:
                pnames = [b.__name__ for b in route[0].__bases__]
                if 'CRUD' in pnames: # CRUD Endpoint
                    name = inflect.engine().plural(route[0].__name__).lower()
                    endpoint = route[1].replace('/<id>', '')
                    if not name in endpoints:
                        endpoints[name] = []
                    endpoints[name].append(endpoint)
        for endpoint_name, endpoint_routes in endpoints.items():
            c.register(endpoint_name, CRUDEndpoint, endpoint_routes)
        return c

    def register_resources(self):
        """Register all API resources with our Flask-Restful API."""
        for res in self.resources:
            cls_ = res.resource_name()
            routes = res.get_routes()
            if all(r[1] is None for r in routes): # multiple endpoints with same endpoint
                urls = [r[0] for r in routes]
                self.api.add_resource(res, *urls)
                self.routes.append((res,) + tuple(urls))
            else:
                for url, endpoint in routes:
                    self.api.add_resource(res, url, endpoint=endpoint)
                    self.routes.append((res, url))
        log.debug(pprint.pformat(self.routes))

    def register_extensions(self, extensions=[]):
        """Register all Flask extensions defined in `extensions.py` with our Flask
        app.
        """
        c = 0
        EXTENSIONS_API.extend(extensions)
        for e in EXTENSIONS_API:
            if isinstance(e, tuple) and e[1] == 'cache': # Flask-Cache extension
                e[0].init_app(self.app, config=self.app.config.get('CACHE_CONFIG', BaseConfig.CACHE_CONFIG))
                c += 1
            else:
                try:
                    e.init_app(self.app)
                    c += 1
                except (AttributeError, ValueError, AssertionError):
                    continue
        log.debug("Registered %s extensions" % c)

class BaseConfig(object):
    SECRET_KEY = 'longrandomstringhere'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_MAX_INPUT = 998
    SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/database.sqlite'
    CACHE_CONFIG = {
        'CACHE_TYPE': 'redis',
        'CACHE_REDIS_HOST': 'localhost',
        'CACHE_REDIS_PORT': '6379',
        'CACHE_KEY_PREFIX': 'flask_',
        'CACHE_DEFAULT_TIMEOUT': 10 # seconds,
    }

    def get(value, default=None):
        try:
            return getattr(self, value)
        except AttributeError:
            return default

    @staticmethod
    def init_app(app):
        pass


test_config = {
    'default': BaseConfig
}
