#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add a config tool
"""
import bokeh.core.properties as props
from bokeh.models.tools import Action

class ConfigTool(Action):
    ''' config tool
    '''
    configclick        = props.Int(-1)
    __implementation__ = 'toolbarconfig.coffee'
