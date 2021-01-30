import click
from olaf.storage import AppContext
from olaf.tools.bootstrap import initialize
from olaf.olaf.server import start_server
from olaf.olaf.shell import Shell


@click.command()
@click.option("--shell", "-s", "shell", is_flag=True, type=bool)
@click.option("--log-level", "-l", "loglevel", default="info", type=str)
def main(shell, loglevel):
    if shell:
        ctx = AppContext()
        ctx.write("shell", True)
        initialize(loglevel=loglevel)
        shell = Shell()
        shell.run()
    else:
        initialize(loglevel=loglevel)
        start_server()
