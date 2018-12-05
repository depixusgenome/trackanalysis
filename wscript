import sys
if sys.version_info.major == 3 and sys.version_info.minor == 6:
    require(python = {'dataclasses' : '0.6'})
make(locals())
