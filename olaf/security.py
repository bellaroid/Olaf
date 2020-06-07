import jwt
import datetime
from bson import ObjectId
from olaf.db import Connection
from olaf.http import JsonResponse, route
from olaf.tools import config
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash

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


@route.add("/token")
def token(request):
    """ Handles POST requests on the /api/token endpoint.
    If a valid email and password are provided within the
    JSON body, it responds with an access token.
    """

    try:
        data = request.get_json()
    except BadRequest:
        return JsonResponse({"msg": "Invalid JSON"})

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
