import logging, pprint, json, yaml, time
from flask import g, request, Response, url_for, jsonify, current_app
from flask_restful import abort, Resource
from flask_restful.reqparse import RequestParser
from redis import Redis
from sqlalchemy import desc, asc
from extensions import db, auth, cache
from utils import *
from datetime import datetime
from sqlalchemy.inspection import inspect

log = logging.getLogger(__name__)
log_access = logging.getLogger(__name__ + '_access')
pp = pprint.PrettyPrinter(indent=4)

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
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise Exception('Boolean value expected.')

#----------------#
# API Exceptions #
#----------------#
class APIException(Exception):
    def __init__(self, code, message):
        self._code = code
        self._message = message

    @property
    def code(self):
        return self._code

    @property
    def message(self):
        return self._message

    def __str__(self):
        return self.__class__.__name__ + ': ' + self.message


class NoPostData(APIException):
    """Custom exception when POST data is empty."""
    def __init__(self, model_name):
        message = 'No data in POST request.'
        super(NoPostData, self).__init__(400, message)


class SchemaValidationError(APIException):
    """Custom exception when POST data is not validated by the schema."""
    def __init__(self, model_name, errors={}):
        super(SchemaValidationError, self).__init__(400, json.dumps(errors))


class MissingParameter(APIException):
    """Custom exception when a parameter is missing (for POST requests)."""
    def __init__(self, model_name, param):
        message = 'Missing parameter {}.{} in request.'.format(model_name.title(), param)
        super(MissingParameter, self).__init__(400, message)


class ResourceNotFound(APIException):
    """Custom exception when resource is not found."""
    def __init__(self, model_name, id):
        message = 'Resource {} {} not found.'.format(model_name.title(), id)
        super(ResourceNotFound, self).__init__(404, message)


class ResourceAlreadyExists(APIException):
    """Custom exception when resource already exist."""
    def __init__(self, model_name, id):
        message = 'Resource {} {} already exist.'.format(model_name.title(), id)
        super(ResourceAlreadyExists, self).__init__(409, message)


class Forbidden(APIException):
    """Custom exception when trying to modify a field that is forbidden."""
    def __init__(self, model_name, field):
        message = 'Not allowed to filter on (or modify) {}.{}.'.format(model_name.title(), field)
        super(Forbidden, self).__init__(403, message)


class InvalidFilter(APIException):
    def __init__(self, model_name, param):
        message = 'Invalid filter for model {}: {}.'.format(model_name.title(), param)
        super(InvalidFilter, self).__init__(400, message)


class FilterNotSupported(APIException):
    def __init__(self, model_name, param):
        message = 'Filter not supported for model {}: {}.'.format(model_name, param)
        super(FilterNotSupported, self).__init__(400, message)


class InvalidNumberOfParameters(APIException):
    def __init__(self, model_name, op, length):
        message = 'Invalid number of parameter ({}) operation {} on model {}.'.format(length, op, model_name)
        super(InvalidNumberOfParameters, self).__init__(400, message)

#-----------#
# Resources #
#-----------#
class Protected(Resource):
    """A Flask Restful resource protected by login."""
    decorators = [auth.login_required]

