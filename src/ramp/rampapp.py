#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
first simple version
Will need rewritting to use Event()
'''
import os
from bokeh.plotting import curdoc, figure
from bokeh.layouts import widgetbox, column, row
from bokeh.models import ColumnDataSource, HoverTool
from bokeh.models import TextInput, Div, Button
import pandas as pd
import numpy
import view.dialog

import ramp
from . import _utils as utils

class DisplayText:
    u''' Manages the Display : widgets, bokeh doc
    '''
    def __init__(self,**kwargs):

        self.prefix = kwargs.get("prefix","")
        width = kwargs.get("width",500)
        height = kwargs.get("height",50)
        self.div = Div(text = self.prefix, render_as_text = True,
                       width=width, height=height)

    def update(self, newstr:str):
        u''' update shown text
        '''
        self.div.text = self.prefix + str(newstr)

class DisplayHist:
    u''' Contains fig and ColumnDataSource
    '''
    def __init__(self, **kwargs):
        u'''
        '''
        title = kwargs.get("title", None)
        x_label = kwargs.get("x_label", None)
        y_label = kwargs.get("y_label", None)
        circle_size = kwargs.get("circle_size", 10)
        fig_width = kwargs.get("fig_width", 600)
        fig_height = kwargs.get("fig_height", 600)
        fill_color = kwargs.get("fill_color", "red")
        self.with_cdf = kwargs.get("with_cdf", False) # bool
        self.normed = kwargs.get("normed", False) # bool

        self.fig = figure(title = title,
                          x_axis_label = x_label,
                          y_axis_label = y_label,
                          width = fig_width,
                          height = fig_height)


        hover = HoverTool(tooltips=[("(x,y)", "(@x, @cdf)")])
        self.fig.add_tools(hover)
        self.rawdata = pd.Series()

        self.cdfdata = ColumnDataSource({"x" : [], "cdf" : [] }) if \
                       self.with_cdf else None

        self.histdata = ColumnDataSource({"top":[0], "left":[0], "right":[0]})
        self.fig.quad(top = "top", bottom = 0,
                      left = "left", right = "right", source = self.histdata)


        if self.with_cdf :
            self.fig.circle(x="x",
                            y="cdf",
                            source = self.cdfdata,
                            size = circle_size,
                            fill_color = fill_color)

    def update(self, data)->None:
        u'''
        updates the values displayed
        '''
        self.rawdata = pd.Series(numpy.sort(data))

        hist, edges = numpy.histogram(data)
        if self.normed:
            self.histdata.data = {"top" : hist/float(hist.sum()),
                                  "left" : edges[:-1], "right" : edges[1:]}
        else:
            self.histdata.data = {"top" : hist,
                                  "left" : edges[:-1], "right" : edges[1:]}


        if self.cdfdata is not None:
            # to correct for bokeh indices there is duplicates in cdf: set(tuple(x,y))
            cdf = numpy.array([(self.rawdata<=i).sum() for i in self.rawdata])
            cdf = cdf/float(cdf.size)
            xycoords = set([(self.rawdata.values[i], cdf[i]) for i in range(len(cdf))])

            self.cdfdata.data = {"x" : [i[0] for i in xycoords],
                                 "cdf" : [i[1] for i in xycoords]}

        return

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
        self.rpdata.setTrack(filename)
        self.rpdata.clean()
        self.rpfulldata.setTrack(filename)

class Select:
    u'''
    Select widget. Open file dialog on update
    '''
    def __init__(self,label,filetypes):
        u'''
        sets a Button label and a file dialog
        '''

        self.button = Button(label = label)
        self.dial = view.dialog.FileDialog(filetypes = filetypes,
                                           title = "please choose a ramp file")

class MyDisplay: # pylint: disable=too-many-instance-attributes
    u'''
    My display
    '''

    def __init__(self, *args, **kwargs): # pylint: disable=unused-argument
        u'''create all widgets
        '''
        self.data = kwargs.get("data", None)
        self.doc = kwargs.get("doc", None)
        self.filename = kwargs.get("filename", None)
        if self.data is None:
            self.data = Data()
        if self.doc is None:
            self.doc = curdoc()
        self.divs = {"ngoods":DisplayText(prefix="number of good beads : "),
                     "good":DisplayText(prefix="good beads are : "),
                     "ugly":DisplayText(prefix="ugly beads are : "),
                     "fixed":DisplayText(prefix="fixed beads are : "),
                     "filestatus":DisplayText(prefix="")}

        self.hists = {"zmop": DisplayHist(title = "Phase 3",
                                          x_label = "zmag_open",
                                          y_label ="Probability",
                                          normed = True,
                                          with_cdf = True),
                      "zmcl": DisplayHist(title = "Phase 5",
                                          x_label = "zmag_close",
                                          y_label ="Probability",
                                          normed = True,
                                          with_cdf = True),
                      "zmcl_reverse": DisplayHist(title = "Ratio of closed hairpin",
                                                  x_label = "zmag_close",
                                                  y_label ="Probability",
                                                  normed = True,
                                                  with_cdf = True),
                      "HPsize": DisplayHist(title = "HP size estimate of good beads",
                                            x_label = "size (micrometer unit)",
                                            y_label ="number of estimates",
                                            normed = False,
                                            with_cdf = False)}
        self.txt_inputs = {"minext" : \
                           TextInput(value = "0.0",
                                     title = "min molecule extension (micrometer unit)"),
                           "zcl_threshold":\
                           TextInput(value = "0.0",
                                     title = "keep bead if zmag close is above :")}

        def call_changeminext(attr,old,new): # pylint: disable=unused-argument
            u''' bokeh requires attr, old, new'''
            return self.changeminext()

        def call_changezclthreshold(attr,old,new): # pylint: disable=unused-argument
            u''' bokeh requires attr, old, new'''
            return self.changezclthreshold()

        self.txt_inputs["minext"].on_change("value",call_changeminext)

        self.txt_inputs["zcl_threshold"].on_change("value",call_changezclthreshold)


        self.buttons = {"gen_rpdiscard":Button(label=" Generate ramp_discard file")}
        self.buttons["gen_rpdiscard"].on_click(self.generate_rpdiscard)

        self.sel = {"rpfile":Select(label = "Select file", filetypes = "trk")}
        self.sel["rpfile"].button.on_click(self.change_data_file)

        self.set_layout()

    def set_layout(self):
        u''' specific layout of widgets
        '''
        self.doc.add_root(column(*self.get_layout()))


    def get_layout(self):
        u'''
        returns docrows
        '''
        docrows = []
        docrows.append(row(widgetbox(self.sel["rpfile"].button),self.divs["filestatus"].div))
        docrows.append(self.divs["ngoods"].div)
        docrows.append(self.divs["good"].div)
        docrows.append(self.divs["ugly"].div)
        docrows.append(widgetbox(self.txt_inputs["minext"]))
        docrows.append(self.divs["fixed"].div)
        docrows.append(row(column(self.hists["zmop"].fig), column(self.hists["zmcl"].fig)) )

        # add file which generates a ramp_discarded.csv (including a list of fixed and ugly beads)
        # (and beads which are not yet closed at zcl_threshold)
        docrows.append(row(self.hists["zmcl_reverse"].fig,
                           widgetbox(self.txt_inputs["zcl_threshold"],
                                     self.buttons["gen_rpdiscard"])))
        docrows.append(self.hists["HPsize"].fig)
        return docrows

    def changezclthreshold(self):
        u'''
        Called when the threshold of zcl value is changed
        '''
        self.data.rpmod.set_zclthreshold(float(self.txt_inputs["zcl_threshold"].value))


    def changeminext(self):
        u'''
        Called when minimal extension value is changed
        '''
        self.data.rpmod.setMinExt(float(self.txt_inputs["minext"].value))
        fixed =  {} if self.data.rpfulldata is None\
                 else self.data.rpfulldata.getFixedBeadIds()
        self.divs["fixed"].update(str(fixed))

    def change_data_file(self):
        u'''
        called when User selects a new file
        '''
        file_diag = view.dialog.FileDialog(filetypes = "trk", title = "please choose a ramp file")
        self.filename = file_diag.open()
        self.divs["filestatus"].update("Loading new file..")
        self._update_rpdata_from_file(self.filename)
        self._update_text_info()
        self._update_zmag_info()
        self._update_HP_info()
        self.divs["filestatus"].update("New file loaded!")

    def generate_rpdiscard(self):
        u'''
        Generates the ramp_discard.csv file for pias input
        '''
        beads = {"Too noisy":self.data.rpfulldata.noBeadCrossIds(),
                 "Fixed":self.data.rpfulldata.getFixedBeadIds(),
                 "HP not closing at the test force":\
                 utils.get_beadids_not_closing(self.data.rpdata,self.data.rpmod.get_zclthreshold())}
        # add "HP not closing at the test force" key values
        _gen_ramp_discard(beads,os.path.basename(self.filename))

    @classmethod
    def open(cls,doc):
        u'''
        returns a bokeh doc view a set up layout
        '''
        self = cls(doc = doc)
        return self.doc

    def _update_rpdata_from_file(self,filename:str)->None:
        self.data.rpdata.setTrack(filename)
        self.data.rpdata.clean()
        self.data.rpfulldata.setTrack(filename)


    def _update_text_info(self):
        good = {} if self.data.rpfulldata is None\
                  else self.data.rpfulldata.getGoodBeadIds()
        ugly = {} if self.data.rpfulldata is None\
               else self.data.rpfulldata.noBeadCrossIds()
        fixed =  {} if self.data.rpfulldata is None\
                 else self.data.rpfulldata.getFixedBeadIds()
        self.divs["ngoods"].update(str(len(good)))
        self.divs["good"].update(str(good))
        self.divs["ugly"].update(str(ugly))
        self.divs["fixed"].update(str(fixed))


    def _update_zmag_info(self):
        zmagop = pd.DataFrame() if self.data.rpdata is \
                 None else self.data.rpdata.zmagOpen()
        zmagcl = pd.DataFrame() if self.data.rpdata is \
                 None else self.data.rpdata.zmagClose()

        rzmagcl = pd.DataFrame() if self.data.rpdata is \
                  None else self.data.rpdata.zmagClose(reverse_time=True)

        self.hists["zmop"].update(zmagop.values.flatten())

        self.hists["zmcl"].update(zmagcl.values.flatten())

        self.hists["zmcl_reverse"].update(rzmagcl.values.flatten())

    def _update_HP_info(self):
        hp_est = pd.DataFrame() if self.data.rpdata is \
                 None else self.data.rpdata.estHPsize()
        self.hists["HPsize"].update(hp_est.values.flatten())



def _gen_ramp_discard(beads:dict,rpfile):
    u'''
    outputs a csv with the same format as ramp_discard.csv
    '''
    with open("ramp_discarded.csv","w") as outfile:
        outfile.write("Bead Id;\tPath;\tReason\n")
        for key,values in beads.items():
            for value in values:
                outfile.write(str(value)+";\t"+rpfile+";\t"+str(key)+"\n")

    outfile.close()

if __name__=="__main__":
    # should move this to unit test
    BOKEHDOC = MyDisplay().open(curdoc())
    ROWS = MyDisplay(doc = curdoc()).get_layout()
    curdoc().add_root(column(*ROWS))
    RPDATA = Data()
    RPDATA.update_data("/home/david/work/trackanalysis/tests/testdata/ramp_5HPs_mix.trk")
    DISPLAY = MyDisplay(data = RPDATA, doc = curdoc())
    ROWS = DISPLAY.get_layout()
