from .agent import Agent
import logging, json, yaml, textwrap, pprint
import numpy as np
from cgi import escape

log = logging.getLogger(__name__)

def logit(func):
    def wrapper(*args, **kwargs):
        log.debug("Running %s with %s" % (func.__name__, args))
        ret = func(*args, **kwargs)
        log.debug("Exiting %s" % func.__name__)
        return ret
    return wrapper

class APIRequestException(Exception):
    def __init__(self, code, reason, description=None):
        self._code = code
        self._reason = reason
        self._description = description

    @property
    def code(self):
        return self._code

    @property
    def reason(self):
        return self._reason

    @property
    def description(self):
        return self._description

    def __str__(self):
        if self.description is not None:
            return "{} ({}) | {}".format(self.code, self.reason, self.description)
        else:
            return "{} ({})".format(self.code, self.reason)

class BaseClient(object):
    """Low level client that implements basic HTTP functions.

    Args:
        host (str, optional): The API hostname. Default: 'devopsconsole.aws.cccis.com'
        port (int, optional): The API port. Default: 80
        auth (tuple): A tuple containing username and password.
    """

    # HTTP Methods supported by this client
    SUPPORTED_HTTP_METHODS = [
        'get',
        'post',
        'put',
        'delete',
        'head'
    ]

    # Max request size (in Bytes) above which the backend will throw
    # Customizable with constructor's **kwargs argument: 'MAX_REQUEST_SIZE'
    DEFAULT_MAX_REQUEST_SIZE = 2900

    def __init__(self, host, auth=(), use_cache=True,
                 paginate=True, **kwargs):
        self.agent = Agent(host)
        if auth:
            self.username, self.password = auth
        try:
            self.token = self.get_token()['token']
        except:
            self.token = None
        self.paginate = paginate
        self.use_cache = use_cache
        self.MAX_REQUEST_SIZE = kwargs.get('MAX_REQUEST_SIZE', self.DEFAULT_MAX_REQUEST_SIZE)
        self.LOGIN_DISABLED = kwargs.get('LOGIN_DISABLED', False)
        if self.LOGIN_DISABLED:
            log.warning(textwrap.dedent("""\
                This client is running with `LOGIN_DISABLED` set to True,
                meaning that you'll login with (fake_user, fake_user).
                The API at {base_url} should be running in a config having LOGIN_DISABLED
                enabled, meaning either in DevelopmentConfig / TestingConfig mode.
                """.format(base_url=self.agent.base_url)))

    def get_token():
        raise NotImplementedError()

    #---------#
    # General #
    #---------#
    @logit
    def get(self, relative_url, use_token=True, auth=()):
        """Sends a GET request to the relative URL passed as argument.

        Args:
            relative_url (str): The relative URL to query.
            use_token (bool, optional): True if token authentication, False if
                username / password authentication.

        Returns:
            dict: The API JSON response

        Example:
            > auth = ('username', 'password')
            > c = Client(auth=auth)
            > c.get('/action/1')
        """
        return self._request('get', relative_url, use_token=use_token, auth=auth)

    @logit
    def get_with_params(self, relative_url, **kwargs):
        """Sends a GET request to the relative URL passed as argument that
        support URL parameters.

        URL parameters are parsed from kwargs to '&key=val' in the URL query
        string.

        Lists are converted to ,-separated args like '&key=val1,val1'

        This function is public and can be used as a stand-alone but will mostly
        be used by other functions like `get_actions` and `get_batches`.
        It provides a common interface for any parameterized query.

        Example:
            > auth = ('username', 'password')
            > c = Client(auth=auth)
            > kwargs = {
                'id': [1, 2, 3],
                'other_attribute': True
            }
            > c.get_with_args('/batches', **kwargs)
            [{}, {}, ...]

        Note:
            If 'id' parameter the `_construct_query_urls` function will take
            care of splitting the ,-separated list of ids in multiple chunks
            when it's too big.

        Args:
            relative_url (str): The relative URL to query.
            kwargs: A dictionary of parameters to parse and add to the query URL.
        """
        data = []
        urls = self._construct_query_urls(relative_url, **kwargs)
        i = 0
        for u in urls:
            i += 1
            part_data = self.get(u)
            data.extend(part_data)
        return data

    @logit
    def post(self, relative_url, json={}, use_token=True, auth=()):
        """Sends a POST request to the relative URL passed as argument.

        Args:
            relative_url (str): The relative URL to query.
            json (dict): The JSON data to POST.
            use_token (bool, optional): True if token authentication, False if
                username / password authentication.
            auth (tuple): Override client auth.

        Returns:
            dict: A dictionary containing the JSON response.

        Example:
            > c = Client(host, port, auth=('username', 'password'))
            > json_data = json.load('some_file.json')
            > c.post('/weblogic', json=json_data)
        """
        return self._request('post', relative_url, json=json, use_token=use_token,
                             auth=auth)

    @logit
    def put(self, relative_url, json={}, use_token=True, auth=()):
        """Send PUT request to the relative URL passed as argument.

        Args:
            relative_url (str): The relative URL to query.
            json (dict): The JSON data to PUT.
            auth (tuple, optional): Override client auth.

        Returns:
            dict: A dictionary containing the JSON response.

        Example:
            > c = Client(host, port, auth=('username', 'password'))
            > json_data = json.load('some_file.json')
            > c.update('/action/1', json=json_data)
        """
        return self._request('put', relative_url, json=json, use_token=True,
                             auth=auth)

    @logit
    def delete(self, relative_url, json={}, use_token=True, auth=()):
        """Send DELETE request to the relative URL passed as argument.

        Args:
            relative_url (str): The relative URL to query.
            json (dict): The JSON data to PUT.
            auth (tuple, optional): Override client auth.

        Returns:
            dict: A dictionary containing the JSON response.

        Example:
            > c = Client(host, port, auth=('username', 'password'))
            > c.delete('/action/1')
        """
        return self._request('delete', relative_url, json=json, use_token=True,
                             auth=auth)

    @logit
    def head(self, relative_url, use_token=True, auth=(), **filters):
        url = self._construct_query_urls(relative_url, **filters)[0]
        return self._request('head', url, json=json, use_token=True,
                             auth=auth)

    #---------#
    # PRIVATE #
    #---------#
    def _request(self, method, relative_url, json={}, use_token=True, auth=()):
        """Low level function to send any request through self.agent.
        Supports HTTP methods that are in SUPPORTED_HTTP_METHODS class attribute.
        Checks for authentication before sending request, and reloads the user
        token if it's expired and use_token is set to True.

        Args:
            method (str): The HTTP method to use.
            relative_url (str): The URL relative to the base API URL (e.g: /weblogic)
            json (dict, optional): The JSON data to pass in the request body.
            use_token (bool, optional): True if token authentication, False if
                username / password authentication.
            auth (tuple, optional): Override client auth.
        """
        # Check method
        if method not in self.SUPPORTED_HTTP_METHODS:
            raise APIRequestException(400, "Method %s is not supported." % method)

        # Authentify with / without token
        if use_token:
            if self.token is not None:
                auth = (self.token, '')
        else:
            if self.username is not None and self.password is not None:
                auth = (self.username, self.password)

        # Request data with agent
        r = self.agent.request(method, relative_url, auth=auth, json=json)

        # Handle empty responses
        if r is None:
            raise APIRequestException(500, "Internal server error", "No response returned from %s" % relative_url)

        # If token expired, refresh token and try again
        if use_token and r.status_code == 401:
            self.token = self.get_token()['token']
            auth = (self.token, '')
            r = self.agent.request(method, relative_url, auth=auth, json=json)

        # Raise exception if response has non-success HTTP code
        if r.status_code != 200:
            description = self.process_error_response(r)
            raise APIRequestException(r.status_code, r.reason, description)

        if method == 'head':
            return yaml.safe_load(r.headers['data'])

        log.info("RESPONSE: %s" % r.json())
        return r.json()

    def process_error_response(self, r):
        try:
            data = r.json()['description']
        except (ValueError, KeyError):
            try:  # Try to load JSON still
                data = json.load(data)['description']
            except:
                data = r.content
                log.warning("API didn't return JSON")
                pass
        if isinstance(data, basestring):
            data = data.replace('\\', '')
        return data

    def _build_put_data(self, ids, **kwargs):
        if not ids:
            return None
        if not isinstance(ids, list):
            ids = [ids]
        data = []
        for id in ids:
            action_data = {k: v for k, v in kwargs.items()}
            action_data['id'] = id
            data.append(action_data)
        return data

    def _construct_query_urls(self, base, **kwargs):
        query_urls = []
        query_url = base + '?'
        for k, v in kwargs.items():
            if isinstance(v, list):
                v = map(str, v)
                v = ','.join(v)
            if k == 'id':
                continue
            query_url += '&{key}={val}'.format(key=k, val=v)

        # Handle 'id' parameter which can be longer than other parameter
        # To avoid having a query limit we split the query in multiple queries
        # when the number of 'id' passed is too long.
        id = kwargs.get('id')
        if id:
            if not isinstance(id, list):  # single id case
                id = [id]
            for chunk in self._split_ids(id):
                query_url += '&id=' + ','.join([str(i) for i in chunk])
                query_urls.append(query_url)
            return query_urls

        return [query_url]

    def _split_ids(self, ids):
        MAX_ARGS_SIZE = self.MAX_REQUEST_SIZE - len(self.agent.base_url + '?ids=')
        if len(ids) > MAX_ARGS_SIZE:  # List too big, chunkify
            n = len(ids) / MAX_ARGS_SIZE + 1
            return _chunkify(ids, n)
        return [ids]

