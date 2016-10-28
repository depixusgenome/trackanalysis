#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"git extraction functions"
import os
import subprocess

def _cmd(*args) -> str:
    if any(os.path.exists('../'*i+'.git') for i in range(5)):
        return subprocess.check_output(('git',)+tuple(args)).strip().decode('utf-8')
    else:
        return ''

def version() -> str:
    u"returns last tag name"
    return _cmd('describe', '--dirty=+', '--always')

def lasthash() -> str:
    u"returns last commit hashtag"
    return _cmd('log', '-n', '1', '--pretty=format:%H')

def lastdate() -> str:
    u"returns last commit date"
    return _cmd('log', '-n', '1', '--pretty=format:%cD')

def lastauthor() -> str:
    u"returns last commit author"
    return _cmd('log', '-n', '1', '--pretty=format:%an')

def branch() -> str:
    u"returns current branch"
    return _cmd('rev-parse', '--abbrev-ref', 'HEAD')

def isdirty() -> bool:
    u"returns whether we're sitting in-between tags"
    return version()[-1] == '+'
