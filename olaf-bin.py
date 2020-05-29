import os
import logging
import time
import colors
from olaf.http import Request, Response, dispatch
from olaf.utils import initialize
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.serving import run_simple


logger = logging.getLogger("werkzeug")


class Olaf(object):

    @staticmethod
    def dispatch_request(request):
        response = dispatch(request)
        return response

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
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
