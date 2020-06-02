import json
import os
import jinja2
from bson import ObjectId
from werkzeug.wrappers import Request as WZRequest, Response as WZResponse
from werkzeug.exceptions import BadRequest
from werkzeug.wrappers.json import JSONMixin
from werkzeug.routing import Map, Rule
from olaf import registry


class Request(JSONMixin, WZRequest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Response(JSONMixin, WZResponse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


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
        self.url_map = Map([])

    def __call__(self):
        return self.url_map

    def add(self, string, methods=None):
        """ Bind an URL pattern to a function """
        def decorator(function):
            rule = Rule(string, methods=methods, endpoint=function)
            self.url_map.add(rule)
            return function
        return decorator


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


@route.add("/jsonrpc", methods=["POST"])
def jsonrpc_dispatcher(request):
    response = Response(content_type="application/json", status=200)

    try:
        data = request.get_json()
    except BadRequest:
        response.set_data(json.dumps({
            "id": data["id"],
            "error": {
                "code": -32700,
                "message": "Parse error"
            },
            "jsonrpc": "2.0"
        }))
        return response

    if not set(data).issubset({"id", "method", "params", "jsonrpc"}):
        response.set_data(json.dumps({
            "id": data["id"],
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            },
            "jsonrpc": "2.0"
        }))
        return response

    if data["method"] == "call":
        try:
            result = handle_call(data)
            response.set_data(json.dumps({
                "id": data["id"],
                "jsonrpc": "2.0",
                "result": result
            }, default=OlafJSONEncoder))
        except Exception as e:
            response.set_data(json.dumps({
                "id": data["id"],
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": str(e)
                },
            }))
    else:
        response.set_data(json.dumps({
            "id": data["id"],
            "error": {
                "code": -32601,
                "message": "Method not found"
            },
            "jsonrpc": "2.0"
        }))

    return response


def handle_call(data):
    """ 
    Take an action according to params values
    """

    p = data["params"]
    method = p["method"]
    model = registry[p["model"]]

    if method == "search":
        query = p.get("query", {})
        result = model.search(query).ids()
    elif method == "read":
        ids = p.get("ids", [])
        fields = p.get("fields", [])
        result = model.browse(ids).read(fields)
    elif method == "count":
        query = p.get("query", {})
        result = model.search({}).count()
    elif method == "search_read":
        query = p.get("query", {})
        fields = p.get("fields", [])
        result = model.search(query).read(fields)

    return result
