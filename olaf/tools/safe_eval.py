# Inspired by (stolen from)
# https://gist.github.com/flying-sheep/5135722

"""A yet-to-be-disproven-as-safe python expression shell
Blacklisted functionalities include:
1. Anything containing '__', because introspection allows many, many hacks.
2. open(), because it allows you to overwrite files
3. memoryview(), because it manipulates memory (?)
4. help(), because it drops you into a manpage-reader with !shell access
5. eval(), exec(), compile(), because they allow code execution via constructable strings, circumventing #1
6. vars(), getattr(), because they allow attribute access via constructable strings, circumventing #1
7. delattr(), setattr(), hasattr(), because they are all but useless without getattr() (?)
8. type(), because it allows class construction (?)
9. super(), @property, @classmethod, @staticmethod, because they are only useful in class definitions
Points denoted with (?) are thrown in for good measure, not because i know they can be exploited :)
"""

import builtins  # unified access to its __dict__
import readline  # history, cursor movement
import traceback # print REPL traceback

class SecurityException(RuntimeError):
	"""Security measure 1 of 2:
	Block introspective attributes/functions (e.g. __dict__, __class__)
	"""
	def __init__(self, *args):
		super().__init__("You may not use expressions containing '__'", *args)

# Whitelist, security measure 2 of 2:
# Block access to dynamic attribute access by string ( e.g. vars(), getattr())
# and dangerous functions (e.g. open(), __import__())
# Whitelist in order to be future-proof and for prettier listing
safe_names = """
object
bool int float complex
str bytes bytearray
tuple list
set frozenset
dict
slice range
abs
round
pow
divmod
iter
next
len sum
min max
all any
map filter
zip
enumerate
sorted
reversed
bin hex oct
ascii
repr
chr ord
format
dir
locals globals
id hash
isinstance
issubclass
callable
print
input
exit quit
copyright credits license
""".strip()

safe_name_set = frozenset(safe_names.split())

safe_builtins = {name: builtins.__dict__[name] for name in safe_name_set}


def safe_eval(code, _locals={}):
    if '__' in code:
        raise SecurityException()
    eval(code, {'__builtins__': safe_builtins}, _locals)

