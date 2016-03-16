#!/usr/bin/env python

from __future__ import division

APA_SCHEDULERS = frozenset([
    'LSA-FP-MP',
])

RESERVATION_SCHEDULERS = frozenset([
    'P-RES',
])

PARTITIONED_SCHEDULERS = frozenset([
    'P-RES',
    'PSN-EDF',
    'P-FP',
# not really partitioned, but can be used as such
    'C-EDF',
])

FIXED_PRIORITY_SCHEDULERS = frozenset([
    'P-FP',
    'LSA-FP-MP',
    'G-FP-MP',
])

MP_SCHEDULERS = frozenset([
    'LSA-FP-MP',
    'G-FP-MP',
    'G-EDF-MP',
])
