"""
client.py
~
Maintainer: Olivier Cervello.
Description: Flask-Flash API base client and endpoints.
"""
from .agent import Agent
import logging, json, yaml, textwrap, pprint
import numpy as np
from cgi import escape
import requests
from requests.exceptions import RequestException

log = logging.getLogger(__name__)

class BaseClient(object):
    """Low level client that implements basic HTTP functions.

    Args:
        host (str, optional): The API hostname. Default: 'localhost'
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
    # Defaults to NGINX default max request size.
    DEFAULT_MAX_REQUEST_SIZE = 2900

    def __init__(self, host, auth=(), use_cache=True, paginate=True, **kwargs):
        self.agent = Agent(host, **kwargs)
        if auth:
            self.username, self.password = auth
        try:
            self.token = self.get_token()['token']
        except Exception as e:
            self.token = None
        self.paginate = paginate
        self.use_cache = use_cache
        self.MAX_REQUEST_SIZE = kwargs.get('MAX_REQUEST_SIZE', self.DEFAULT_MAX_REQUEST_SIZE)
        self.LOGIN_DISABLED = kwargs.get('LOGIN_DISABLED', False)
        if self.LOGIN_DISABLED:
            log.warning(textwrap.dedent("""\
                This client is running with `LOGIN_DISABLED` set to True,
                meaning that you'll login with any user / password.
                This assumes your API is running with 'LOGIN_DISABLED' set to
                True in the config (BaseConfig object).

                The config for the Flask-Flash API at {base_url} should have
                it's attribute 'LOGIN_DISABLED' set to True, otherwise this
                option won't work.
                """.format(base_url=self.agent.base_url)))

    def get_token(self):
        raise NotImplementedError()

    def register(self, name, cls, routes):
        """Register an endpoint with this client."""
        self.__dict__[name] = cls(self, routes[0], routes[1])

    #---------#
    # General #
    #---------#
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

    def delete_with_params(self, relative_url, **kwargs):
        data = {}
        urls = self._construct_query_urls(relative_url, **kwargs)
        i = 0
        for u in urls:
            i += 1
            part_data = self.delete(u)
            data.update(part_data)
        return data

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

    def put(self, relative_url, json={}, use_token=True, auth=(), **filters):
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
        url = self._construct_query_urls(relative_url, **filters)[0]
        return self._request('put', url, json=json, use_token=True, auth=auth)

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

    def head(self, relative_url, use_token=True, auth=(), **filters):
        url = self._construct_query_urls(relative_url, **filters)[0]
        return self._request('head', url, json=json, use_token=True, auth=auth)

    #---------#
    # PRIVATE #
    #---------#
    def _request(self, method, url, json={}, use_token=True, auth=(), retry_401=True):
        """Low level function to send any request through self.agent.
        Supports HTTP methods that are in SUPPORTED_HTTP_METHODS class attribute.
        Checks for authentication before sending request, and reloads the user
        token if it's expired and use_token is set to True.

        Args:
            method (str): The HTTP method to use.
            url (str): The URL relative to the base API URL (e.g: /weblogic)
            json (dict, optional): The JSON data to pass in the request body.
            use_token (bool, optional): True if token authentication, False if
                username / password authentication.
            auth (tuple, optional): Override client auth.
        """
        # Check method
        if method not in self.SUPPORTED_HTTP_METHODS:
            raise ValueError("Method '%s' is not supported by this client." % method)

        # Authentify with / without token
        if not auth: # no auth passed, build it
            if use_token:
                if self.token is not None:
                    auth = (self.token, '')
            elif self.username is not None and self.password is not None:
                auth = (self.username, self.password)

        # Request data using agent.
        # Retry on 401 to refresh the auth token.
        try:
            r = self.agent.request(method, url, auth=auth, json=json)
        except requests.exceptions.RequestException as e:
            r = e.response
            if (r is not None \
                    and r.status_code == 401 \
                    and retry_401 \
                    and use_token \
                    and self.token is not None):
                return self.retry_401(r, method, url, auth=auth, json=json)
            else:
                raise

        # Validate JSON headers
        headers = r.headers
        if headers.get('Content-Type') != 'application/json':
            log.info("API did not return JSON content. Data: %s" % r.content)
            raise Exception("API did not return JSON content")

        # Return JSON data
        if method == 'head':
            return yaml.safe_load(headers['data'])
        else:
            return r.json()

    def retry_401(self, r, method, url, auth=(), json={}):
        self.token = self.get_token()['token']
        auth = (self.token, '')
        return self._request(method, url, auth=auth, json=json, retry_401=False)

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
            if isinstance(k, basestring):
                k = str(k)
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
    def __init__(self, client, url=None, parent=None):
        self.client = client
        if parent is not None:
            self.parent = parent
        if url is not None:
            self.url = url
            self.get = self._get
            self.post = self._post
            self._put = self._put
            self._delete = self._delete

    def _get(self, *args, **kwargs):
        return self.client.get(self.url, *args, **kwargs)

    def _post(self, *args, **kwargs):
        return self.client.post(self.url, *args, **kwargs)

    def _put(self, *args, **kwargs):
        return self.client.put(self.url, *args, **kwargs)

    def _delete(self, *args, **kwargs):
        return self.client.put(self.url, *args, **kwargs)

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
        `TypeError`: If a parameter passed to either create, get, update or delete
            is of the wrong type.
        `requests.exceptions.RequestException`: If the underlying request fails.
    """
    def __init__(self, client, single, multiple, parent=None):
        super(CRUDEndpoint, self).__init__(client, parent=parent)
        self.single = single
        self.multiple = multiple

    @property
    def url(self):
        return self.multiple

    def create(self, json=None, **params):
        """Create a new resource by sending POST request with `kwargs` as JSON
        in the body.

        Assuming you have a model in your API with the following fields:
        - action (String)
        - name (String)
        - args (JSON)
        Direct resource creation (using **params)
        >>> c.create(action='status', name='My Action', )
        {
            'id': 1,
            'action': 'status',
            'name': 'My Action',
            'args': {'extra': 1, 'parameter': 2}
        }

        >>> param = {
        ...   'any': 4,
        ...   'of': '',
        ...   'the': True,
        ...   'model': True,
        ...   'field': []
        ... }
        >>> c.create(**kwargs)
        """
        json = json or params
        return self.client.post('{0}'.format(self.multiple), json=json)

    def get(self, id=None, paginate=None, page=None, per_page=None,
            order_by=None, sort=None, match=None, use_cache=None, **params):
        """Sends GET request with either id or **params url-encoded.
        Allows filtering of query by url-encoding parameters.

        This mean you can do:
            >>> c.get(id=[1, 5, 100], p1=['SCHEDULED', 'RUNNING'], p2=True)

        The previous parameters will be be url-encoded like:
            `<host>/api/myendpoint?id=1,5,100&p1=SCHEDULED,RUNNING&p2=True`

        Args:
            params: A dictionary of parameters to filter the GET query on.

        Raises:
            `requests.exceptions.RequestException`: If one of **params not
                present in the database model was used (400), if one of **params
                is read-forbidden, or if the `id` passed doesn't point an existing
                resource.

        Returns:
            list|dict: A list of dict (if  **params is not empty) or a single
                dict (if only one `id` was passed).
        """

        # Convert id if necessary
        id = id or params.get('id')
        if isinstance(id, int) or isinstance(id, basestring):
            return self.client.get('{0}/{1}'.format(self.single, id))
        params['id'] = id

        # Handle pagination
        if paginate is not None:  params['paginate'] = paginate
        else:                     params['paginate'] = self.client.paginate
        if per_page is not None:  params['per_page'] = per_page
        if page is not None:      params['page'] = page

        # Handle ordering / sorting
        if order_by is not None:  params['order_by'] = order_by
        if sort is not None:      params['sort'] = sort

        # Handle filter matches (dirty fix)
        if match is not None:     params['match'] = [match]

        # Handle cache
        params['cache'] = use_cache or self.client.use_cache

        return self.client.get_with_params('{0}'.format(self.multiple), **params)

    def get_or_create(self, eq=[], **kwargs):
        if eq:
            filters = { k:v for k,v in kwargs.items() if k in eq }
            obj = self.get(**filters)
            if obj:
                return obj[0]
        return self.create(**kwargs)

    def update(self, id=None, **params):
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
            id (int|list): A single `int` or a list of `int` identifying the
                action(s) to update.
            params: A dictionary of parameters to update.

        Raises:
            `requests.exceptions.RequestException`: If one of **params not
                present in the database model was used (400), or if one of the
                resources identified by `id` does not exist (404), or if a
                parameter was write-forbidden (403).

        Returns:
            list|dict: A list of dict (if  **params is not empty) or a single
                dict (if only one `id` was passed).
        """
        filters = {}
        _action = params.get('_action', None)
        if _action is not None: filters['_action'] = _action
        if isinstance(id, list):
            json = self.client._build_put_data(id, **params)
            return self.client.put('{0}'.format(self.multiple), json=json, **filters)
        elif isinstance(id, int) or isinstance(id, basestring):
            return self.client.put('{0}/{1}'.format(self.single, id), json=params, **filters)
        else:
            raise TypeError("`update` first argument `id` must be a list or an int")

    def update_multiple(self, json):
        return self.client.put('{0}'.format(self.multiple), json=json)

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
            `requests.exceptions.RequestException`: Raised if one of the
                resources identified by `ids` does not exist, or the database
                model doesn't implement the `_links` field.
        """
        if isinstance(ids, list):
            return [o['_links']['self'] for o in self.get(id=ids)]
        else:
            return self.get(ids)['_links']['self']

    def delete(self, ids=None, match=None, **filters):
        """Delete objects identified either by `ids` or by a list of filters.
        """
        if ids is None:
            log.info("No ids: Using filters: %s" % filters)
            return self.client.delete_with_params('{0}'.format(self.multiple), **filters)

        elif isinstance(ids, list):
            filters['id'] = ','.join(map(str, ids))
            if match is not None:
                filters['match'] = [match]
            return self.client.delete_with_params('{0}'.format(self.multiple), **filters)

        elif isinstance(ids, int) or isinstance(ids, basestring):
            return self.client.delete('{0}/{1}'.format(self.single, ids))

        else:
            raise TypeError("`delete` first argument `ids` must be a list or an int")
