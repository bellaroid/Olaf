import os
import logging
import time
import colors
from olaf.http import Request, route
from olaf.utils import initialize
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.serving import run_simple
from werkzeug.routing import Map, Rule, NotFound, RequestRedirect


logger = logging.getLogger("werkzeug")


class Olaf(object):

    def wsgi_app(self, environ, start_response):
        url_map = route.url_map
        request = Request(environ)
        urls = url_map.bind_to_environ(environ)
        try:
            endpoint, values = urls.match()
            response = endpoint(request, **values)
        except NotFound as e:
            return e(environ, start_response)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def create_app():
    app = Olaf()
    return app


if __name__ == '__main__':
    initialize()
    app = create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True,
               use_reloader=True, passthrough_errors=True)
