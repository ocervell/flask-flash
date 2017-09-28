"""
agent.py
~
Maintainer: Olivier Cervello.
Description: Low-level agent for Flask-Flash client. Implements retries.
"""
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import pprint
import logging
from urlparse import urlparse
import re
import time
import sys
pp = pprint.PrettyPrinter(indent=4)
log = logging.getLogger(__name__)

RETRY_CONFIG = {
    'total': 3,
    'read': 3,
    'connect': 3,
    'backoff_factor': 0.1,
    'status_forcelist': [500, 502, 503, 505]
}

class Agent(object):
    """Wrapper class to send HTTP queries to an API at:
        http://<host>:<port>/<api_suffix>.

    Args:
        url (str): The url to use.
        params (dict):
            api_suffix (str, optional): The suffix for the API. Default: /api
            retry_disabled (bool, optional): Disable retries. Default: False
            retry_config (dict, optional): The config for `HTTPAdapter.max_retries`.
                Config is disabled if `retry_disabled` set to True.
            timeout_config (dict, optional): The config for timeouts.
    """
    def __init__(self, url, **params):
        # Initialize requests Session
        api_suffix = params.get('api_suffix', 'api').lstrip('/')
        self.host, self.port = Agent.get_host_port(url)
        self.base_url = 'http://{}:{}/{}'.format(self.host, self.port, api_suffix)
        self.session = requests.Session()

        # Get retry config
        if params.get('retry_disabled', False):
            self.session.mount(self.base_url, HTTPAdapter())
        else:
            config = RETRY_CONFIG.copy()
            user_config = params.get('retry_config', {})
            config.update(user_config)
            retries = Retry(**config)
            self.session.mount(self.base_url, HTTPAdapter(max_retries=retries))

    def request(self, method, url, auth=(), json={}, absolute=False, log_401=True):
        """Wrapper around `requests` lib methods."""
        r = None
        url, rel_url = self.get_url(url, absolute=absolute)
        req = getattr(self.session, method)
        params = {'auth': auth}
        if method in ['post', 'put', 'delete']:
            params['json'] = json
        r = req(url, **params)
        try:
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise type(e), type(e)(e.message + ' | Additional data: ' + r.content, response=r), sys.exc_info()[2]
        return r

    def get_url(self, url, absolute=False):
        if not absolute:
            rel = url
            full = self.build_url(url)
        else:
            rel = self._construct_relative_url(url)
            full = url
        return full, rel

    def build_url(self, relative_url):
        if not relative_url.startswith('/'):
            relative_url = '/' + relative_url
        url = self.base_url + relative_url
        log.debug("Relative URL: %s | Full URL: %s" % (relative_url, url))
        return url

    def _construct_relative_url(self, full_url):
        """Get the relative URL corresponding to a full URL for this API."""
        return re.sub(r'(http://)?.*(\d+|.com|localhost)/api', '', full_url)

    @staticmethod
    def get_host_port(url):
        if not url.startswith('http://'): url = 'http://' + url
        parsed = urlparse(url)
        try:
            host = parsed.hostname
        except AttributeError:
            host = '127.0.0.1'
        try:
            port = parsed.port
            if port is None: port = 80
        except AttributeError:
            port = 80
        return host, port
