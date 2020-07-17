import json
import os
import logging
from bson import ObjectId
from jinja2 import Environment as Jinja2Environment, FileSystemLoader
from werkzeug.wrappers import Request as WZRequest, Response as WZResponse
from werkzeug.exceptions import BadRequest
from werkzeug.wrappers.json import JSONMixin
from werkzeug.wrappers.cors import CORSResponseMixin
from werkzeug.routing import Map, Rule, NotFound
from olaf import registry
from olaf.tools import config


logger = logging.getLogger(__name__)


class Request(WZRequest, JSONMixin):
    """ Standard Werkzeug Request with JSON Mixin """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Response(WZResponse, JSONMixin, CORSResponseMixin):
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
    """
    Stores the application URL map.
    The add() method collects mappings of
    a URL string and its HTTP methods with a 
    certain function. In order to allow different
    modules to overwrite previously added rules,
    collected rules are not loaded until 
    build_url_map() method is called.
    """

    def __init__(self):
        self.pre_map = dict()
        self.url_map = None

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
            # Store (or overwrite) rule
            self.pre_map[key] = Rule(
                string, methods=methods, endpoint=function)
            return function

        return decorator

    def build_url_map(self):
        """
        Build url map out of collected rules.
        If the URL Map has been alredy initialized,
        then skip the procedure.
        """
        if not self.url_map:
            # Initialize URL Map only it if hasn't been yet.
            logger.info("Generating Route Map")
            self.url_map = Map([])
            for rule in self.pre_map.values():
                self.url_map.add(rule)
        return self.url_map


# Instantiate RouteMap
route = RouteMap()


def dispatch(env, start_response):
    """ 
    Main HTTP entrypoint
    """

    # Bind URL Map
    url_map = route.url_map
    urls = url_map.bind_to_environ(env)
    request = Request(env)  # pylint: disable=assigning-non-slot

    # Intercept OPTIONS requests
    if request.method == "OPTIONS":
        r = Response(status=200)
        r.access_control_max_age = 3600 * 24
        r.access_control_allow_methods = ["POST", "GET"]
        r.access_control_allow_origin = config.CORS_ALLOW_ORIGIN
        r.access_control_allow_headers = [
            "Access-Control-Allow-Headers",
            "Content-Type",
            "Authorization",
            "X-Requested-With"]
        return r(env, start_response)
    try:
        endpoint, values = urls.match()
        response = endpoint(request, **values)
    except NotFound as e:
        return e(env, start_response)

    # Add CORS headers to all responses
    response.access_control_allow_origin = config.CORS_ALLOW_ORIGIN
    response.access_control_allow_methods = ["POST", "GET"]
    response.access_control_allow_headers = [
        "Access-Control-Allow-Headers",
        "Content-Type",
        "Authorization",
        "X-Requested-With"]

    return response(env, start_response)


class J2EnvironmentMeta(type):
    """ Ensures a single instance of the J2Environment class """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                J2EnvironmentMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class J2Environment(metaclass=J2EnvironmentMeta):
    """
    A wrapper for a Jinja2 Environment.
    By calling `build` passing along a list
    of template paths, a Jinja2 environment is built.
    """

    def build(self, template_paths):
        self.env = Jinja2Environment(loader=FileSystemLoader(template_paths))


# Instantiate J2Environment
j2env = J2Environment()


def render_template(template_name, context=dict()):
    """ Renders a Jinja2 Template """
    template = j2env.env.get_template(template_name)
    return Response(template.render(**context), mimetype='text/html')


def OlafJSONEncoder(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
