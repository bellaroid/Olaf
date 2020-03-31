from werkzeug.wrappers import Response

def dispatch(request):
    return Response("Hello World!")