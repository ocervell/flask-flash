"""
extensions.py
~
Maintainer: Olivier Cervello.
Description: Definition of all Flask-Flash API resources.
"""
import logging, pprint, json, yaml, time
from flask import g, request, Response, url_for, jsonify, current_app
from flask_restful import abort, Resource as FlaskRestfulResource
from flask_restful.reqparse import RequestParser
from sqlalchemy import desc, asc
from sqlalchemy.orm.session import make_transient
from extensions import db, auth, cache, ma
from utils import *
from decorators import json, errorhandler, add_schema
from exceptions import NoPostData, SchemaValidationError, ResourceNotFound, \
                        ResourceFieldForbidden, FilterInvalid, \
                        FilterNotSupported
from datetime import datetime
from sqlalchemy.inspection import inspect
import re
from os.path import join
import os
import inflect
import inspect as inspc
from functools import wraps
import marshmallow

log = logging.getLogger(__name__)

#----------------#
# Regparse types #
#----------------#
def liststr(value):
    try:
        return value.split(',')
    except:
        return value

def jsonlist(value):
    try:
        return yaml.safe_load(value)
    except:
        return []

def str2bool(v):
    if v.lower() in ('yes', 'true', 'True', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'False', 'f', 'n', '0'):
        return False
    else:
        raise Exception('Boolean value expected.')

#-----------#
# Resources #
#-----------#
class Resource(FlaskRestfulResource):
    """The base Flask-Flash resource to inherit from."""

    """list: methods
    The HTTP methods enabled for this resource.
    """
    methods = ['GET', 'POST', 'PUT', 'DELETE']

    """bool: cached
    Add a cache to the resource on `GET`. Derived implementations are responsible
    for clearing the cache when required.
    """
    cached = True

    """dict: permissions
    A dict of permissions indexed by the HTTP method name.
    """
    permissions = {}

    """str: url, optional
    The url for the resource. Auto-generate path if omitted.
    """
    url = ''

    """str: url_prefix, optional
    The url_prefix for the resource. Default: '/'
    """
    url_prefix = '/'

    @classmethod
    def resource_name(cls):
        return cls.__name__

    @classmethod
    def get_default_url(cls):
        """Default URL for a Flask-Flash resource.
        Converts a CamelCase resource name into an API url.
        """
        fragments = re.findall('[A-Z][^A-Z]*', cls.__name__)
        if fragments:
            return join(cls.url_prefix, *fragments).lower().replace('\\', '/')
        return join(cls.url_prefix, cls.__name__).lower().replace('\\', '/')

    # @classmethod
    # TODO: Work on autogeneration of resource names for non-CRUD resources
    # def build_url(cls, url):
    #     """Builds URL from a resource URL and append optional parameters defined
    #     in 'GET' function to it."""
    #     urls = []
    #     if hasattr(cls, 'get'):
    #         params = inspec.getargspec(cls.get).args
    #         url = join(url.rstrip('/'), *['<' + p + '>' for p in params if p != 'self'])
    #         params = re.findall(r'(<\w+>)', url)
    #         while (len(params) > 0):
    #             p = params.pop()
    #             urls.append(url)
    #             url = url.replace(p, '').rstrip('/')
    #     return urls


    @classmethod
    def get_urls(cls):
        """Builds the resource URL(s), either from class parameters (cls.url) or
        generates default url from resource class name.
        """
        if not cls.url:
            urls = [cls.get_default_url()]
        elif isinstance(cls.url, list):
            urls = [join(cls.url_prefix, u.rstrip('/')) for u in cls.url]
        else:
            urls = [join(cls.url_prefix, cls.url.rstrip('/'))]
        urls = map(lambda x: x.replace('\\', '/'), urls)
        return urls

    @classmethod
    def get_routes(cls):
        routes = [(u, cls.get_endpoint(u)) for u in cls.get_urls()]
        return routes

    @classmethod
    def get_endpoint(cls, url):
        return None

class Index(Resource):
    """A Flash resource listing all the endpoints."""
    pass


