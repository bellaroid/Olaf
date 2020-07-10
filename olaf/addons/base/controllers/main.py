from olaf.http import route, Response, render_template
import datetime

@route.add("/")
def index(request):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("index.html.j2", dict(now=now))
