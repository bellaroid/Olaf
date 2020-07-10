import json
import os
import jinja2
import logging
from bson import ObjectId
from werkzeug.wrappers import Request as WZRequest, Response as WZResponse
from werkzeug.exceptions import BadRequest
from werkzeug.wrappers.json import JSONMixin
from werkzeug.routing import Map, Rule
from olaf import registry

logger = logging.getLogger(__name__)


class Request(JSONMixin, WZRequest):
    """ Standard Werkzeug Request with JSON Mixin """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Response(JSONMixin, WZResponse):
    """ Standard Werkzeug Response with JSON Mixin """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class JsonResponse(Response):
    """ This class is a shortcut for creating
    a JSON response object out of a dictionary.
    """

    def __init__(self, *args, **kwargs):
        if args[0] is not None:
            list_args = list(args)
            list_args[0] = json.dumps(args[0], default=OlafJSONEncoder)
        elif "response" in kwargs:
            kwargs["response"] = json.dumps(
                kwargs["response"], default=OlafJSONEncoder)
        kwargs["content_type"] = "application/json"
        super().__init__(*list_args, **kwargs)


class RouteMapMeta(type):
    """ Ensures a single instance of the RouteMap class """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                RouteMapMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class RouteMap(metaclass=RouteMapMeta):
    """ Stores the application URL map """

    def __init__(self):
        self.pre_map = dict()
        self.url_map = Map([])

    def __call__(self):
        return self.url_map

    def add(self, string, methods=None):
        """ Bind an URL pattern to a function """

        def _sanitize_methods(methods):
            """ Sort and capitalize methods """
            if methods is None:
                return []

            methods.sort(key=lambda x: x.upper())
            return [method.upper() for method in methods]

        def decorator(function):
            # Create a dict with the given parameters
            key = (string, frozenset(_sanitize_methods(methods)))
            # Verify if rule is already present
            self.pre_map[key] = Rule(string, methods=methods, endpoint=function)
            return function

        return decorator

    def build_url_map(self):
        """ Build url map out of collected rules """

        for rule in self.pre_map.values():
            self.url_map.add(rule)
        return self.url_map


# Instantiate RouteMap
route = RouteMap()


def render_template(relative_path, context):
    """ Renders a Jinja2 Template.
    NOTE: It is not the purpose of this framework to serve views.
    """
    abs_path = os.path.join(os.path.dirname(__file__), relative_path)
    with open(abs_path) as file_:
        template = jinja2.Template(file_.read())
    return Response(template.render(**context), mimetype='text/html')


def OlafJSONEncoder(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
