import os
import logging
import time
from olaf.http import Request, route
from olaf.tools import initialize
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.serving import run_simple
from werkzeug.routing import Map, Rule, NotFound, RequestRedirect
from werkzeug.local import Local, LocalManager
from frozendict import frozendict

class Olaf(object):

    def wsgi_app(self, env, start_response):
        # Bind URL Map
        url_map = route.url_map
        urls = url_map.bind_to_environ(env)
        local = Local()
        local.request = request = Request(env) # pylint: disable=assigning-non-slot
        try:
            endpoint, values = urls.match()
            response = endpoint(request, **values)
        except NotFound as e:
            return e(env, start_response)
        return response(env, start_response)

    def __call__(self, env, start_response):
        return self.wsgi_app(env, start_response)


def create_app():
    local = Local()
    local_manager = LocalManager([local])
    app = local_manager.make_middleware(Olaf())
    return app


if __name__ == '__main__':
    initialize()
    app = create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True,
               use_reloader=True, passthrough_errors=True)
