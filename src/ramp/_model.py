#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
defines the model (config, default parameters) of ramp
'''
class RampModel:
    ''' holds instruction to handle the data
    If values change in the Model the Controller must be notified and act accordingly
    '''
    def __init__(self, **kwargs):
        self.scale = 5.0
        self.needsCleaning:bool = False
        self.corrThreshold = 0.5 # if above then correlation
        self._minExt:float = kwargs.get("minExtension",0.0)
        self.window = 7
        self._zclthreshold = kwargs.get("zclthreshold",None)
        self.good_ratio = kwargs.get("good_ratio",0.8) # if good_cycles/cycles above, then good

    def set_zclthreshold(self,value):
        '''
        sets _zclthreshold
        if _minExt is changed call controller and apply changes in RampData
        '''
        self._zclthreshold = value

    def get_zclthreshold(self):
        '''
        returns  _zclthreshold
        '''
        return self._zclthreshold

    def set_minext(self,value):
        '''
        set _minExt
        if _minExt is changed call controller and apply changes in RampData
        '''
        self._minExt = value

    def get_minext(self):
        '''
        Returns _minExt value.
        Warns User if _minExt has not be set.
        '''
        return self._minExt
