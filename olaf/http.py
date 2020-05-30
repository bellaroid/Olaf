import json
from werkzeug.wrappers import Request as WZRequest, Response as WZResponse
from werkzeug.exceptions import BadRequest
from werkzeug.wrappers.json import JSONMixin


class Request(JSONMixin, WZRequest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.json_module = json


class Response(JSONMixin, WZResponse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.json_module = json


def dispatch(request):
    if request.path == "/jsonrpc" and request.method in ["POST"]:
        return jsonrpc_dispatcher(request)
    response = Response()
    response.status_code = 404
    return response


def jsonrpc_dispatcher(request):
    response = Response(content_type="application/json", status=200)

    try:
        data = request.get_json()
    except BadRequest:
        response.set_data(json.dumps({
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error"
            },
            "jsonrpc": "2.0"
        }))
        return response

    if not set(data).issubset({"id", "method", "params", "jsonrpc"}):
        response.set_data(json.dumps({
            "id": None,
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            },
            "jsonrpc": "2.0"
        }))
        return response

    if data["method"] == "call":
        params = data["params"]
        response.set_data(handle_call(params))
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

def handle_call(request):
    pass

