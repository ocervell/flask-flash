import logging, pprint, json, yaml, time
from flask import g, request, Response, url_for, jsonify
from flask_restful import abort, Resource
from flask_restful.reqparse import RequestParser
from redis import Redis
from sqlalchemy import desc, asc
from extensions import db, auth
from utils import *
from datetime import datetime

log = logging.getLogger(__name__)
log_access = logging.getLogger(__name__ + '_access')
pp = pprint.PrettyPrinter(indent=4)

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
    METHODS = ['head', 'get', 'put', 'post', 'delete']

    # parser = RequestParser()
    # parser.add_argument('page', type=int, default=1, location='args')
    # parser.add_argument('per_page', type=int, default=10, location='args')
    # parser.add_argument('paginate', type=bool, default=True, location='args')
    # parser.add_argument('order_by', type=str, default='', location='args')
    # parser.add_argument('sort', type=str, default='asc', choices=['asc', 'desc'], location='args')

    def head(self):
        query = self.model.query
        kwargs = request.args.to_dict()
        kwargs.pop('order_by', None)
        kwargs.pop('sort', None)
        config = self.parse_unique(kwargs)
        query = self.filter_query(self.model.query, config, kwargs)
        try:
            count = query.count()
            resp = Response(mimetype='application/json')
            resp.headers = {
                "Content-Type": "application/json",
                "data": {
                    "count": count
                }
            }
            return resp
        except Exception as e:
            log.exception(e)
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

    def get(self, id=None):
        start = time.time()
        model_name = self.model.__name__.title()
        kwargs = request.args.to_dict()
        many = True
        try:
            if id is not None:
                many = False
                elems = self.model.query.get(id)
                if not elems or elems is None:
                    raise ResourceNotFound(model_name, id)
                return self.schema().jsonify(elems)
            else:
                config = self.parse_unique(kwargs)
                query = self.filter_query(self.model.query, config, kwargs)
                if config['paginate']:
                    elems = query.paginate(config['page'], config['per_page'], False).items
                else:
                    elems = query.all()
                    if not elems or elems is None:
                        return []
            end = time.time()
            log.debug("GET | {url} | {time:.4f}s".format(url=request.url, time=(end - start)))
            return self.schema(many=many,
                               only=config['only'],
                               exclude=config['exclude']).jsonify(elems)

        except APIException as e:
            abort(e.code, message=str(e))

        except Exception as e:
            log.exception(e)
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

    def put(self, id=None):
        """TODO: Convert data loading to Marshmallow schema load."""
        model_name = self.model.__name__.title()
        try:
            # Get update list
            updates = request.get_json()
            if not isinstance(updates, list):
                updates = [updates]

            # Loop through updates
            ids = []
            for update_dict in updates:

                # Convert date fields
                try:
                    update_dict = self.schema().on_load(update_dict)
                except AttributeError:
                    pass

                # Get object id
                oid = id or update_dict.get('id')
                ids.append(oid)
                if oid is None:
                    raise MissingParameter(model_name, 'id')
                update_dict['id'] = oid

                # Done field
                done = update_dict.get('done', False)
                if done:
                    update_dict['end_date'] = datetime.utcnow()
                dbo = self.model.query.get(oid)
                if not dbo:
                    raise ResourceNotFound(model_name, oid)
                log.info("{model} {id} | PUT {params}".format(
                            model=model_name, id=oid,
                            params=reprd(update_dict)))
                for k, v in update_dict.items():
                    if k == 'id':
                        continue
                    if not hasattr(self.model, k) or k in self._get_excluded_fields():
                        raise Forbidden(model_name, k)
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

            # Get the updated objects from the db and return them as JSON
            id_attr = getattr(self.model, 'id')
            objs = self.model.query.filter(id_attr.in_(ids)).all()
            if id is not None and len(objs) == 1:
                return self.schema().jsonify(objs[0])
            return self.schema(many=True).jsonify(objs)

        except APIException as e:
            abort(e.code, message=str(e))

        except Exception as e:
            log.exception(e)
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

    def get_resource_url(self, **params):
        return url_for('api.' + self.__class__.__name__.lower(), **params)

    def post(self):
        try:
            model_name = self.model.__name__
            defs = request.get_json()
            if not defs:
                raise NoPostData(model_name)

            if not isinstance(defs, list):
                defs = [defs]

            log.info("{model} | POST {defs}".format(model=model_name, defs=reprd(defs)))

            # Validation + Objects creation
            dbos, errors = self.schema(many=True).load(defs, session=db.session)
            if errors:
                raise SchemaValidationError(model_name, errors=errors)

            # Add / Commit db objects
            for dbo in dbos:
                db.session.add(dbo)
            db.session.commit()

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

    def delete(self, id):
        model_name = self.model.__name__.title()
        try:
            dbo = self.model.query.get(id)
            if not dbo:
                return jsonify({
                    'id': id,
                    'deleted': False,
                    'message': ResourceNotFound(model_name, id).message
                })
            log.info("{model} | DELETE {id}".format(model=model_name, id=id))
            db.session.delete(dbo)
            db.session.commit()
            return jsonify({
                'id': id,
                'deleted': True
            })

        except APIException as e:
            abort(e.code, message=str(e))

        except Exception as e:
            log.exception(e)
            abort(500, message='%s - %s' % (type(e).__name__, str(e)))

    def filter_query(self, query, config, kwargs):
        model_name = self.model.__name__.title()
        query = self._filter_params(query, kwargs)
        query = self._filter_matches(query, config['match'])
        query = self._order_query(query, config['order_by'], config['sort'])
        return query

    def _order_query(self, query, order_by=None, sort=None):
        model_name = self.model.__name__.title()
        if order_by is not None:
            log.debug("Ordering query by key %s (%s)" % (order_by, sort))
            if not hasattr(self.model, order_by):
                raise Forbidden(model_name, order_by)
            column_obj = getattr(self.model, order_by)
            if sort == 'desc':
                query = query.order_by(column_obj.desc())
            elif sort == 'asc':
                query = query.order_by(column_obj.asc())
            else:
                query = query.order_by(column_obj)
        return query

    def _filter_params(self, query, params):
        """Return filtered query based on URL parameters.

        Parameters:
            query: The SQLAlchemy query object
            params: A dict of parameters extracted from the request URL

        Returns:
            query: The filtered SQLAlchemy query object
        """
        # log.debug("Filters (params): \n%s" % pprint.pformat(params))
        model_name = self.model.__name__.title()
        params = {k: v.split(',') for k, v in params.items()}
        for k, v in params.items():
            column = getattr(self.model, k, None)
            if column is None:
                continue
            if k in self._get_excluded_fields():
                raise Forbidden(model_name, k)
            if len(v) == 1:
                v = v[0]
                if isbool(v): # boolean string, convert
                    v = str2bool(v)
                    query = query.filter(column.is_(v))
                    continue
                if 'date' in k: # date, convert
                    v = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                log.debug("Filtering %s == %s" % (k, v))
                query = query.filter(column == v)
            else:
                query = query.filter(column.in_(v))
        return query

    def _filter_matches(self, query, filters):
        """Return filtered query based on filters.

        Parameters:
            query: The SQLAlchemy query object
            filters: A list of lists / tuples, ie: [[key, operator, value], ...]

        Returns:
            query: The filtered SQLAlchemy query object
        """
        # log.debug("Filters (matches): \n%s" % pprint.pformat(filters))
        model_name = self.model.__name__.title()  # returns the query's Model
        for raw in filters:
            try:
                key, op, values = tuple(raw)
                log.debug("Key: %s | Op: %s | Value: %s" % (key, op, values))
                if isinstance(values, basestring):
                    values = values.split(',')
            except ValueError as e:
                log.exception(e)
                raise InvalidFilter(model_name, raw)
            column = getattr(self.model, key, None)
            if column is None:
                continue
            if key in self._get_excluded_fields():
                raise Forbidden(model_name, k)

            # Handle '~' operator
            if op == '~':
                query = query.filter(self.model.name.op('~')(values))

            # Handle 'in' operator
            if op == 'in':
                query = query.filter(column.in_(values))

            # Handle 'between' operator
            elif op == 'between':
                query = query.filter(column.between(values[0], values[1]))

            # Handle 'like' operator
            elif op == 'like':
                for v in values:
                    query = query.filter(column.like(v + '%'))

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
                        raise FilterNotSupported(model_name, op)
                    query = query.filter(getattr(column, attr)(v))
        return query

    def parse_unique(self, kwargs):
        # TODO: Replace the following 10 lines by a RequestParser instance.
        paginate = str2bool(kwargs.pop('paginate', 'True'))
        per_page = int(kwargs.pop('per_page', '10'))
        page = int(kwargs.pop('page', '1'))
        only = [f for f in tuple(kwargs.pop('only', '').split(',')) if f]
        exclude = [f for f in tuple(kwargs.pop('exclude', '').split(',')) if f]
        match = yaml.safe_load(kwargs.pop('match', '[]'))
        order_by = kwargs.pop('order_by', None)
        sort = kwargs.pop('sort', None)
        cache = kwargs.pop('cache', True) # don't remove even if unused
        return {
            'paginate': paginate,
            'per_page': per_page,
            'page': page,
            'only': only,
            'exclude': exclude,
            'match': match,
            'order_by': order_by,
            'sort': sort,
            'cache': cache
        }

    def _get_model_name(self):
        return self.__class__.__name__.replace('Id', '').replace('List', '')

    def _get_excluded_fields(self):
        try:
            return self.schema.Meta.exclude
        except Exception as e:
            return ()

def abort_400_if_not_belong(name, elem, group):
    if not elem:
        raise APIException(400, "{} needs to be in input data".format(name.title()))
    if elem not in group:
        raise APIException(400, "{0} {1} is invalid. List of valid {2}s: {3}".format(name.title(), elem, name, group))
