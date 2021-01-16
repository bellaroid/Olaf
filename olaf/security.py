import jwt
import datetime
from bson import ObjectId
from olaf.db import Connection
from olaf.tools.safe_eval import safe_eval
from functools import reduce
from olaf.http import Response, JsonResponse, route
from olaf.tools import config
from olaf.tools.environ import Environment
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash

acl_operation_field_map = {
    "read":     "allow_read",
    "write":    "allow_write",
    "create":   "allow_create",
    "unlink":   "allow_unlink"
}

dls_operation_field_map = {
    "read":     "on_read",
    "write":    "on_write",
    "create":   "on_create",
    "unlink":   "on_unlink"
}

def jwt_required(func, *args, **kwargs):
    """ Methods wrapped around this decorator
    will require an authorization header with a valid
    access token.
    """
    def function_wrapper(*args, **kwargs):
        request = args[0]
        access_token = request.headers.get("Authorization", None)

        # Make sure header is present and it's valid
        if not access_token or not access_token.startswith("Bearer "):
            return JsonResponse({"msg": "Missing or Invalid Authorization Header"}, status=401)

        # Attempt to decode
        try:
            payload = jwt.decode(access_token[7:], key=config.SECRET_KEY)
            assert({"expires", "uid"} <= set(payload.keys()))
        except Exception:
            return JsonResponse({"msg": "Invalid Token"}, status=401)

        # Check if token is expired
        fmt_str = r"%Y-%m-%dT%H:%M:%S.%f"
        if datetime.datetime.now() > datetime.datetime.strptime(payload["expires"], fmt_str):
            return JsonResponse({"msg": "Access Token Has Expired"}, status=401)

        # Try to create ObjectID out of str
        try:
            oid = ObjectId(payload["uid"])
        except TypeError:
            return JsonResponse({"msg": "Invalid Token"}, status=401)

        # Verify if user exists in database
        conn = Connection()
        user = conn.db["base.user"].find_one({"_id": oid})
        
        if not user:
            # Either user was deleted or token was tampered with
            return JsonResponse({"msg": "Invalid Token"}, status=401)

        return func(oid, *args, **kwargs)
    return function_wrapper


@route.add("/token", methods=["POST"])
def token(request):
    """ Handles POST requests on the /api/token endpoint.
    If a valid email and password are provided within the
    JSON body, it responds with an access token.
    """

    try:
        data = request.get_json()
    except BadRequest:
        return JsonResponse({"msg": "Invalid JSON"}, status=400)

    # Fail if data is None
    if data is None:
        return JsonResponse({"msg": "Invalid JSON"}, status=400)

    # Make sure request body is valid
    if not "email" in data or not "password" in data:
        return JsonResponse({"msg": "Malformed Request"}, status=400)

    conn = Connection()
    user = conn.db["base.user"].find_one({"email": data["email"]})

    # Check user exists
    if not user:
        return JsonResponse({"msg": "Bad Username or Password"}, status=401)

    # Check password is valid
    if not check_password_hash(user["password"], data["password"]):
        return JsonResponse({"msg": "Bad Username or Password"}, status=401)

    # Calculate token expiration time
    token_expiration = datetime.datetime.now() + datetime.timedelta(
        seconds=config.JWT_EXPIRATION_TIME)

    # The token payload is composed with the email and the expiration time.
    # There's no need to store it in database.
    payload = {"uid": str(user["_id"]),
               "expires": token_expiration.isoformat()}

    return JsonResponse({"access_token": jwt.encode(payload, key=config.SECRET_KEY).decode('utf-8')})


class AccessError(Exception):
    pass

def check_access(docset, operation, skip_DLS=False):
    """ 
    Check if a given user can perform 
    a given operation on a given model
    """
    # Read docset attributes
    model_name = docset._name
    uid = docset.env.context["uid"]

    # Root user bypasses all security checks
    if uid == ObjectId("000000000000000000000000"):
        return

    conn = Connection()
    user = conn.db["base.user"].find_one({"_id": uid })
    if not user:
        raise AccessError("User not found")

    # Search in user/group many2many intermediate collection
    # for groups this is user is related to.
    user_group_rels = conn.db["base.user.group.rel"].find({"user_oid": uid})

    # Create a list of groups this user belongs to
    groups = [rel["group_oid"] for rel in user_group_rels]
    
    # Abort right here if user doesn't belong to any groups
    if not groups:
        raise AccessError(
            "Access Denied -- Model: '{}' "
            "Operation: '{}' - User: '{}'".format(
                model_name, operation, user["_id"]))

    # The following function calls will raise an AccessError
    # if user doesn't have the required privileges to operate
    # the requested model.
    check_ACL(model_name, operation, groups, user)
    if not skip_DLS:
        check_DLS(model_name, operation, groups, user, docset)

    return

