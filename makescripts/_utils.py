#!/usr/bin/env python3
# encoding: utf-8
"The list of modules"
from wafbuilder.modules import Modules, basecontext

BaseContext = basecontext('../build')
MODULES     = Modules(src = ['core', 'src'])
__all__     = ['MODULES']