class Protected(Resource):
    """A Flash resource protected by login."""
    decorators = [auth.login_required]


class CRUD(Resource):
    """A Flash resource implementing CRUD model.

    This resource exposes GET / POST / PUT / DELETE / HEAD HTTP methods based
    only on a db model and a schema.

    CRUD resources will be registered by Flask-Flash with two different routes:
    single, multiple. Those can be user defined or automatically infered from
    the resource class name.

    Example:

        >>> from models import *
        >>> from flask_flash import Resource, Protected, CRUD
        >>>
        >>> class MyPrefixAction(CRUD):
        >>>    model = ActionModel
        >>>    schema = ActionSchema
        >>>
        >>> class Batch(CRUD):
        >>>     url = ('/batch', '/batches')
        >>>     url_prefix = '/my/prefix'
        >>>     model = BatchModel
        >>>     schema = BatchSchema

    The above code will generate the following routes:
        MyPrefixAction: ("/my/prefix/action/<id>", "/my/prefix/actions")
        Batch:          ("/my/prefix/batch/<id>" , "/my/prefix/batches")
    """

    """obj:`flask_sqlalchemy.Model`, required
    The Flask SQLAlchemy database model.
    """
    model = None

    """obj:`flask_marshmallow.ModelSchema`, optional
    The Flask Marshmallow schema.
    """
    schema = None

    """str: pk, optional
    The primary key to use for routing. Defaults to first primary key found
    in the model if omitted.
    """
    pk = ''

    """obj:`flask_sqlalchemy.BaseQuery`, optional
    The query object to use. Defaults to `self.model.query` if omitted.
    """
    query = None

    """bool: cached, optional
    Use cache on GET queries (recommended).
    Cache is cleared on POST / PUT / DELETE
    """
    cached = True

    """dict: SQLALCHEMY_OPERATORS, fixed
    A list of SQLAlchemy operator translations for query.
    """
    SQLALCHEMY_OPERATORS = {
        '==': 'eq',
        '<=': 'le',
        '<': 'lt',
        '>=': 'ge',
        '>': 'gt',
        '!=': 'ne'
    }

    def __init__(self):
        # Decorate get function to enable caching
        # self.get = cache.cached(query_string=True)(self.get)
        log.debug("Request URL: %s" % request.url)

        # Set schema from db model if not set
        if self.schema is None:
            if not hasattr(self.model, 'Schema'):
                self.model = add_schema(self.model)
            self.schema = self.model.Schema

        # Set primary key name directly from db model
        self.pk = self.pk or inspect(self.model).primary_key[0].name
        self.model_title = self.model.__name__
        self.columns = inspect(self.model).columns.keys()
        self.relationships = inspect(self.model).relationships.keys()
        self.parser = RequestParser()
        for c in self.columns:
            self.parser.add_argument(c, type=liststr, default=None, location='args')
        self.parser.add_argument('page', type=int, default=1, location='args')
        self.parser.add_argument('per_page', type=int, default=10, location='args')
        self.parser.add_argument('paginate', type=str2bool, default=True, location='args')
        self.parser.add_argument('order_by', type=str, default=self.pk, choices=self.columns, location='args')
        self.parser.add_argument('sort', type=str, default='desc', choices=['asc', 'desc'], location='args')
        self.parser.add_argument('only', type=liststr, default=(), location='args')
        self.parser.add_argument('exclude', type=liststr, default=(), location='args')
        self.parser.add_argument('match', type=jsonlist, default=[], location='args')
        self.parser.add_argument('cache', type=str2bool, default=True, location='args')
        self.parser.add_argument('_action', type=str, default='overwrite', choices=['overwrite', 'append'], location='args')
        self.fields, self.opts = self._parse_args()
        self.request_args = self.fields.copy()
        self.request_args.update(self.opts)
        self.request_args = {k:v for k,v in self.request_args.items() if v}

    @classmethod
    def get_urls(cls):
        """Builds the resource URL(s), either from class parameters (cls.url,
        cls.url_prefix) or generates URLs by splitting the resource name by
        capital letters.
        Generates the plural for the 'collection' url by using `inflect`
        module.
        """
        urls = []
        default = cls.get_default_url()
        if not cls.url: # get default urls from class name
            single = join(default, '<id>')
            multiple = inflect.engine().plural(default)
        elif len(cls.url) == 2: # get user-defined urls
            urls = [u.rstrip('/') for u in cls.url]
            if not urls[0]:
                urls[0] = join(default, '<id>')
            if not urls[1]:
                urls[1] = inflect.engine().plural(default)
            single = join(cls.url_prefix, urls[0], '<id>')
            multiple = join(cls.url_prefix, urls[1])
        else:
            raise TypeError("`url` must be either omitted or a tuple of size 2 for CRUD resources.")

        # Replace \ by / on Windows
        single = single.replace('\\', '/')
        multiple = multiple.replace('\\', '/')
        return [single, multiple]

    @classmethod
    def get_endpoint(cls, url):
        return ''.join(re.sub('/<\w+>', '', url).split('/')[1:])

    @property
    def original_query(self):
        return self.query or self.model.query

    def get_query(self,
            skip_column_filter=False,
            skip_operation_filter=False,
            skip_order_query=False,
            skip_paginate_query=False):
        """Get the filtered query from the request parameters."""
        query = self.original_query
        fields = self.fields
        filters = self.opts.get('match')
        order_by = self.opts.get('order_by')
        sort = self.opts.get('sort')
        limit = self.opts.get('limit')
        offset = self.opts.get('offset')
        paginate = self.opts.get('paginate')
        page = self.opts.get('page')
        per_page = self.opts.get('per_page')

        # Direct filter on column (field=value syntax)
        if not skip_column_filter and fields and request.method in ['HEAD', 'GET', 'PUT', 'DELETE']:
            self.raise_if_forbidden(fields)
            log.debug("Filtering on columns: %s" % fields)
            fields = self.convert_fields(fields)
            for k, v in fields.items():
                column = getattr(self.model, k, None)
                if isinstance(v, list):
                    query = query.filter(column.in_(v))
                else:
                    query = query.filter(column == v)

        # Filter on column by operation (match=[filter1, filter2, ..] syntax)
        if not skip_operation_filter and filters is not None and request.method in ['HEAD', 'GET', 'PUT', 'DELETE']:
            self.raise_if_forbidden([f[0] for f in filters])
            log.debug("Filtering with filters: %s" % filters)
            for raw in filters:
                try:
                    key, op, values = tuple(raw)
                    log.debug("Key: %s | Op: %s | Value: %s" % (key, op, values))
                    if isinstance(values, basestring): values = values.split(',')
                except ValueError as e:
                    raise FilterInvalid(self.model_title, raw)
                column = getattr(self.model, key, None)
                if column is None:
                    continue

                # Handle '~' operator
                if op == '~':
                    query = query.filter(self.model.name.op('~')(values))

                # Handle 'in' operator
                elif op == 'in':
                    query = query.filter(column.in_(values))

                # Handle 'between' operator
                elif op == 'between':
                    query = query.filter(column.between(values[0], values[1]))

                # Handle 'like' operator
                elif op == 'like':
                    for v in values:
                        query = query.filter(column.like(v + '%'))

                # Handle all other operators ('==', '>=', '<=', ...)
                else:
                    op = self.SQLALCHEMY_OPERATORS.get(op) or op
                    if not isinstance(values, list):
                        values = [values]
                    for v in values:
                        try:
                            attr = list(filter(lambda e: hasattr(column, e % op),
                                              ['%s', '%s_', '__%s__']))[0] % op
                        except IndexError:
                            raise FilterNotSupported(self.model_title, op)
                        query = query.filter(getattr(column, attr)(v))

        # Order query by field (order_by=<field>, sort=asc/desc syntax)
        if not skip_order_query and order_by is not None and request.method in ['GET', 'PUT']:
            self.raise_if_forbidden(order_by)
            log.debug("Ordering query by key %s (%s)" % (order_by, sort))
            column_obj = getattr(self.model, order_by)
            if sort == 'desc':
                query = query.order_by(column_obj.desc())
            elif sort == 'asc':
                query = query.order_by(column_obj.asc())
            else:
                query = query.order_by(column_obj)

        # Paginate query (paginate=true/false, per_page=<n>, page=<n> syntax)
        if not skip_paginate_query and paginate is True and request.method in ['GET', 'PUT']:
            log.debug("Pagination enabled | Page: %s | Records per page: %s" % (page, per_page))
            query = query.paginate(page, per_page, False)

        # Return query
        return query

    #--------------------#
    # CRUD HTTP Methods #
    #--------------------#
    @errorhandler
    def head(self):
        resp = Response(mimetype='application/json')
        resp.headers = {
            "Content-Type": "application/json",
            "data": {
                "count": int(self.get_query().count())
            }
        }
        return resp

    @cache.cached(query_string=True, timeout=10)
    @json
    @errorhandler
    def get(self, id=None):
        if id is not None:
            objs = self.original_query.get(id)
            if not objs:
                raise ResourceNotFound(self.model_title, id)
        else:
            if self.opts['paginate']:
                objs = self.get_query().items
            else:
                objs = self.get_query().all()
        self.opts['many'] = (id is None)
        return objs

    @json
    @errorhandler
    def put(self, id=None):
        data = self.get_data()
        data = self._preprocess(data)

        # Loop through updates
        objs = []
        for d in data:
            self.raise_if_forbidden(d, type='write')

            # Check for object existence
            oid = d.pop(self.pk, None) or d.pop('id', None) or id
            if oid is None:
                raise ResourceFieldMissing(self.model_title, self.pk, request.method)

            # Get object to update
            log.debug("Updating %s.%s with update: \n%s" % (self.model_title, oid, pprint.pformat(d)))
            obj = self.original_query.get(oid)
            if not obj:
                 raise ResourceNotFound(self.model_title, oid)

            # Relationship updates
            if self.opts['_action'] == 'append':
                rel_updates = {k: v for k, v in d.items() if k in self.relationships}
                new, errors = self.schema().load(rel_updates, session=db.session, partial=True)
                if errors:
                    raise SchemaValidationError(self.model_title, errors=errors)
                make_transient(new) # to avoid IntegrityErrors
                for name in rel_updates:
                    rel_old = getattr(obj, name)
                    rel_new = getattr(new, name)
                    rel_old.extend(rel_new)
                d = {k: v for k, v in d.items() if k not in rel_updates}

            # Other updates
            _, errors = self.schema().load(d, instance=obj, session=db.session, partial=True)
            if errors:
                raise SchemaValidationError(self.model_title, errors=errors)

            # Add this db object
            objs.append(obj)

        # Add all objects and commit
        db.session.add_all(objs)
        db.session.commit()

        # Clear cache
        if self.cached: cache.clear()

        # Set 'many' option for jsonify
        self.opts['many'] = (id is None)
        return objs

    @json
    @errorhandler
    def post(self):
        data = self.get_data()
        data = self._preprocess(data)

        log.debug("POST | {model} | \n{data}".format(model=self.model_title, data=pprint.pformat((data))))

        # Validation + Objects creation
        objs, errors = self.schema(many=True).load(data, session=db.session)
        if errors:
            raise SchemaValidationError(self.model_title, errors=errors)

        # Add / Commit db objects
        db.session.add_all(objs)
        db.session.commit()

        # Clear cache
        if self.cached: cache.clear()

        # Set 'many' option for jsonify
        self.opts['many'] = (len(objs) > 1)
        return objs

    @errorhandler
    def delete(self, id=None):
        if id is not None:
            dbo = self.original_query.get(id)
            if not dbo:
                return jsonify({
                    self.pk: id,
                    'deleted': False,
                    'message': ResourceNotFound(self.model_title, id).message
                })
            db.session.delete(dbo)
            db.session.commit()
            if self.cached: cache.clear()
            return jsonify({
                'deleted': True
            })
        else:
            query = self.get_query(skip_order_query=True, skip_paginate_query=True)
            log.debug("Delete query: \n%s" % query)
            count = query.delete(synchronize_session='fetch')
            return jsonify({
                'deleted': True
            })

    #---------#
    # PRIVATE #
    #---------#
    def _preprocess(self, data):
        processors = getattr(self, request.method.lower() + '_preprocessors', [])
        for p in processors:
            data = p(data)
        return data

    def _parse_args(self):
        args = self.parser.parse_args()
        model_filters, unique_args = {}, {}
        for k, v in args.items():
            if k in self.columns:
                if v is not None:
                    model_filters[k] = v
            else:
                unique_args[k] = v
        log.debug("Model args: %s" % model_filters)
        log.debug("Unique args: %s" % unique_args)
        return model_filters, unique_args

    def convert_fields(self, fields):
        """Convert `fields` to their Python datatype using each Marshmallow
        field's `_deserialize` method.

        Args:
            fields (dict): A dict of column name / value(s).
        """
        self.raise_if_forbidden(fields)
        fields = {k: v for k, v in fields.items() if k in self.columns}
        res = {k: None for k in fields}
        schema = self.schema(partial=True)
        for k, values in fields.items():
            try:
                converted = schema.fields[k]._deserialize(values, None, None)
                res[k] = converted
            except marshmallow.ValidationError:
                if isinstance(values, list):
                    for v in values:
                        try:
                            converted = schema.fields[k]._deserialize(v, None, None)
                            if res[k] is None:
                                res[k] = [converted]
                            else:
                                res[k].append(converted)
                        except marshmallow.ValidationError:
                            pass
        return res

    def raise_if_forbidden(self, fields, type='read', allow_non_existent=True):
        """Raises a `ResourceFieldForbidden` exception if trying to access any
        'forbidden' field.

        Args:
            fields (dict / list): A dictionary or list of fields to check for
            'read' or 'write' access.
            type (str): 'read' or 'write'.
            allow_non_existent (bool): If set to False, raise if the field does
                not belong to model columns.
        """
        forbidden = [k for k in fields if k in self.get_schema_forbidden(type=type)]
        if allow_non_existent is False:
            forbidden.extend([k for k in fields if k not in self.columns and k not in self.relationships])
        if forbidden:
            raise ResourceFieldForbidden(self.model_title, forbidden[0])

    def get_schema_forbidden(self, type='read'):
        """Get fields that can't be modified, either for a 'read' operation
        (trying to access or search on a field) or a 'write' operation (trying
        to update a field).

        Args:
            type (str): 'read' or 'write'.
        """
        exclude = []
        try: # add `exclude` fields from schema `Meta` class
            exclude.extend(self.schema.Meta.exclude)
        except AttributeError:
            pass
        if type == 'write': # adding `dump_only` (read-only) fields from schema
            fields = self.schema().fields
            dump_only = filter(lambda x: fields[x].dump_only, fields)
            exclude.extend(dump_only)
        return exclude

    def get_data(self):
        data = request.get_json()
        if not data:
            raise NoPostData(self.model_title)
        if not isinstance(data, list):
            data = [data]
        return data

    def clear_cache(self, **params):
        """Clears the cache key(s) corresponding to `params`."""
        # Note: we have to use the Redis client to delete key by prefix,
        # so we can't use the 'cache' Flask extension for this one.
        config = current_app.config['CACHE_CONFIG']
        endpoint =  url_for('api.' + self.resource_name.lower(), **params)
        key_prefix = config['CACHE_KEY_PREFIX'] + endpoint
        redis_client = Redis(config['CACHE_REDIS_HOST'], config['CACHE_REDIS_PORT'])
        keys = [key for key in redis_client.keys() if key.startswith(key_prefix)]
        nkeys = len(keys)
        for key in keys:
            redis_client.delete(key)
        if nkeys > 0:
            log.debug("Cleared %s cache keys" % nkeys)
            log.debug(keys)
