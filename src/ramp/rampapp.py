#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
first simple version
Will need rewritting to use Event()
'''

from typing import Sequence
from bokeh.plotting import curdoc, figure
from bokeh.layouts import widgetbox, column, row
from bokeh.models import ColumnDataSource
from bokeh.models import TextInput, Div, Button
import pandas as pd
import numpy
import ramp
import view.dialog


class DisplayText:
    u''' Manages the Display : widgets, bokeh doc
    '''
    def __init__(self, prefix):

        self.prefix = prefix
        self.div = Div(text = prefix, render_as_text = True,
                       width=300, height=50)

    def update(self, data:Sequence):
        u''' update shown data
        '''
        self.div.text = self.prefix + str(data)

class DisplayHist:
    u''' Contains fig and ColumnDataSource
    '''
    def __init__(self, **kwargs):
        u'''
        '''
        title = kwargs.get("title", None)
        x_label = kwargs.get("x_label", None)
        y_label = kwargs.get("y_label", None)
        self.fig = figure(title = title, x_axis_label = x_label,
                          y_axis_label = y_label)
        self.datasrc = ColumnDataSource({"top":[0], "left":[0], "right":[0]})
        self.fig.quad(top = "top", bottom = 0,
                      left = "left", right = "right", source = self.datasrc)

    def update(self,data:dict)->None:
        u''' updates columnDataSource
        '''
        self.datasrc.data = data
class Data:
    u''' Manages the data
    '''
    def __init__(self):
        u''' initialise  rampData, RampModel
        '''

        self.rpmod = ramp.RampModel()
        self.rpmod.setMinExt(0.0)
        self.rpdata = ramp.RampData()
        self.rpdata.model = self.rpmod
        self.rpfulldata = ramp.RampData()
        self.rpfulldata.model = self.rpmod


    def update_data(self,filename: str):
        u'''
        updates data if the filename changes
        '''
        print("updating rpdata from file")
        self.rpdata.setTrack(filename)
        self.rpdata.clean()
        self.rpfulldata.setTrack(filename)
        print("updating rpdata from file : Done")

class Select:
    u'''
    Select widget. Open file dialog on update
    '''
    def __init__(self,label,filetypes):
        u'''
        sets a Button label and a file dialog
        '''

        self.select = Button(label = label)
        self.dial = view.dialog.FileDialog(filetypes = filetypes,
                                           title = "diag title")

class MyDisplay:
    u'''
    My personal Display
    '''

    def __init__(self, data = Data(), doc = curdoc()):
        u'''create all widgets
        '''
        self.data = data
        self.divs = {"good":DisplayText("good beads are : "),
                     "ugly":DisplayText("ugly beads are : "),
                     "fixed":DisplayText("fixed beads are : ")}

        self.hists = {"zmop": DisplayHist(x_label = "zmag_open",
                                          y_label ="Probability"),
                      "zmcl": DisplayHist(x_label = "zmag_close",
                                          y_label ="Probability")}
        self.txt_inputs = {"minext" : \
                           TextInput(value = "0.0", title = "min molecule extension")}

        def tmp(attr,old,new): # pylint: disable=unused-argument
            u''' bokeh requires attr, old, new'''
            return self.changeminext()

        self.txt_inputs["minext"].on_change(tmp)


        self.sel = {"rpfile":Select(label = "Select file", filetypes = "trk")}
        self.sel["rpfile"].select.on_click(self.change_data_file)

        self.doc = doc

        self.set_mylayout()

    def set_mylayout(self):
        u''' specific layout of widgets
        '''
        docrows = []
        docrows.append(widgetbox(self.sel["rpfile"]))
        docrows.append(self.divs["good"])
        docrows.append(self.divs["ugly"])
        docrows.append(widgetbox(self.txt_inputs["minext"]))
        docrows.append(self.divs["fixed"])
        # docrows.append(row(column(fightop,tableop), column(fightcl,tablecl)) )
        docrows.append(row(column(self.hists["zmop"]), column(self.hists["zmcl"])) )
        self.doc().add_root(column(*docrows))

    def changeminext(self):
        u'''
        Called when minimal extension value is changed
        '''
        print("changing min mol extension")
        self.data.rpmod.setMinExt(float(self.txt_inputs["minext"].value))
        fixed =  {} if self.data.rpfulldata is None\
                 else self.data.rpfulldata.getFixedBeadIds()
        self.divs["fixed"].update(fixed)

    def change_data_file(self):
        u'''
        called when User selects a new file
        '''
        file_diag = view.dialog.FileDialog(filetypes = "trk", title = "diag title")
        filename = file_diag.open()
        self._update_rpdata_from_file(filename)
        self._update_text_info()
        self._update_zmag_info()

    def open(self):
        u'''
        returns the Bokeh doc
        '''

        return self.doc


    def _update_rpdata_from_file(self,filename:str)->None:
        print("in _update_rpdata_from_file")
        self.data.rpdata.setTrack(filename)
        self.data.rpdata.clean()
        self.data.rpfulldata.setTrack(filename)
        print("out _update_rpdata_from_file")


    def _update_text_info(self):
        print ("in _update_text_info")
        good = {} if self.data.rpfulldata is None\
                  else self.data.rpfulldata.getGoodBeadIds()
        ugly = {} if self.data.rpfulldata is None\
               else self.data.rpfulldata.noBeadCrossIds()
        fixed =  {} if self.data.rpfulldata is None\
                 else self.data.rpfulldata.getFixedBeadIds()
        self.divs["good"].update(good)
        self.divs["ugly"].update(ugly)
        self.divs["fixed"].update(fixed)
        print ("out _update_text_info")


    def _update_zmag_info(self):
        print("in _update_zmag_info")
        #global topdata, tcldata, src_fightop, src_fightcl
        zmagop = pd.DataFrame() if self.data.rpdata is \
                 None else self.data.rpdata.zmagOpen()
        zmagcl = pd.DataFrame() if self.data.rpdata is \
                 None else self.data.rpdata.zmagClose()
        #zmoseries = pd.Series(zmagop.values.flatten())
        histop, edgesop = numpy.histogram(zmagop.values.flatten())
        dataop = {"top" : histop/histop.sum(),
                  "left" : edgesop[:-1], "right" : edgesop[1:]}
        self.hists["zmop"].update(dataop)

        #topdata.data = {"quantiles":quantiles,
        #                "zmag":[round(zmoseries.quantile(i),2) for i  in quantiles]}
        #print("updated topdata.data")
        #zmcseries = pd.Series(zmagcl.values.flatten())
        histcl, edgescl = numpy.histogram(zmagcl.values.flatten())
        datacl = {"top":histcl/histcl.sum(), "left":edgescl[:-1], "right":edgescl[1:]}
        self.hists["zmcl"].update(datacl)
        #tcldata.data = {"quantiles":quantiles,
        #                "zmag":[round(zmcseries.quantile(i),2) for i  in quantiles]}
        print("out _update_zmag_info")