def _chunkify(lst, n):
    """Split a list in n chunks.

    Args:
        lst (list): The input list.
        n (int): The number of chunks.

    Returns:
        list: A list of n lists corresponding to chunks of the input list.

    Example:
        > l = [1, 2, 3, 4, 5, 6]
        > chunkify(l, 3)
        [[1, 2], [3, 4], [5, 6]]
    """
    return np.array_split(np.array(lst), n)


class Endpoint(object):
    """API endpoint. Provides base utility functions (get, put, post) and can be
    derived from to implement custom endpoint functionalities.

    Args:
        client: An instance of API client to use to carry requests out.
    """
    def __init__(self, client):
        self.client = client


class CRUDEndpoint(Endpoint):
    """CRUD endpoint supporting CRUD convention.

    The CRUDEndpoint implements the following methods:
        * count: Sends a HEAD request to the endpoints.
        * create: Sends a POST request to the endpoints.
        * get: Sends a GET request to the endpoints.
        * update: Sends a PUT request to the endpoints.
        * delete: Sends a DELETE request to the endpoints.

    Args:
        client: An instance of API client to use to carry requests out.
        single: The 'single' endpoint (e.g: /action).
        multiple: The 'multiple' endpoints (e.g: /actions).

    Example:
        Instanciating a client:

        >>> host = 'localhost'
        >>> client = Client(host, auth=('username', 'password'))

        or, if the API has a port:

        >>> host = 'localhost:8080'
        >>> client = Client(host, auth=('username', 'password'))

        Instanciating a CRUD endpoint:

        >>> c = CRUDEndpoint(client, '/user', '/users')
        >>> c.get(5)
        >>> c.count()
        >>> c.create(first_name='Oliver', last_name='Unkown')
        >>> c.update(id=[1, 5], first_name='Olivier')

        A more advanced example for filtering on models using match and cache
        option and no pagination.

        >>> c.get(paginate=False,
                  use_cache=True,
                  match=[
                    ['field_1', '<=', 5],
                    ['field_2', '!=' 2],
                    ['field_3', 'startswith', 'the quick brown fox jumps'],
                    ['field_4', 'endswith', 'over the lazy dog'],
                    ['field_5', 'in', [1, 100]], # choices
                    ['field_6', 'between', [1, 100]] # range
                  ])


    Raises:
        TypeError: If a parameter passed to either create, get, update or delete
            is of the wrong type.
        APIRequestException: If the response HTTP status code of an object is
            not a valid status code.
    """
    def __init__(self, client, single, multiple):
        super(CRUDEndpoint, self).__init__(client)
        self.single = single
        self.multiple = multiple

    @property
    def url(self):
        return self.multiple

    def create(self, json=None, **params):
        """Create a new resource by sending POST request with `params` as JSON
        in the body.

        Examples of resource creation:
        >>> params = {'id': 4, 'action': 'status'}
        >>> c.create(**params)
        >>> param = {
        ...   'any': 4,
        ...   'of': '',
        ...   'the': True,
        ...   'required': True,
        ...   'fields': [] }
        >>> c.create(**params)
        """
        if json is not None: params = json
        return self.client.post('{0}'.format(self.multiple), json=params)

    def create_multiple(self, defs):
        return self.client.post('{0}'.format(self.multiple), json=defs)

    def get(self, id=None, paginate=None, page=None, per_page=None,
            order_by=None, sort=None, match=None, use_cache=None, **filters):
        """Sends GET request with either id or **filters url-encoded.
        Allows filtering of query by url-encoding parameters.

        This mean you can do:
            >>> c.get(id=[1, 5, 100], p1=['SCHEDULED', 'RUNNING'], p2=True)

        The previous parameters will be be url-encoded like:
            `<host>/api/myendpoint?id=1,5,100&p1=SCHEDULED,RUNNING&p2=True`

        Args:
            filters: A dictionary of parameters to filter the GET query on.

        Raises:
            :obj:`APIRequestException`: If one of **filters not present in the
                database model was used (400), if one of **filters is
                read-forbidden, or if the `id` passed doesn't point an existing
                resource.

        Returns:
            list|dict: A list of dict (if  **filters is not empty) or a single
                dict (if only one `id` was passed).
        """

        # Convert id if necessary
        id = id or filters.get('id')
        if isinstance(id, int):
            return self.client.get('{0}/{1}'.format(self.single, id))
        filters['id'] = id

        # Handle pagination
        if paginate is not None:  filters['paginate'] = paginate
        else:                     filters['paginate'] = self.client.paginate
        if per_page is not None:  filters['per_page'] = per_page
        if page is not None:      filters['page'] = page

        # Handle ordering / sorting
        if order_by is not None:  filters['order_by'] = order_by
        if sort is not None:      filters['sort'] = sort

        # Handle filter matches (dirty fix)
        if match is not None:     filters['match'] = [match]

        # Handle cache
        if use_cache is not None: filters['cache'] = use_cache
        else:                     filters['cache'] = self.client.use_cache

        return self.client.get_with_params('{0}'.format(self.multiple), **filters)

    def update(self, ids, **params):
        """Sends GET request with either 'id' or **params url-encoded.
        Allows filtering of query by url-encoding parameters.

        This mean you can do:
            >>> c.update([1, 5, 100], status='RUNNING')

        The previous parameters will send the PUT request as a JSON like:
            [
                {
                    'id': 1,
                    'status': 'RUNNING'
                },
                {
                    'id': 5,
                    'status': 'RUNNING'
                },
                {
                    'id': 100,
                    'status': 'RUNNING'
                }
            ]

        Args:
            ids (int|list): A single `int` or a list of `int` identifying the
                action(s) to update.
            params: A dictionary of parameters to update.

        Raises:
            :obj:`APIRequestException`: If one of **params not present in the
                database model was used (400), or if one of the resources
                identified by `ids` does not exist (404), or if a parameter was
                write-forbidden (403).

        Returns:
            list|dict: A list of dict (if  **params is not empty) or a single
                dict (if only one `id` was passed).
        """
        if isinstance(ids, list):
            json = self.client._build_put_data(ids, **params)
            return self.client.put('{0}'.format(self.multiple), json=json)
        elif isinstance(ids, int):
            return self.client.put('{0}/{1}'.format(self.single, ids), json=params)
        else:
            raise TypeError("`update` first argument `ids` must be a list or an int")

    def update_multiple(self, defs):
        return self.client.put('{0}'.format(self.multiple), json=defs)

    def count(self, match=None, use_cache=None, **filters):
        """Return the number of objects in the CRUD table asssociated with this
        endpoint.
        """
        # Handle filter matches (dirty fix)
        # TODO: Remove the following 2 lines
        if match is not None: filters['match'] = [match]

        # Handle cache
        filters['cache'] = use_cache or self.client.use_cache
        return self.client.head('{0}'.format(self.multiple), **filters).get('count', None)

    def get_resource_url(self, ids):
        """Return a list of links for the resources identified by `ids`.

        Args:
            ids (list): A list of resource ids to get the URL of.

        Returns:
            str|list: A single URL (if `id` is an int) or a list of URLs (if
                `ids` is a list of ids) corresponding to the resources
                identified by `ids`.

        Example:
            >>> c.endpoint.get_resource_url([1,2,4])
            ['http://localhost/api/endpoint/path/to/1',
             'http://localhost/api/endpoint/path/to/2',
             'http://localhost/api/endpoint/path/to/3',
             'http://localhost/api/endpoint/path/to/4']

        Raises:
            :obj:`APIRequestException`: Raised if one of the resources identified
                by `ids` does not exist, or the database model doesn't implement
                the `_links` field.
        """
        if isinstance(ids, list):
            return [o['_links']['self'] for o in self.get(id=ids)]
        else:
            return self.get(ids)['_links']['self']

    def delete(self, ids=None, **filters):
        if ids is None and filters:
            ids = [a['id'] for a in self.get(**filters)]
        if isinstance(ids, list):
            deletes = []
            for id in ids:
                r = self.client.delete('{0}/{1}'.format(self.single, id))
                deletes.append(r)
            return deletes
        elif isinstance(ids, int):
            return self.client.delete('{0}/{1}'.format(self.single, ids))
        else:
            raise TypeError("`delete` first argument `ids` must be a list or an int")
