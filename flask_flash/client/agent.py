import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import pprint
import logging
from urlparse import urlparse
import re
import time
pp = pprint.PrettyPrinter(indent=4)
log = logging.getLogger(__name__)

class Agent(object):
    """Wrapper class to send HTTP queries to an API at http://host:port/api.

    Args:
        host (str): The host to use. Can be in the form http://a.b.c.com or
            a.b.c.com
        port (int, optional): The port to use. Default to 80.
    """
    def __init__(self, url, **params):
        self.host, self.port = Agent.get_host_port(url)
        api_suffix = params.get('api_suffix', 'api').lstrip('/')
        self.base_url = 'http://{}:{}/{}'.format(self.host, self.port, api_suffix)
        retries = Retry(
            total=5,
            read=5,
            connect=5,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 505],
            raise_on_status=False)
        self.session = requests.Session()
        self.session.mount(self.base_url, HTTPAdapter(max_retries=retries))

    def request(self, method, url, auth=(), json={}, absolute=False, log_401=True):
        """Wrapper around `requests` lib methods."""
        success = 'FAILURE'
        r = None
        now = time.time()
        if not absolute:
            rel_url = url
            url = self.build_url(url)
        else:
            rel_url = self._construct_relative_url(url)
        if url:
            self.before_request(method, url)
            requests_method = getattr(self.session, method)
            try:
                if method == 'get' or method == 'head':
                    r = requests_method(url, auth=auth)
                else:
                    r = requests_method(url, auth=auth, json=json)
                success = 'SUCCESS'
                self.after_request(r, method, log_401)
            except Exception as e:
                if 'BadStatusLine' in str(e):
                    pass
                else:
                    log.exception(e)
                success = 'FAILURE'
            finally:
                message = "%s | %s | %s | %s s" % (method.upper(), rel_url, success, (time.time() - now))
                if success:
                    log.debug(message)
                else:
                    log.error(message)
        return r

    def before_request(self, method, url):
        log.debug("{method} | {url} | REQUEST".format(method=method.upper(), url=url))

    def after_request(self, r, method, log_401=True):
        if r.status_code != 200:
            if r.status_code == 401 and not log_401: return
            log.error("{method} | {r.url} | RESPONSE | HTTP Status: {r.status_code} ({r.reason})".format(r=r, method=method))
            return
        content_type = r.headers.get('Content-Type', '')
        if content_type == 'application/json':
            log.debug("{method} | {r.url} | RESPONSE | API returned a valid JSON response".format(r=r, method=method))
        else:
            log.warning("{method} | {r.url} | RESPONSE | API did not return JSON response | Content-Type: {ctype}"
                        .format(ctype=content_type, r=r, method=method))

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
