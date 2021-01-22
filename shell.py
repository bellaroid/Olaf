"""
The following file is meant to provide a 
basic shell context.

Inspired by / stolen from https://github.com/odoo/odoo/blob/14.0/odoo/cli/shell.py
"""
import code
import logging
import os
import signal
import sys
from bson import ObjectId
from olaf import registry
from olaf.db import Connection
from olaf.tools import initialize
from olaf.storage import AppContext
from olaf.tools.environ import Environment

_logger = logging.getLogger(__name__)

ctx = AppContext()
ctx.write("shell", True)

initialize()

def raise_keyboard_interrupt(*a):
    raise KeyboardInterrupt()
class Console(code.InteractiveConsole):
    def __init__(self, locals=None, filename="<console>"):
        code.InteractiveConsole.__init__(self, locals, filename)
        try:
            import readline
            import rlcompleter
        except ImportError:
            print('readline or rlcompleter not available, autocomplete disabled.')
        else:
            readline.set_completer(rlcompleter.Completer(locals).complete)
            readline.parse_and_bind("tab: complete")


class Shell:
    """
    Start Olaf in an interactive shell
    """
    supported_shells = ['ipython', 'python']

    def console(self, local_vars): 
        shells_to_try = self.supported_shells
        for shell in shells_to_try:
            try:
                return getattr(self, shell)(local_vars)
            except ImportError:
                pass
            except Exception:
                _logger.warning("Could not start '%s' shell." % shell)
                _logger.debug("Shell error:", exc_info=True)

    def ipython(self, local_vars):
        from IPython import start_ipython
        start_ipython(argv=[], user_ns=local_vars)

    def python(self, local_vars):
        Console(locals=local_vars).interact()

    def run(self):
        conn = Connection()
        client = conn.cl
        with client.start_session() as session:
            with session.start_transaction():
                uid = ObjectId("000000000000000000000000")
                env = Environment(uid, session)
                baseUser = registry["base.user"]
                rootUser = baseUser(env)
                self.console({"self": rootUser})
                session.abort_transaction()

shell = Shell()
shell.run()