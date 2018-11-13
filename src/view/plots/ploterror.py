#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds titles to a plot for displaying errors"
from typing                 import Callable
from bokeh.models           import Title
from bokeh.plotting         import Figure
from cleaning.processor     import DataCleaningException
from .                      import CACHE_TYPE

class PlotError:
    "Adds titles to a plot for displaying errors"
    _fig: Figure
    _pos: str
    def __init__(self, fig, cnt, position = "above"):
        "adds the titles"
        self._fig = fig
        self._pos = position
        for _ in range(getattr(cnt, 'ntitles', cnt)):
            self._fig.add_layout(Title(), self._pos)

    def __call__(self, cache: CACHE_TYPE, creator: Callable, displayer: Callable):
        tmp = None
        try:
            tmp = creator()
        except Exception as exc: # pylint: disable=broad-except
            self.reset(cache, exc)
            raise
        else:
            self.reset(cache)
        finally:
            displayer(tmp)

    def reset(self, cache:CACHE_TYPE, label = None, hideothers = True):
        "sets titles"
        titles  = [i for i in self._fig.above if isinstance(i, Title)]
        if label:
            if isinstance(label, DataCleaningException):
                label = str(label.args[0])
            else:
                label = str(label)

            labels  = label.split("\n")[::-1]
            labels += [""]*(len(titles) - len(labels))

            for i, j in zip(titles, labels):
                cache[i]['text'] = j

            good = False
        else:
            good = True

        if hideothers:
            for i in self._fig.above:
                cache[i]['visible'] = (not good) if isinstance(i, Title) else good
        else:
            for i in titles:
                cache[i]['visible'] = not good
