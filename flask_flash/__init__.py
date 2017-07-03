import os, logging
from flask import Blueprint, Flask, session
from flask_restful import Api
from extensions import *
from flask_script import Manager, Shell, Server, prompt_bool
from flask_migrate import Migrate, MigrateCommand
from flask_flash.client import BaseClient, CRUDEndpoint

log = logging.getLogger(__name__)
profile = os.environ.get('FLASK_API_PROFILE', 'default')

class Flash(object):
    def __init__(self, resources, config=None, **kwargs):
        if config is None: config = { 'default': BaseConfig }
        self.app = Flask(__name__)
        self.db = db
        self.resources = resources
        self.routes = []
        self.create_api(config, resources, **kwargs)

    def create_api(self, config, resources, **kwargs):
        """Create the main Flash API."""
        # Init app config
        cfg = config[profile]
        cfg.init_app(self.app)
        self.app.config.from_object(cfg)

        # Create Flask-Restful API
        bp = Blueprint('api', __name__)
        self.api = Api(bp)

        # Add API resources to API
        self.register_resources()

        # Register extensions required by Flask-Flash
        self.register_extensions()

        # Register Flask-Restful API blueprint to Flask app
        self.app.register_blueprint(bp, url_prefix=kwargs.get('url_prefix', '/api'))

        # Create Flask-Script Server
        host = kwargs.get('host', "0.0.0.0")
        port = kwargs.get('port', 5001)
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

    def get_path(self, resource):
        """Infer partial URL of resource based on class name / class param 'path'"""
        try:
            path_prefix = resource.path
        except AttributeError:
            path_prefix = '/' + resource.__name__.lower()
        try:
            collection = resource.collection
        except:
            collection = False
        if collection:
            return path_prefix.replace('_col', '') + 's'
        else:
            return path_prefix + '/<id>'

    def create_api_client(self, url='localhost:5001', **kwargs):
        """Create an API client from the API routes definitions."""
        c = BaseClient(url, **kwargs)
        for r in self.routes:
            c.add(CRUDEndpoint, r[1].replace('/<id>', ''), r[2])
        return c

    def register_resources(self):
        """Register all API resources with our Flask-Restful API."""
        for r in self.resources:
            # Duplicate 'single' resource to make identical one for 'collection'
            r_col = type(r.__name__ + '_col', r.__bases__, dict(r.__dict__))
            r_col.collection = True

            # Get resource paths (from class name or through class attribute 'path')
            rpath = self.get_path(r)
            rpath_col = self.get_path(r_col)

            # Add resources to API
            self.api.add_resource(r, rpath)
            self.api.add_resource(r_col, rpath_col)
            self.routes.append((r.__name__, rpath, rpath_col))

    def register_extensions(self):
        """Register all Flask extensions defined in `extensions.py` with our Flask
        app.
        """
        c = 0
        for e in EXTENSIONS_API:
            if isinstance(e, tuple) and e[1] == 'cache': # Flask-Cache extension
                log.info(self.app.config)
                e[0].init_app(self.app, config=self.app.config['CACHE_CONFIG'])
                c += 1
            else:
                try:
                    e.init_app(self.app)
                    c += 1
                except (AttributeError, ValueError):
                    continue
        log.debug("Registered %s extensions" % c)

class BaseConfig(object):
    SECRET_KEY = 'ea0d47d240455e609e5201e66f3838c36c5c37fac2abe306'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_MAX_INPUT = 998
    SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/test.db'
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
