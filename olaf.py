import os
import logging
import datetime, time
import colors
from werkzeug.wrappers import Request
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.utils import redirect
from werkzeug.serving import run_simple
from olaf.http import dispatch

logger = logging.getLogger("werkzeug")

class Olaf(object):

    def dispatch_request(self, request):
        start = time.time()
        response = dispatch(request)
        now = time.time()
        duration = round(now - start, 3)

        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        host = request.host.split(':', 1)[0]
        args = dict(request.args)

        log_params = [
            ('method', request.method, 'blue'),
            ('path', request.path, 'blue'),
            ('status', response.status_code, 'yellow'),
            ('duration', duration, 'green'),
            ('ip', ip, 'red'),
            ('host', host, 'red'),
            ('params', args, 'blue')
        ]

        request_id = request.headers.get('X-Request-ID')
        if request_id:
            log_params.append(('request_id', request_id, 'yellow'))

        parts = []
        for name, value, color in log_params:
            part = colors.color("{}={}".format(name, value), fg=color)
            parts.append(part)
        line = " ".join(parts)

        logger.info(line)
        return response

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

def create_app():
    app = Olaf()
    app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
            '/static':  os.path.join(os.path.dirname(__file__), 'static')
        })
    return app

if __name__ == '__main__':
    app = create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True, use_reloader=True, passthrough_errors=True)