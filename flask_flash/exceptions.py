"""
exceptions.py
~
Maintainer: Olivier Cervello.
Description: Flask-Flash API HTTP exceptions.
"""
import json

class APIException(Exception):
    """Flask-Flash API Exception Base class.
    All API exceptions should derive from this class.
    """
    def __init__(self, code, message):
        self._code = code
        self._message = message
        super(APIException, self).__init__(code, message)

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


class ResourceNotFound(APIException):
    """Custom exception when resource is not found."""
    def __init__(self, model_name, id):
        message = 'Resource {} {} not found.'.format(model_name.title(), id)
        super(ResourceNotFound, self).__init__(404, message)


class ResourceFieldForbidden(APIException):
    """Custom exception when trying to modify a field that is forbidden."""
    def __init__(self, model_name, field):
        message = 'Not allowed to filter on (or modify) {}.{}.'.format(model_name.title(), field)
        super(ResourceFieldForbidden, self).__init__(403, message)


class ResourceFieldMissing(APIException):
    """Custom exception when a field is missing in request."""
    def __init__(self, model_name, field, request):
        message = 'Field %s missing in %s request.'.format(model_name.title(), field, request)
        super(ResourceFieldMissing, self).__init__(403, message)


class FilterInvalid(APIException):
    def __init__(self, model_name, param):
        message = 'Invalid filter for model {}: {}.'.format(model_name.title(), param)
        super(FilterInvalid, self).__init__(400, message)


class FilterNotSupported(APIException):
    def __init__(self, model_name, param):
        message = 'Filter not supported for model {}: {}.'.format(model_name, param)
        super(FilterNotSupported, self).__init__(400, message)