class CRUD(Resource):
    """A Flask Restful resource implementing CRUD.
    Create an API resource to GET / POST / PUT / DELETE / HEAD based only on a
    db model and a schema.

    Note:
        API Resources derived from this class need to set two class attributes:
        `model (db.Model)` and `schema (ma.modelSchema)`.

    Example:
        A CRUD resource using this model can be defined like:

        > from ccc_db.models import MyModel, MyModelSchema
        > from app.api.core import CRUD
        >
        > class MyAPIEndpoint(CRUD)
        >    model = MyModel
        >    schema = MyModelSchema
    """
    SUPPORTED_OPERATORS = {
        '==': 'eq',
        '<=': 'le',
        '<': 'lt',
        '>=': 'ge',
        '>': 'gt',
        '!=': 'ne'
    }

    # Overridable defaults
    methods = ['GET', 'POST', 'PUT', 'DELETE']
    cached = True

    def __init__(self):
        # Decorate get function to enable caching
        if self.cached: self.get = cache.cached(query_string=True)(self.get)

        # Set primary key name directly from db model
        self.pk = inspect(self.model).primary_key[0].name
        self.model_title = self.model.__name__.title()
        self.q = self.model.query
        self.columns = [column.key for column in inspect(self.model).attrs]
        self.excluded_fields = self._get_excluded_fields()
        self.parser = RequestParser()
        for c in self.columns:
            self.parser.add_argument(c, type=liststr, default=None, location='args')
        self.parser.add_argument('page',     type=int, default=1, location='args')
        self.parser.add_argument('per_page', type=int, default=10, location='args')
        self.parser.add_argument('paginate', type=str2bool, default=True, location='args')
        self.parser.add_argument('order_by', type=str, default=self.pk, choices=self.columns, location='args')
        self.parser.add_argument('sort',     type=str, default='desc', choices=['asc', 'desc'], location='args')
        self.parser.add_argument('only',     type=liststr, default=(), location='args')
        self.parser.add_argument('exclude',  type=liststr, default=(), location='args')
        self.parser.add_argument('match',    type=jsonlist, default=[], location='args')
        self.parser.add_argument('sort',     type=str, default=None, location='args')
        self.parser.add_argument('cache',    type=str2bool, default=True, location='args')

    def parse_args(self):
        args = self.parser.parse_args()
        log.info(args)
        model_filters, unique_args = {}, {}
        for k, v in args.items():
            if k in self.columns:
                if v is not None:
                    model_filters[k] = v
            else:
                unique_args[k] = v
        return model_filters, unique_args

    def head(self):
        c, g = self.parse_args()
        self.filter_query(g, c)
        try:
            resp = Response(mimetype='application/json')
            resp.headers = {
                "Content-Type": "application/json",
                "data": {
                    "count": self.q.count()
                }
            }
            return resp
        except Exception as e:
            log.exception(e)
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

    def get(self, id=None):
        try:
            start = time.time()
            c, g = self.parse_args()
            if id is not None:
                many = False
                elems = self.q.get(id)
                if not elems or elems is None:
                    raise ResourceNotFound(self.model_title, id)
            else:
                many = True
                self.filter_query(g, c)
                if g['paginate']:
                    elems = self.q.paginate(g['page'], g['per_page'], False).items
                else:
                    elems = self.q.all()
                    if not elems or elems is None: return []
            end = time.time()
            log.debug("GET | {url} | {time:.4f}s".format(url=request.url, time=(end - start)))
            return self.schema(many=many,
                               only=g['only'],
                               exclude=g['exclude']).jsonify(elems)

        except APIException as e:
            abort(e.code, message=str(e))

        except Exception as e:
            log.exception(e)
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

    def put(self, id=None):
        """TODO: Convert data loading to Marshmallow schema load."""
        try:
            # Get update list
            data = request.get_json()
            if not isinstance(data, list):
                data = [data]

            # Loop through updates
            ids = []
            for d in data:

                # Convert date fields
                try:
                    d = self.schema().on_load(d)
                except AttributeError:
                    pass

                # Get object id
                oid = id or d.get(self.pk)
                ids.append(oid)
                if oid is None:
                    raise MissingParameter(self.model_title, self.pk)
                d[self.pk] = oid

                # Done field
                done = d.get('done', False)
                if done:
                    d['end_date'] = datetime.utcnow()
                dbo = self.q.get(oid)
                if not dbo:
                    raise ResourceNotFound(self.model_title, oid)
                log.info("{model} {id} | PUT {params}".format(
                            model=self.model_title, id=oid,
                            params=reprd(d)))
                for k, v in d.items():
                    if k == self.pk:
                        continue
                    if not hasattr(self.model, k) or k in self.excluded_fields:
                        raise Forbidden(self.model_title, k)
                    if isinstance(v, list) or isinstance(v, dict): # JSON, convert to string
                        v = json.dumps(v)
                    if isbool(v): # bool string, convert to bool
                        v = str2bool(v)
                    log.debug("%s | %s" % (k, v))
                    try:
                        setattr(dbo, k, v)
                    except AttributeError:  # Try to update a field that has no attribute '_sa_instance_state'
                        continue
                db.session.add(dbo)
            db.session.commit()

            # Clear cache
            if self.cached: self.clear_cache(id=id)

            # Get the updated objects from the db and return them as JSON
            id_attr = getattr(self.model, self.pk)
            objs = self.q.filter(id_attr.in_(ids)).all()
            if id is not None and len(objs) == 1:
                return self.schema().jsonify(objs[0])
            return self.schema(many=True).jsonify(objs)

        except APIException as e:
            abort(e.code, message=str(e))

        except Exception as e:
            log.exception(e)
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

    def post(self):
        try:
            defs = request.get_json()
            if not defs:
                raise NoPostData(self.model_title)

            if not isinstance(defs, list):
                defs = [defs]

            log.info("{model} | POST {defs}".format(model=self.model_title, defs=reprd(defs)))

            # Validation + Objects creation
            dbos, errors = self.schema(many=True).load(defs, session=db.session)
            if errors:
                raise SchemaValidationError(self.model_title, errors=errors)

            # Add / Commit db objects
            db.session.add_all(dbos)
            db.session.commit()

            # Clear cache
            if self.cached: self.clear_cache()

            # Return created objects in JSON format
            if len(defs) == 1:
                return self.schema().jsonify(dbos[0])
            else:
                return self.schema(many=True).jsonify(dbos)

        except APIException as e:
            log.exception(e)
            abort(e.code, message=str(e))

        except Exception as e:
            log.exception(e)
            abort(500, message=str(e))

    def delete(self, id=None):
        try:
            if id is not None:
                dbo = self.q.get(id)
                if not dbo:
                    return jsonify({
                        self.pk: id,
                        'deleted': False,
                        'message': ResourceNotFound(self.model_title, id).message
                    })
                log.info("{model} | DELETE {id}".format(model=self.model_title, id=id))
                db.session.delete(dbo)
                db.session.commit()
                return jsonify({
                    self.pk: id,
                    'deleted': True
                })
            else:
                c, g = self.parse_args()
                g['order_by'], g['sort'] = None, None # .delete() cannot be called otherwise
                self.filter_query(g, c)
                count = self.q.count()
                self.q.delete()
                db.session.commit()
                return jsonify({
                    'count': count,
                    'deleted': True
                })

        except APIException as e:
            abort(e.code, message=str(e))

        except Exception as e:
            log.exception(e)
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

    def filter_query(self, g, c):
        self._filter_columns(c)
        self._filter_matches(g['match'])
        self._order_query(g['order_by'], g['sort'])

    def _order_query(self, order_by=None, sort=None):
        """Order the query and sort it based on 'order_by' and 'sort' parameters.

        Args:
            order_by: The model column to order by.
            sort: Descending ('desc'), ascending ('asc'), or None.
        """
        if order_by is not None:
            log.debug("Ordering query by key %s (%s)" % (order_by, sort))
            if not hasattr(self.model, order_by):
                raise Forbidden(self.model_title, order_by)
            column_obj = getattr(self.model, order_by)
            if sort == 'desc':
                self.q = self.q.order_by(column_obj.desc())
            elif sort == 'asc':
                self.q = self.q.order_by(column_obj.asc())
            else:
                self.q = self.q.order_by(column_obj)

    def _filter_columns(self, params):
        """Filter the query based on column key/value parameters.

        Args:
            query: The SQLAlchemy query object.
            params: A list of dict columns name / value to filter on.
        """
        for k, v in params.items():
            column = getattr(self.model, k, None)
            if column is None:
                continue
            if k in self.excluded_fields:
                raise Forbidden(self.model_title, k)
            if len(v) == 1:
                v = v[0]
                if isbool(v): # boolean string, convert
                    v = str2bool(v)
                    self.q = self.q.filter(column.is_(v))
                    continue
                if 'date' in k: # date, convert
                    v = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                log.debug("Filtering %s == %s" % (k, v))
                self.q = self.q.filter(column == v)
            else:
                self.q = self.q.filter(column.in_(v))

    def _filter_matches(self, filters):
        """Filters query based on operators.

        Args:
            query: The SQLAlchemy query object.
            filters: A list of lists / tuples, ie: [[key, operator, value], ...]
        """
        for raw in filters:
            try:
                key, op, values = tuple(raw)
                log.debug("Key: %s | Op: %s | Value: %s" % (key, op, values))
                if isinstance(values, basestring):
                    values = values.split(',')
            except ValueError as e:
                log.exception(e)
                raise InvalidFilter(self.model_title, raw)
            column = getattr(self.model, key, None)
            if column is None:
                continue
            if key in self.excluded_fields:
                raise Forbidden(self.model_title, k)

            # Handle '~' operator
            if op == '~':
                self.q = self.q.filter(self.model.name.op('~')(values))

            # Handle 'in' operator
            if op == 'in':
                self.q = self.q.filter(column.in_(values))

            # Handle 'between' operator
            elif op == 'between':
                self.q = self.q.filter(column.between(values[0], values[1]))

            # Handle 'like' operator
            elif op == 'like':
                for v in values:
                    self.q = self.q.filter(column.like(v + '%'))

            # Handle all other operators ('==', '>=', '<=', 'like', ...)
            else:
                op = self.SUPPORTED_OPERATORS.get(op) or op
                if not isinstance(values, list):
                    values = [values]
                for v in values:
                    try:
                        attr = list(filter(lambda e: hasattr(column, e % op),
                                          ['%s', '%s_', '__%s__']))[0] % op
                    except IndexError:
                        raise FilterNotSupported(self.model_title, op)
                    self.q = self.q.filter(getattr(column, attr)(v))

    def _get_excluded_fields(self):
        try:
            return self.schema.Meta.exclude
        except Exception as e:
            return ()

    def clear_cache(self, **params):
        # Note: we have to use the Redis client to delete key by prefix,
        # so we can't use the 'cache' Flask extension for this one.
        config = current_app.config['CACHE_CONFIG']
        redis_client = Redis(config['CACHE_REDIS_HOST'], config['CACHE_REDIS_PORT'])
        endpoint = self.get_resource_url(**params)
        key_prefix = config['CACHE_KEY_PREFIX'] + endpoint
        keys = [key for key in redis_client.keys() if key.startswith(key_prefix)]
        nkeys = len(keys)
        for key in keys:
            redis_client.delete(key)
        if nkeys > 0:
            log.debug("Cleared %s cache keys" % nkeys)
            log.debug(keys)

    def get_resource_url(self, **params):
        return url_for('api.' + self.__class__.__name__.lower(), **params)
