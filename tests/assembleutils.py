#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u''' scoring functions for assembly
'''

import scipy.stats as stats
from assemble import _utils as utils

def test_group_normdists():
    u'tests'
    dist1 = stats.norm(loc=0.0,scale=0.5)
    dist2 = stats.norm(loc=0.5,scale=0.5)
    dist3 = stats.norm(loc=1.0,scale=0.5)

    # tests on nscale
    assert {0,1} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=1)[1]
    assert {1,2} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=1)[1]
    assert not {0,1,2} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=1)[1]

    assert {0,1,2} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=1.1)[1]
    assert not {0,1} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=1.1) [1]
    assert not {1,2} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=1.1)[1]

    assert not {0,1,2} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=0.9)[1]
    assert {0,1} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=0.9) [1]
    assert {1,2} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=0.9)[1]

    dist1 = stats.norm(loc=0.0,scale=0.1)
    dist2 = stats.norm(loc=0.5,scale=0.5)
    dist3 = stats.norm(loc=1.0,scale=0.5)

    print(utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=0.9)[1])
    assert {0} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=0.9)[1]
    assert not {0,1} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=0.9) [1]
    assert not {0,2} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=0.9) [1]
    assert {1,2} in utils.group_overlapping_normdists(dists=[dist1,dist2,dist3],nscale=0.9)[1]
