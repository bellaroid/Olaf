import click
from olaf.storage import AppContext
from olaf.tools.bootstrap import initialize
from olaf.olaf.server import start_server
from olaf.olaf.shell import Shell


@click.command()
@click.option("--shell", "-s", "shell", is_flag=True, type=bool)
def main(shell):
    if shell:
        ctx = AppContext()
        ctx.write("shell", True)
        initialize()
        shell = Shell()
        shell.run()
    else:
        initialize()
        start_server()
