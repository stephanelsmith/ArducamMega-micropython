
import upydash as _ 
from micropython import const

_BASE62   = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
_BASE62_L = const(62)

# TODO, C/VIPER IMPLEMENTATION

# @micropython.native
def b62_encode_int(_int):
    b62 = _BASE62
    if _int == 0:
        return b62[0]
    ret = ''
    while _int != 0:
        ret = b62[_int % _BASE62_L] + ret
        _int //= _BASE62_L
    return ret

# @micropython.native
def b2a_base62(buff):
    # TODO PRE-ALLOCATE STRING
    _b62en = b62_encode_int #preload function
    return ''.join(_.map(buff, _b62en))
