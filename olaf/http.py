import json
from werkzeug.wrappers import Request as WZRequest, Response as WZResponse
from werkzeug.exceptions import BadRequest
from werkzeug.wrappers.json import JSONMixin
# from jwt import ExpiredSignatureError, InvalidSignatureError


class Request(JSONMixin, WZRequest):
    pass


class Response(JSONMixin, WZResponse):
    pass


def dispatch(request):
    if request.path == "/jsonrpc" and request.method in ["POST"]:
        return jsonrpc_dispatcher(request)
    response = Response()
    response.status_code = 404
    return response


def jsonrpc_dispatcher(request):
    if not request.is_json:
        response = Response(json.dumps({"message": "Invalid JSON"}))
        return response
    response = Response(json.dumps(
        {"message": "This is the JSONRPC dispatcher"}))
    return response
