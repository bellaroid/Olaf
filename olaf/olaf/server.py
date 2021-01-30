import os
import time
from olaf import olaf
from olaf.http import Request, Response, route, dispatch
from olaf.tools import initialize, config
from olaf.storage import AppContext
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
    app = set_statics(app)
    return app


def set_statics(app):
    ctx = AppContext()
    modules = ctx.read("modules")
    for module_name in ctx.read("sorted_modules"):
        if modules[module_name]["static"] == True:
            if modules[module_name]["base"] == True:
                app = SharedDataMiddleware(
                    app, {"/base": ("olaf.addons.base", 'static')})
            else:
                app = SharedDataMiddleware(
                    app, {"/{}".format(module_name): (module_name, 'static')})
    return app


def start_server():
    app = create_app()
    debug = config.APP_DEBUG
    reloader = config.APP_RELOAD
    run_simple(config.APP_URL, config.APP_PORT, app, use_debugger=debug,
               use_reloader=reloader, passthrough_errors=True)
