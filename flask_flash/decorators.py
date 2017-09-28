"""
decorators.py
~
Maintainer: Olivier Cervello.
Description: Flask-Flash decorators.
"""
import time
import logging
from functools import wraps
from exceptions import APIException
from sqlalchemy.exc import SQLAlchemyError
from flask_restful import abort
from flask import request, jsonify
from extensions import db, ma
import urlparse
from os.path import join
import pprint

log = logging.getLogger(__name__)

def errorhandler(f):
    """Decorator handling all exceptions."""
    @wraps(f)
    def wrapper(self, *args, **kwds):
        try:
            start = time.time()
            ret = f(self, *args, **kwds)
            end = time.time()
            url = urlparse.urlparse(request.url)
            url_str = url.path
            params = urlparse.parse_qs(url.query)
            data = request.get_json()
            log.info("{fname} | {url} | {duration:.4f}s".format(
                fname=f.__name__.upper(),
                url=url_str,
                duration=(end - start)))
            if params:
                log.debug("URL Params: \n{params}".format(params=pprint.pformat(self.request_args)))
            if data:
                log.debug("Data: \n{data}".format(data=request.get_json()))
            return ret

        except APIException as e:  # API Exceptions
            abort(e.code, message=str(e))

        except SQLAlchemyError as e:  # Database Exceptions
            log.exception(e)
            db.session.rollback()
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

        except Exception as e:  # All other exceptions
            log.exception(e)
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

    return wrapper

def json(f):
    """Decorator handling object rendering."""
    @wraps(f)
    def wrapper(self, *args, **kwds):
        objs = f(self, *args, **kwds)
        marshmallow_fields = [
            'only',
            'exclude',
            'prefix',
            'strict',
            'many',
            'context',
            'load_only',
            'dump_only',
            'partial'
        ]
        schema_opts = { k: v for k, v in self.opts.items() if k in marshmallow_fields }
        if schema_opts.get('many', False) is False and \
                isinstance(objs, list) and \
                len(objs) == 1:
            objs = objs[0]
        if self.schema is not None:
            return self.schema(**schema_opts).jsonify(objs)
    return wrapper

def add_schema(cls):
    """Decorator to add a default schema to a model."""
    class Schema(ma.ModelSchema):
        class Meta:
            model = cls
    cls.Schema = Schema
    return cls

def shared(theClass):
    classInstances = {}
    def getInstance(*args, **kwargs):
        key = (theClass, args, str(kwargs))
        if key not in classInstances:
            classInstances[key] = theClass(*args, **kwargs)
        return classInstances[key]
    return getInstance
