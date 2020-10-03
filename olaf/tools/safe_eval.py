# Inspired by (stolen from)
# https://gist.github.com/flying-sheep/5135722
# and
# https://github.com/odoo/odoo/blob/14.0/odoo/tools/safe_eval.py

import functools
import traceback # print REPL traceback

class SecurityException(RuntimeError):
	"""
	Block introspective attributes/functions (e.g. __dict__, __class__)
	"""
	def __init__(self, *args):
		super().__init__("You may not use expressions containing '__'", *args)

# Block access to dynamic attribute access by string ( e.g. vars(), getattr())
# and dangerous functions (e.g. open(), __import__())
builtins = {
	'True': True,
    'False': False,
    'None': None,
    'bytes': bytes,
    'str': str,
    'unicode': str,
    'bool': bool,
    'int': int,
    'float': float,
    'enumerate': enumerate,
    'dict': dict,
    'list': list,
    'tuple': tuple,
    'map': map,
    'abs': abs,
    'min': min,
    'max': max,
    'sum': sum,
    'reduce': functools.reduce,
    'filter': filter,
    'round': round,
    'len': len,
    'repr': repr,
    'set': set,
    'all': all,
    'any': any,
    'ord': ord,
    'chr': chr,
    'divmod': divmod,
    'isinstance': isinstance,
    'range': range,
    'xrange': range,
    'zip': zip,
    'Exception': Exception
}

def safe_eval(code, _locals={}):
    if '__' in code:
        raise SecurityException()
    eval(code, {'__builtins__': builtins}, _locals)

