import os
import logging
import time
import colors
from olaf.http import Request, route
from olaf.tools import initialize
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.serving import run_simple
from werkzeug.routing import Map, Rule, NotFound, RequestRedirect
from frozendict import frozendict


logger = logging.getLogger("werkzeug")


class Olaf(object):

    def wsgi_app(self, env, start_response):
        url_map = route.url_map
        request = Request(env)
        urls = url_map.bind_to_environ(env)
        try:
            endpoint, values = urls.match()
            response = endpoint(request, **values)
        except NotFound as e:
            return e(env, start_response)
        return response(env, start_response)

    def __call__(self, env, start_response):
        return self.wsgi_app(env, start_response)


def create_app():
    app = Olaf()
    return app


if __name__ == '__main__':
    initialize()
    app = create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True,
               use_reloader=True, passthrough_errors=True)
