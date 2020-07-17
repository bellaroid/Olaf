import os
import time
from olaf.http import Request, Response, route
from frozendict import frozendict
from olaf.tools import initialize, config
from werkzeug.serving import run_simple
from werkzeug.routing import NotFound
from werkzeug.local import Local, LocalManager
from werkzeug.middleware.shared_data import SharedDataMiddleware


class Olaf(object):

    def wsgi_app(self, env, start_response):
        # Bind URL Map
        url_map = route.url_map
        urls = url_map.bind_to_environ(env)
        local = Local()
        local.request = request = Request(env)  # pylint: disable=assigning-non-slot
        # Intercept OPTIONS requests
        if request.method == "OPTIONS":
            r = Response(status=200)
            r.access_control_max_age = 3600 * 24
            r.access_control_allow_methods = ["POST", "GET"]
            r.access_control_allow_origin = config.CORS_ALLOW_ORIGIN
            r.access_control_allow_headers = [
                "Access-Control-Allow-Headers", 
                "Content-Type", 
                "Authorization", 
                "X-Requested-With"]
            return r(env, start_response)
        try:
            endpoint, values = urls.match()
            response = endpoint(request, **values)
        except NotFound as e:
            return e(env, start_response)

        # Add CORS headers to all responses
        response.access_control_allow_origin = config.CORS_ALLOW_ORIGIN
        response.access_control_allow_methods = ["POST", "GET"]
        response.access_control_allow_headers = [
            "Access-Control-Allow-Headers", 
            "Content-Type", 
            "Authorization", 
            "X-Requested-With"]
        return response(env, start_response)

    def __call__(self, env, start_response):
        return self.wsgi_app(env, start_response)


def create_app():
    local = Local()
    local_manager = LocalManager([local])
    app = local_manager.make_middleware(Olaf())
    app = SharedDataMiddleware(app, {'/static': ('olaf', 'static')})
    return app


if __name__ == '__main__':
    initialize()
    app = create_app()
    debug = config.APP_DEBUG
    reloader = config.APP_RELOAD
    run_simple(config.APP_URL, config.APP_PORT, app, use_debugger=debug,
               use_reloader=reloader, passthrough_errors=True)
