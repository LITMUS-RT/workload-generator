#!/usr/bin/env python

from __future__ import division

from os.path import basename
from os import chmod

import random
import sys
import stat
import json

from config import *
from templates import *

def us2ms(x):
    return x / 1000

def generate_sh(name, data,
                duration=30,
                scale=0.95,
                scheduler='LSA-FP-MP',
                want_debug=False,
                want_overheads=False,
                want_schedule=False,
                default_wss=0,
                background_wss=0):
    fname = name + '.sh'
    f = open(fname, 'w')
    f.write(PREAMBLE.format(
        sched = scheduler,
        name = name,
        duration = duration
    ))
    f.write(SET_SCHEDULER.format(scheduler = 'Linux'))

    core = lambda n: '${CORE[%d]}' % n

    if scheduler in MP_SCHEDULERS:
        max_cpu = 0
        for t in data['tasks'].itervalues():
            max_cpu = max(max_cpu, max(t['affinity']))
        max_cpu += 1

        trace_affinity = SET_AFFINITY.format(core_list = core(max_cpu))
        f.write(SET_DSP.format(scheduling_core = core(max_cpu)))
    else:
        trace_affinity = ''

    f.write(SET_SCHEDULER.format(scheduler = scheduler))

    if background_wss > 0:
        f.write(BACKGROUND_WORKLOAD.format(wss_in_pages = background_wss))

    if want_debug:
        f.write(DEBUG_TRACE.format(
            name = fname,
            taskset = trace_affinity
        ))
    if want_overheads:
        f.write(OVERHEAD_TRACE.format(
            name = fname,
            taskset = trace_affinity
        ))
    if want_schedule:
        f.write(OVERHEAD_TRACE.format(
            name = fname,
            taskset = trace_affinity
        ))

    for id in data['tasks']:
        t = data['tasks'][id]
        if scheduler in APA_SCHEDULERS:
            core_list = ",".join([core(x) for x in t['affinity']])
            affinity = SET_AFFINITY.format(core_list = core_list)
        else:
            affinity = ''
        if scheduler in FIXED_PRIORITY_SCHEDULERS:
            prio = '-q %s' % t['priority']
        else:
            prio =''
        if scheduler in RESERVATION_SCHEDULERS:
            reservation = '-R'
        else:
            reservation = ''
        if scheduler in PARTITIONED_SCHEDULERS:
            partition = '-p %s' % core(random.choice(t['affinity']))
        else:
            partition = ''

        wss = default_wss
        if 'wss' in t:
            wss = t['wss']
        if wss:
            wss = '-m %s' % wss
        else:
            wss = ''

        f.write(RTSPIN.format(
            taskset       = affinity,
            prio          = prio,
            cost          = us2ms(t['cost']),
            period        = us2ms(t['period']),
            duration      = duration,
            scale         = scale,
            reservation   = reservation,
            partition     = partition,
            wss           = wss,
        ))
    f.write(MAIN_EXP.format(
        num_tasks = len(data['tasks']),
        duration  = duration,
    ))
    f.write(SET_SCHEDULER.format(scheduler = 'Linux'))
    f.close()
    chmod(fname, stat.S_IRGRP | stat.S_IROTH | stat.S_IRWXU)


def load_ts_from_json(fname):
    data = json.load(open(fname, 'r'))
    return data

def main(args=sys.argv[1:]):
    for fname in args:
        name = basename(fname).replace('.json', '')
        print 'Processing %s -> %s' % (fname, name + '.sh')
        ts = load_ts_from_json(fname)
                    duration=30, scheduler="G-FP-MP",
                    want_debug=False, want_overheads=True, want_schedule=False)
        generate_sh(name, ts,


if __name__ == '__main__':
    main()
