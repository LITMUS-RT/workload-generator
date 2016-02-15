#!/usr/bin/env python

from __future__ import division

import random
import json

from schedcat.model.tasks import TaskSystem, SporadicTask
from schedcat.util.time import ms2us
from schedcat.sched import get_native_affinities, get_native_taskset
from schedcat.sched.native import apa_implicit_deadline_feasible
import schedcat.generator.generator_emstada as emstada

def is_feasible(taskset):
    aff = get_native_affinities(taskset)
    ts  = get_native_taskset(taskset)
    sol = apa_implicit_deadline_feasible(ts, aff)
    if sol:
        return True
    else:
        return False


def make_taskset(n, u, min_wcet=500):
    ts = emstada.gen_taskset('uni-broad', 'logunif', n, u,
            period_granularity=1, want_integral=True, scale=ms2us)

    for t in ts:
        while t.cost < min_wcet:
            t.cost *= 2
            t.period *= 2
            t.deadline *= 2

    return ts


def all_possible_affinities(m):
    all_cores = frozenset(range(1, m))
    to_look_at = [all_cores]
    while to_look_at:
        aff = to_look_at.pop()
        yield aff
        if len(aff) > 1:
            # can be subdivided
            mid = sorted(aff)[len(aff) // 2]
            left  = frozenset([x for x in aff if x < mid])
            right = frozenset([x for x in aff if x >= mid])
#            print aff, mid, left, right
            to_look_at.append(left)
            to_look_at.append(right)

def assign_random_laminar_affinities(ts, m, max_tries=10):
    all_picks = list(all_possible_affinities(m))

    print all_picks[0], ts.utilization()

    # initially global
    for t in ts:
        t.affinity = all_picks[0]

    assert is_feasible(ts)

    for t in ts:
        attempts = 1
        while True:
            attempts += 1
            t.affinity = random.choice(all_picks)
#             print t, 'trying', t.affinity
            if is_feasible(ts):
                break
            if attempts >= max_tries:
                # restore global
                t.affinity = all_picks[0]
                break

def assign_random_priorities(ts):
    prios = range(1, len(ts) + 1)
    random.shuffle(prios)
    for (t, p) in zip(ts, prios):
        t.priority = p
    ts.assign_ids()

def assign_rm_priorities(ts):
    ts.assign_ids_by_period()
    for t in ts:
        t.priority = t.id

def assign_arm_priorities(ts):
    for (t, i) in zip(sorted(ts, key=lambda t: (1/len(t.affinity), t.period)), range(1, len(ts) + 1)):
        t.priority = i
    ts.assign_ids()

def to_hex(affinity):
    hex = 0
    for cpu in affinity:
        hex |= (1 << cpu)
    return hex

def to_json(ts):
    tsks = {}
    for t in ts:
        tsks[t.id] = {
            'cost'     : t.cost,
            'period'   : t.period,
            'affinity' : list(t.affinity),
            'affinity_mask' : to_hex(t.affinity),
            'priority' : t.priority,
        }
    data = {
        'tasks' : tsks,
    }
    return json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))

def store_taskset(m, n, u, seq, prefix=''):
    print u * (m - 1)
    ts = make_taskset(n, u * (m - 1))
    assign_random_laminar_affinities(ts, m)
    assign_arm_priorities(ts)
    fname = "%sapa-workload_m=%02d_n=%02d_u=%2d_seq=%02d.json" % \
        (prefix, m, n, int(100 * u), seq)
    print fname
    f  = open(fname, 'w')
    f.write(to_json(ts))
    f.close()

for m in [4, 8, 48]:
    for n in set([m * 2, m * 4, m * 6, m * 8, m * 10]):
        for u in [0.75, 0.85, 0.95]:
            for seq in xrange(10):
                store_taskset(m, n, u, seq, prefix='tasksets/')