def check_ACL(model_name, operation, groups, user):
    """
    Computes the ACL (Access Control List)
    Raises AccessError if the given user cannot perform
    the requested operation on the requested model.
    """

    # Search for ACL Rules associated to all of these groups
    # and also for ACL Ruless not associated to any group (Globals)
    conn = Connection()
    acl_rules = conn.db["base.acl"].find(
        {
            "model": model_name,
            "$or": [
                {"group_id": {"$in": groups}}, 
                {"group_id": None}]})

    # Compute access
    allow_list = [rule[acl_operation_field_map[operation]] for rule in acl_rules]
    if allow_list:
        allow = reduce(lambda x, y: x | y, allow_list)
    else:
        allow = []

    if not allow:
        # Deny access
        raise AccessError(
            "Access Denied -- Model: '{}' "
            "Operation: '{}' - User: '{}'".format(
                model_name, operation, user["_id"]))
    
    return

def check_DLS(model_name, operation, groups, user, docset):
    """
    Raises AccessError if the given user cannot perform
    the requested operation on the requested DocSet.
    """
    q = build_DLS_query(model_name, operation, groups, user)
    
    # q is False if there are no access rules
    # affecting the current user and operation.
    if q:
        # Instantiate a DocSet (class Model)
        dls_docset = docset.__class__(docset.env, q)

        # If the docset the user has instantiated
        # is different from the one we created by
        # mixing the same query with all the 
        # DLS queries, then we can safely say
        # user can't perform the requested operation.
        if not docset == dls_docset:
            raise AccessError(
                "Access Denied -- Not allowed "
                "to perform the requested operation. "
                "Model: {} - Operation: '{}' - "
                "User: '{}'".format(
                    model_name, operation, user["_id"]))
    return

def build_DLS_query(model_name, operation, groups, user):
    """
    Builds the DLS (Document Level Security) query.
    
    This mongo query is the combination of all individual 
    mongo queries that affect the current user for a 
    given operation on a given model.

    DLS rules not associated to any group are considered
    as "global" and they affect everyone.

    The resulting query will have the following format:
    {
        "$and": [
            {"whatever_the_user_requested": "..."},
            {"global_rule_1": "..."},
            {"global_rule_2": "..."},
            {
                "$or": [
                    {"group_rule_1": "..."},
                    {"group_rule_2": "..."}
                ]
            }
        ]
    }

    From the previous example, we can see global rules
    constraint the domain of documents; and so do the
    combination of all user specific rules. However,
    one group specific rule may relax other group
    specific rules previously found (but not a global one).
    """
    
    # Root user bypasses all security checks
    if user == ObjectId("000000000000000000000000"):
        return False

    conn = Connection()
    
    # Search for DLS Rules associated to all of these groups
    group_rules = conn.db["base.dls"].find({
        dls_operation_field_map[operation]: True,
        "model": model_name,
        "group_id": {"$in": groups}})

    # ...and also for DLS Rules not associated to any group (Globals)
    global_rules = conn.db["base.dls"].find({
        dls_operation_field_map[operation]: True,
        "model": model_name,
        "group_id": None})

    # Initialize queries list
    group_queries = []
    global_queries = []

    # Evaluate global expressions and add them to their list
    for rule in global_rules:
        query = safe_eval(rule["query"], {"user": user})
        if not isinstance(query, dict):
            raise ValueError(
                "Invalid query in DLS rule '{}' ({}): '{}'".format(
                    rule.name, rule._id, rule["query"]))
        global_queries.append(query)

    # Evaluate user expressions and add them to their list
    for rule in group_rules:
        query = safe_eval(rule["query"], {"user": user})
        if not isinstance(query, dict):
            raise ValueError(
                "Invalid query in DLS rule '{}' ({}): '{}'".format(
                    rule.name, rule._id, rule["query"]))
        group_queries.append(query)
    
    # Build query structure
    if len(group_queries) > 0:
        global_queries.append({"$or": group_queries})
    
    if len(global_queries) > 0:
        q = {"$and": global_queries}
    else:
        return False

    return q