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
# s = requests.Session()
# retries = Retry(total=5,
#                 backoff_factor=0.1,
#                 status_forcelist=[ 500, 502, 503, 504 ])
# s.mount('http://', HTTPAdapter(max_retries=retries))

class Agent(object):
    """Wrapper class to send HTTP queries to an API at http://host:port/api.

    Args:
        host (str): The host to use. Can be in the form http://a.b.c.com or
            a.b.c.com
        port (int, optional): The port to use. Default to 80.
    """
    HTTP_STATUS_CODES = {
        '200': 'OK',
        '400': 'BAD_REQUEST',
        '401': 'UNAUTHORIZED',
        '403': 'FORBIDDEN',
        '404': 'NOT FOUND',
        '408': 'REQUEST TIMEOUT'
    }

    def __init__(self, url):
        self.host, self.port = Agent.get_host_port(url)
        self.base_url = 'http://{host}:{port}/api'.format(
                            host=self.host,
                            port=self.port)
        log.debug("API Agent initialized at %s" % (self.base_url))

    def request(self, method, url, auth=(), json={}, absolute=False):
        success = 'FAILURE'
        r = None
        now = time.time()
        if not absolute:
            rel_url = url
            url = self.build_url(url)
        else:
            rel_url = self._construct_relative_url(url)
        log.info("Hitting URL: %s" % url)
        if url:
            self.before_request(method, url)
            # requests_method = getattr(s, method)
            requests_method = getattr(requests, method)
            try:
                if method == 'get' or method == 'head':
                    r = requests_method(url, auth=auth)
                else:
                    r = requests_method(url, auth=auth, json=json)
                success = 'SUCCESS'
                self.after_request(r, method)
            except Exception as e:
                if 'BadStatusLine' in str(e):
                    pass
                else:
                    log.exception(e)
                success = 'FAILURE'
            finally:
                message = "%s | %s | %s | %s s" % (method.upper(), rel_url, success, (time.time() - now))
                if success:
                    log.info(message)
                else:
                    log.error(message)
        return r

    def before_request(self, method, url):
        log.debug("{method} | {url} | REQUEST".format(method=method.upper(), url=url))

    def after_request(self, r, method):
        if r.status_code != 200:
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
