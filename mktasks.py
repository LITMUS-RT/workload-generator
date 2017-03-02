#!/usr/bin/env python

from __future__ import division

import argparse
import sys

from math import ceil

from os.path import exists, dirname
from os import makedirs

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
    return True if sol else False


def make_taskset(n, u, min_wcet=500):
    ts = emstada.gen_taskset('uni-broad', 'logunif', n, u,
            period_granularity=1, want_integral=True, scale=ms2us)

    for t in ts:
        while t.cost < min_wcet:
            t.cost *= 2
            t.period *= 2
            t.deadline *= 2

    return ts

def three_level_affinities(m, num_sockets):
    per_socket = int(ceil(m / num_sockets))
    all_cores = frozenset(range(0, m))

    sockets = []
    for i in range(0, num_sockets):
        s = range(i * per_socket, (i + 1) * per_socket)
        # check for last incomplete socket
        while s[-1] >= m:
            del s[-1]
        sockets.append(frozenset(s))
    parts = [frozenset([x]) for x in all_cores]
    return ([all_cores], sockets, parts)


def assign_three_level_affinities(ts, m, sockets, max_tries=10):
    affinities = three_level_affinities(m, sockets)

    # initially global
    for t in ts:
        t.affinity = affinities[0][0]

    assert is_feasible(ts)

    for t in ts:
        attempts = 1
        while True:
            attempts += 1
            group = random.choice(affinities)
            t.affinity = random.choice(group)
            if is_feasible(ts):
                break
            if attempts >= max_tries:
                # restore global
                t.affinity = affinities[0][0]
                break

def all_possible_affinities(m):
    all_cores = frozenset(range(0, m))
    to_look_at = [all_cores]
    while to_look_at:
        aff = to_look_at.pop()
        yield aff
        if len(aff) > 1:
            # can be subdivided
            mid = sorted(aff)[len(aff) // 2]
            left  = frozenset([x for x in aff if x < mid])
            right = frozenset([x for x in aff if x >= mid])
            to_look_at.append(left)
            to_look_at.append(right)

def assign_random_laminar_affinities(ts, m, max_tries=10):
    all_picks = list(all_possible_affinities(m))

    # initially global
    for t in ts:
        t.affinity = all_picks[0]

    assert is_feasible(ts)

    for t in ts:
        attempts = 1
        while True:
            attempts += 1
            t.affinity = random.choice(all_picks)
            if is_feasible(ts):
                break
            if attempts >= max_tries:
                # restore global
                t.affinity = all_picks[0]
                break

def assign_random_priorities(ts):
    "assign random priorities"
    prios = range(1, len(ts) + 1)
    random.shuffle(prios)
    for (t, p) in zip(ts, prios):
        t.priority = p
    ts.assign_ids()

def assign_rm_priorities(ts):
    "assign rate-monotomic priorities"
    ts.assign_ids_by_period()
    for t in ts:
        t.priority = t.id

def assign_arm_priorities(ts):
    "assign affinity- and rate-monotonic priorities"
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
            'priority' : t.priority,
        }
    data = {
        'tasks' : tsks,
    }
    return json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))

def store_random_taskset(m, n, u, seq, prefix=''):
    print "[random laminar APAs, %d cores, %.2f utilization, and %d tasks per core]" \
             % (m, u, n)
    ts = make_taskset(n, u * m)
    assign_random_laminar_affinities(ts, m)
    assign_arm_priorities(ts)
    fname = "%sapa-r-workload_m=%02d_n=%02d_u=%2d_seq=%02d.json" % \
        (prefix, m, n, int(100 * u), seq)
    print '=>', fname
    f  = open(fname, 'w')
    f.write(to_json(ts))
    f.close()

def store_partitioned_taskset(m, n, u, seq, prefix=''):
    print "[partitioned, %d cores, %.2f utilization, and %d tasks per core]" \
         % (m, u, n)
    ts = TaskSystem()
    for core in xrange(m):
        per_core = make_taskset(n, u)
        for t in per_core:
            t.partition = core
            t.affinity = set([core])
        ts += per_core

    assign_rm_priorities(ts)
    fname = "%spart-workload_m=%02d_n=%02d_u=%2d_seq=%02d.json" % \
        (prefix, m, n * m, int(100 * u), seq)
    print '=>', fname
    f  = open(fname, 'w')
    f.write(to_json(ts))
    f.close()

def store_socket_taskset(m, sockets, n, u, seq, prefix=''):
    print "[socket-aware laminar APAs, %d cores, %d sockets, %.2f utilization, and %d tasks per core]" \
         % (m, sockets, u, n)
    fname = "%sapa-s-workload_m=%02d_s=%02d_n=%02d_u=%2d_seq=%02d.json" % \
        (prefix, m, sockets, n, int(100 * u), seq)
    if exists(fname):
        print 'Skipping %s; exists already.' % fname
        return
    ts = make_taskset(n, u)
    assign_three_level_affinities(ts, m, sockets)
    assign_rm_priorities(ts)
    fname = "%sapa-workload_m=%02d_n=%02d_u=%2d_seq=%02d.json" % \
        (prefix, m, n, int(100 * u), seq)
    print '=>', fname
    f  = open(fname, 'w')
    f.write(to_json(ts))
    f.close()


def parse_args():
    p = argparse.ArgumentParser(
        description='LITMUS^RT workload generator')

    p.add_argument(
        '--prefix', type=str, dest='prefix', default='',
        help='Prefix for the generated file[s]')

    p.add_argument(
        '-m', '--num-cores', type=int, nargs='*', dest='ncores', default=[],
        help='processor counts to consider [multiple possible]')
    p.add_argument(
        '-s', '--num-sockets', type=int, nargs='*', dest='nsockets', default=[1],
        help='socket counts to consider [multiple possible]')
    p.add_argument(
        '-n', '--tasks-per-core', type=int, nargs='*', dest='ntasks', default=[5],
        help='task counts to consider [multiple possible]')
    p.add_argument(
        '-u', '--per-core-utilization', type=float, nargs='*', dest='utils',
        default=[0.5],
        help='processor utilizations to consider [multiple possible]')

    p.add_argument(
        '--apa', type=str, choices=['partitioned', 'random', 'socket'],
            dest='apa_type', default='partitioned',
        help='what sort of affinities to generate [default: partitioned]')

    p.add_argument(
        '-c', '--count', type=int, dest='count', default=1,
        help='how many task sets per #cores, #tasks, and util')

    return p.parse_args()

def main(args=sys.argv[1:]):
    options = parse_args()

    prefix_dir = dirname(options.prefix)
    if prefix_dir and not exists(prefix_dir):
        makedirs(prefix_dir)

    for m in options.ncores:
        for n in options.ntasks:
            for u in options.utils:
                for seq in xrange(options.count):
                    if options.apa_type == 'partitioned':
                        store_partitioned_taskset(m, n, u, seq,
                            prefix=options.prefix)
                    elif options.apa_type == 'random':
                        store_random_taskset(m, n, u, seq,
                            prefix=options.prefix)
                    elif options.apa_type == 'socket':
                        for s in options.nsockets:
                            store_socket_taskset(m, s, n, u, seq,
                                prefix=options.prefix)
                    else:
                        assert False

if __name__ == '__main__':
    main()
