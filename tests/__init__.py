from olaf.storage import AppContext
from olaf.tools import initialize

ctx = AppContext()
ctx.write("shell", True)

initialize()