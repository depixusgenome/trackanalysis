#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Class for tagging tracks, beads ..."
from enum   import Enum, unique
from typing import Dict, Set
from utils  import toenum
from .base  import Task, Level

@unique
class TagAction(Enum):
    "type of actions to perform on selected tags"
    none    = 0
    keep    = 1
    remove  = 2

class TaggingTask(Task):
    "Class for tagging tracks, beads ..."
    none    = TagAction.none
    keep    = TagAction.keep
    remove  = TagAction.remove

    def __init__(self, level:Level, **kw) -> None:
        super().__init__(level = level)
        self.tags:      Dict[str,Set[int]] = dict(kw.get('tags', []))
        self.selection: Set                = set (kw.get('tags', []))
        self.action:    TagAction          = toenum(TagAction, kw.get('action', 'none'))

    def selected(self, item) -> bool:
        "Returns whether an item is selected"
        if self.action is TagAction.none:
            return False

        return any(item.id in self.tags[tag] for tag in self.selection & set(self.tags))

    def process(self, item) -> bool:
        "Returns whether an item is kept"
        if self.action is TagAction.none:
            return True

        return self.selected(item) == (self.action == TagAction.keep)

    def clean(self):
        "Removes tags not in the parent"
        self.selection &= set(self.tags)
