import os, logging
from flask import Blueprint, Flask, session
from flask_restful import Api
from flask_script import Manager, Shell, Server, prompt_bool
from flask_migrate import Migrate, MigrateCommand
from client import *
from core import *
from extensions import *
from utils import *
import inspect

log = logging.getLogger(__name__)
DEFAULT_PROFILE = os.environ.get('FLASK_API_PROFILE', 'default')

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
        cfg.init_app(self.app)
        self.app.config.from_object(cfg)

        # Create Flask-Restful API
        bp = Blueprint('api', __name__)
        self.api = Api(bp)

        # Add API resources to API
        self.register_resources()

        # Register extensions required by Flask-Flash
        self.register_extensions(extensions=kwargs.get('extensions', []))

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
        """Infer partial URL of resource based on resource.__class__.__name__
        and / or from params 'resource.path', 'resource.path_prefix',
        'resource.path_collection'
        """
        prefix = getattr(resource, 'path_prefix', '')
        suffix = getattr(resource, 'path', self.get_default_suffix(resource))
        prefix = '/' + prefix if not prefix.startswith('/') else prefix
        suffix = suffix[1:] if suffix.startswith('/') else suffix
        collection = getattr(resource, 'collection', False)
        path = os.path.join(prefix, suffix)
        if collection:
            pathc = getattr(resource, 'path_collection', path.replace('_collection', '') + 's')
            path = pathc
        else:
            paths = os.path.join(path, '<id>')
            path = paths
        log.info("%s --> %s" % (resource.__name__, path))
        return path

    def get_default_suffix(self, resource):
        matches = re.findall('[A-Z][^A-Z]*', resource.__name__)
        if matches:
            return os.path.join('/', *matches).lower()
        return os.path.join('/', resource.__name__).lower()

    def create_api_client(self, url='localhost:5001', **kwargs):
        """Create an API client from the API routes definitions."""
        c = BaseClient(url, **kwargs)
        for r in self.routes:
            c.register(CRUDEndpoint, r[1].replace('/<id>', ''), r[2])
        return c

    def register_resources(self):
        """Register all API resources with our Flask-Restful API."""
        for r in self.resources:
            parent_classes = [i.__name__ for i in inspect.getmro(r)]
            if 'CRUD' in parent_classes:
                # Duplicate 'single' resource to make identical one for 'collection'
                r_col = type(r.__name__ + '_collection', r.__bases__, dict(r.__dict__))
                r_col.collection = True

                # Get resource paths (from class name or through class attribute 'path')
                rpath = self.get_path(r)
                rpath_col = self.get_path(r_col)

                # Add resources to API
                self.api.add_resource(r, rpath)
                self.api.add_resource(r_col, rpath_col)
                self.routes.append((r.__name__, rpath, rpath_col))
            else:
                rpath = getattr(r, 'path', None)
                if rpath is not None:
                    if isinstance(r.path, list):
                        self.api.add_resource(r, *rpath)
                    else:
                        self.api.add_resource(r, rpath)
                else:
                    rpath = os.path.join('/', *re.findall('[A-Z][^A-Z]*', r.__name__)).lower()
                    self.api.add_resource(r, rpath)

    def register_extensions(self, extensions=[]):
        """Register all Flask extensions defined in `extensions.py` with our Flask
        app.
        """
        c = 0
        EXTENSIONS_API.extend(extensions)
        for e in EXTENSIONS_API:
            if isinstance(e, tuple) and e[1] == 'cache': # Flask-Cache extension
                try:
                    e[0].init_app(self.app, config=self.app.config['CACHE_CONFIG'])
                except AssertionError:
                    continue
                c += 1
            else:
                try:
                    e.init_app(self.app)
                    c += 1
                except (AttributeError, ValueError, AssertionError):
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
