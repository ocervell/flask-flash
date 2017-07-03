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
    def __init__(self, config, resources=[]):
        self.app = Flask(__name__)
        self.resources = resources
        self.routes = []
        self.create_api(config, resources)

    def create_api(self, config, resources=[]):
        # Init app config
        cfg = config[profile]
        cfg.init_app(self.app)
        self.app.config.from_object(cfg)

        # Create API blueprint
        bp = Blueprint('api', __name__)
        api = Api(bp)

        # Add API resources to Flask-Restful API
        for r in resources:
            r_col = type(r.__name__ + '_col', r.__bases__, dict(r.__dict__))
            r_col.collection = True
            rpath = self.get_path(r)
            rpath_col = self.get_path(r_col)
            api.add_resource(r, rpath)
            self.routes.append((r.__name__, rpath, rpath_col))
            api.add_resource(r_col, rpath_col)

        # Register extensions required by Flask-Flash
        register_extensions(self.app, EXTENSIONS_API)

        # Register API blueprint to Flask app
        self.app.register_blueprint(bp, url_prefix=os.environ.get('FLASK_API_PREFIX', '/api'))

        # Create server
        host = os.environ.get('FLASK_API_HOST', "0.0.0.0")
        port = os.environ.get('FLASK_API_PORT', 5001)
        self.server = Server(host, port)

        # Create API client
        self.client = self.create_api_client(host + ':' + str(port))

        # Create db migrater
        migrate = Migrate(self.app, db)

        # Create manager
        self.manager = Manager(self.app)
        self.shell = Shell(make_context=lambda: dict(app=self.app, db=db))
        self.manager.add_command("runserver", self.server)
        self.manager.add_command("shell", self.shell)
        self.manager.add_command("db", MigrateCommand)

    def get_path(self, resource):
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
        """Returns an instance of `BaseClient` configured with the endpoints."""
        c = BaseClient(url, **kwargs)
        for r in self.routes:
            c.add(CRUDEndpoint, r[1].replace('/<id>', ''), r[2])
            print c.__dict__
        return c

def create_app(config, resources):
    """Create the Flask app.
    This function accomplishes the following:
      * Create the Flask application object.
      * Load our config into the app.
      * Load application data (if needed) locally (data files will be loaded in
        data/ folder).
      * Register the Flask extensions defined in `extensions.py`.
      * Inject variables needed by all our Jinja2 templates.

    Args:
        profile_name (str): The name of the profile to use.

    Returns:
        :obj:`flask.Flask`: The Flask application object.
    """
    api_bp = Blueprint('api', __name__)
    api = Api(api_bp)
    for (model, path) in resources:
        api.add_resource(model, path)
    app = Flask(__name__)
    if not profile in config.keys():
        raise Exception("Profile %s does not exist. Check your `config` dict." % profile)
    cfg = config[profile]
    cfg.init_app(app)
    app.config.from_object(cfg)
    register_extensions(app, EXTENSIONS_API)
    app.register_blueprint(api_bp, url_prefix=os.environ.get('FLASK_API_PATH', '/api'))
    server = Server(
        host=os.environ.get('FLASK_API_HOST', "0.0.0.0"),
        port=os.environ.get('FLASK_API_PORT', 5001)
    )
    def make_shell_context():
        return dict(app=app, db=db)
    manager = Manager(app)
    migrate = Migrate(app, db)
    manager.add_command("runserver", server)
    manager.add_command("shell", Shell(make_context=make_shell_context))
    manager.add_command("db", MigrateCommand)
    return app, manager, migrate

def register_extensions(app, extensions):
    """Register all Flask extensions defined in `extensions.py` with our Flask
    app.

    Args:
        app: The Flask application.
        extensions (list): A list of instances of Flask extensions.
    """
    c = 0
    for e in extensions:
        if isinstance(e, tuple) and e[1] == 'cache': # Flask-Cache extension
            log.info(app.config)
            e[0].init_app(app, config=app.config['CACHE_CONFIG'])
            c += 1
        else:
            try:
                e.init_app(app)
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
