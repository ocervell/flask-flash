"""
utils.py
~
Maintainer: Olivier Cervello.
Description: Utility functions used by Flask-Flash.
"""
from datetime import datetime
import logging
from flask import request
import urllib
from extensions import cache

log = logging.getLogger(__name__)

TIME_FORMATS = {
    'naive': "%Y-%m-%d %H:%M:%S",
    'with_timezone': "%Y-%m-%d %H:%M:%S %Z%z"
}

def print_datetime(dt, fmt=TIME_FORMATS['with_timezone']):
    """Print a datetime object with any format. See TIME_FORMATS for available
    formats.

    Args:
        dt (datetime.datetime): A datetime object (timezone aware or not)

    Returns:
        str: The datetime object representation as a string.
    """
    return dt.strftime(fmt)

def isbool(v):
    return v == 'True' or v == 'False'

def str2bool(v):
    return v == 'True'

def reprd(d):
    if not d:
        return []
    if isinstance(d, list):
        return [reprd(e) for e in d]
    data = {k: v for k, v in d.items()}
    for k, v in data.items():
        if k == 'id':
            continue
        if isinstance(v, unicode) and len(v) > 20:
            data[k] = v[:10] + '...' + v[-10:]
        if isinstance(v, datetime):
            data[k] = print_datetime(v)
    try:
        return convert(data)
    except UnicodeEncodeError:
        return data

def abort_400_if_not_belong(name, elem, group):
    """Raise APIException (404) if `elem` does not belong to `group`."""
    if not elem:
        raise APIException(400, "{} needs to be in input data".format(name.title()))
    if elem not in group:
        raise APIException(400, "{0} {1} is invalid. List of valid {2}s: {3}".format(name.title(), elem, name, group))

def convert(data):
    """Convert all unicode strings to strings in any iterable, mapping or
    basestring."""
    import collections
    if isinstance(data, basestring):
        return str(data)
    elif isinstance(data, collections.Mapping):
        return dict(map(convert, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(convert, data))
    else:
        return data

def transform_html(data, headers=None):
    """Transform a string to an HTML-formatted string
    and return a Flask response.

    Args:
        data (str): A string to transform.
        headers (str, optional): The headers of the response.

    Return:
        A Flask response object.
    """
    data_html = "<br>".join(escape(data).split("\n"))
    resp = current_app.make_response(data_html)
    resp.headers.extend(headers or {})
    return resp

def get_required_args(func):
    args, varargs, varkw, defaults = inspect.getargspec(func)
    if defaults:
        args = args[:-len(defaults)]
    return args

from operator import itemgetter
def format_as_table(data,
                    keys,
                    header=None,
                    sort_by_key=None,
                    sort_order_reverse=False):
    """Takes a list of dictionaries, formats the data, and returns
    the formatted data as a text table.

    Required Parameters:
        data - Data to process (list of dictionaries). (Type: List)
        keys - List of keys in the dictionary. (Type: List)

    Optional Parameters:
        header - The table header. (Type: List)
        sort_by_key - The key to sort by. (Type: String)
        sort_order_reverse - Default sort order is ascending, if
            True sort order will change to descending. (Type: Boolean)
    """
    if isinstance(data, dict):
        data = [data]

    # Sort the data if a sort key is specified (default sort order
    # is ascending)
    if sort_by_key:
        data = sorted(data,
                      key=itemgetter(sort_by_key),
                      reverse=sort_order_reverse)

    # If header is not empty, add header to data
    if header:
        # Get the length of each header and create a divider based
        # on that length
        header_divider = []
        for name in header:
            header_divider.append('-' * len(name))

        # Create a list of dictionary from the keys and the header and
        # insert it at the beginning of the list. Do the same for the
        # divider and insert below the header.
        header_divider = dict(zip(keys, header_divider))
        data.insert(0, header_divider)
        header = dict(zip(keys, header))
        data.insert(0, header)

    column_widths = []
    for key in keys:
        column_widths.append(max(len(str(column[key])) for column in data))

    # Create a tuple pair of key and the associated column width for it
    key_width_pair = zip(keys, column_widths)

    format = ('%-*s ' * len(keys)).strip() + '\n'
    formatted_data = ''
    for element in data:
        data_to_format = []
        # Create a tuple that will be used for the formatting in
        # width, value format
        for pair in key_width_pair:
            data_to_format.append(pair[1])
            data_to_format.append(element[pair[0]])
        formatted_data += format % tuple(data_to_format)
    return formatted_data

def print_endpoint(endpoint, default_keys=[], **user_filters):
    keys = user_filters.get('only') or default_keys
    filters = {
        'paginate': True,
        'only': keys
    }
    filters.update(user_filters)
    print("Query:\n  Endpoint '%s'\n  Filters: %s\n" % (endpoint.url, filters))
    data = endpoint.get(**filters)
    if not data:
        print "No data found !"
        return
    if isinstance(data, list):
        keys = [k for k in data[0].keys() if k in keys]
    else:
        keys = [k for k in data.keys() if k in keys]
    headers = [c.capitalize() for c in keys]
    print format_as_table(data, keys, headers)
