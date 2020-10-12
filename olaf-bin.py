import os
import time
from olaf.http import Request, Response, route, dispatch
from olaf.tools import initialize, config
from werkzeug.serving import run_simple
from werkzeug.local import Local, LocalManager
from werkzeug.middleware.shared_data import SharedDataMiddleware


class Olaf(object):

    def __call__(self, env, start_response):
        return dispatch(env, start_response)


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
