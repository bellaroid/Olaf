from olaf import registry
from olaf.db import Connection
from olaf.http import Request, JsonResponse, route
from olaf.tools import config
from olaf.security import jwt_required
from olaf.tools.environ import Environment
from werkzeug.exceptions import BadRequest
from werkzeug.local import Local

@route.add("/jsonrpc", methods=["POST"])
@jwt_required
def jsonrpc_dispatcher(uid, request):
    """ 
    JSONRPC Dispatcher

    Expects a POST JSON request and 
    returns a response compliant
    with the directives listed in 
    https://www.jsonrpc.org/specification
    """

    # Ensure JSON request
    try:
        data = request.get_json()
    except BadRequest:
        return JsonResponse({
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error"
            },
            "jsonrpc": "2.0"
        })

    # Ensure basic parameters are present
    if not set(data).issubset({"id", "method", "params", "jsonrpc"}):
        return JsonResponse({
            "id": data["id"],
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            },
            "jsonrpc": "2.0"
        })

    # Handle CALL method
    if data["method"] == "call":
        try:
            res = handle_call(data, uid)
            result = {
                "id": data["id"],
                "jsonrpc": "2.0",
                "result": res
            }
        except Exception as e:
            raise
            result = {
                "id": data["id"],
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": str(e)
                }
            }
    else:
        # Method not found
        result = {
            "id": data["id"],
            "error": {
                "code": -32601,
                "message": "Method not found"
            },
            "jsonrpc": "2.0"
        }

    return JsonResponse(result)


def handle_call(data, uid):
    """
    Take an action according to params values
    TODO: This is a provisory method until
    there's something more sophisticated.
    """

    p = data["params"]
    method = p["method"]
    cls = registry[p["model"]]

    conn = Connection()
    client = conn.cl

    if config.DB_RS_E:    
        with client.start_session() as session:
            with session.start_transaction():
                env = Environment(uid, session)
                model = cls(env)
                result = call_method(p, model, method)
    else:
        env = Environment(uid)
        model = cls(env)
        result = call_method(p, model, method)
    return result


def call_method(p, model, method):
    import pdb; pdb.set_trace()
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
    elif method == "unlink":
        query = p.get("query", {})
        result = model.search(query).unlink()
    return result
