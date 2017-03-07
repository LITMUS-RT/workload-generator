#!/usr/bin/env python

PARTITIONED_SCHEDULERS = frozenset([
    'PSN-EDF',
    'P-FP',
    'P-RES',
    'ESPRESSO',
])

RESERVATION_SCHEDULERS = frozenset([
    'P-RES',
    'ESPRESSO',
])

CLUSTERED_SCHEDULERS = frozenset([
    'C-EDF',
    'PFAIR',
])

APA_SCHEDULERS = frozenset([
    'LSA-FP-MP',
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
