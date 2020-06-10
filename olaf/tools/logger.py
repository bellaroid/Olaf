import click
import logging
from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG

def setup_logger(logger):
    logger.setLevel(logging.DEBUG)

    sh = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s.%(funcName)s - %(message)s")
    sh.setFormatter(formatter)
    color = click.style

    def decorate_emit(fn):
    # add methods we need to the class
        def new(*args):
            levelno = args[0].levelno
            if(levelno >= logging.CRITICAL):
                colname = 'magenta'
            elif(levelno >= logging.ERROR):
                colname = 'red'
            elif(levelno >= logging.WARNING):
                colname = 'yellow'
            elif(levelno >= logging.INFO):
                colname = 'green'
            elif(levelno >= logging.DEBUG):
                colname = 'cyan'
            else:
                colname = 'white'

            args[0].levelname = color(args[0].levelname, fg=colname, bold=True)

            return fn(*args)
        return new
    sh.emit = decorate_emit(sh.emit)
    logger.addHandler(sh)