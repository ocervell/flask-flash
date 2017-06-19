import os, logging
from flask import Blueprint, Flask, session
from flask_restful import Api
from extensions import *
from flask_script import Manager, Shell, Server, prompt_bool
from flask_migrate import Migrate, MigrateCommand

log = logging.getLogger(__name__)
profile = os.environ.get('FLASK_API_PROFILE', 'default')

def create_app(config, resources):
    """Create the Flask app.
    This function accomplishes the following:
      * Create the Flask application object.
      * Load our config into the app.
      * Load application data (if needed) locally (data files will be loaded in
        data/ folder).
      * Register the Flask extensions defined in `extensions.py`.
      * Register the Flask blueprints defined in `blueprints.py`.
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
            e[0].init_app(app, config=cfg.CACHE_CONFIG)
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

    def get(value, default=None):
        try:
            return getattr(self, value)
        except AttributeError:
            return default

    @staticmethod
    def init_app(app):
        pass
