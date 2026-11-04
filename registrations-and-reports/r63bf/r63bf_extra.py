#!/usr/bin/env python3
"""r63bf extra: B2 sensitivity (VyOS cap 16 / 16.55 / 18 = v8sim11 vy_knee; ready<=2*worker check) and F-Minor4 p99 distribution detail.
Reads results.json (from r63bf.py) + the same per-minute CSVs; read-only."""
import json, csv, collections, math
R = json.load(open('/home/user/experiment/qsim/r63bf/results.json')); P = '/home/user/experiment/p2'
mins = R['B2_minutes']
def classify(x, capvy, use_up=True, use_vy=True):
    up = use_up and x['ready_slots'] * 5 < x['target']; vy = use_vy and x['vyos_n'] * capvy < x['target']
    wk = x['worker_n'] * 2 < math.ceil(x['target'] / 5)
    return 'fleet' if (up or vy or wk) else ('placement' if x['old'] in ('capacity', 'tail', 'type2') else 'other')
for lab, kw in [('capVY16', dict(capvy=16)), ('capVY16.55', dict(capvy=4.45e6 * 0.93 / 250e3)), ('capVY18(vy_knee)', dict(capvy=18)),
                ('slot-only', dict(capvy=16, use_vy=False)), ('VY-only', dict(capvy=16, use_up=False))]:
    c = collections.defaultdict(collections.Counter)
    for x in mins: k = classify(x, **kw); c[x['block']][k] += 1; c['all'][k] += 1
    print(lab, {b: dict(c[b]) for b in ('t3', 't4', 't6', 't7', 'all')})
print('ready <= 2*worker_n holds in all violating minutes:', all(x['ready_slots'] <= 2 * x['worker_n'] for x in mins))
# per-arm table for all violating minutes
arm = collections.defaultdict(collections.Counter)
for x in mins: arm[(x['block'], x['arm'])][x['new']] += 1
for k in sorted(arm): print('arm', k, dict(arm[k]))
# F-Minor4 detail: p99 histogram near threshold, list of p99-only violators and of 900-1100 minutes
VOID = {'r302', 'r304', 'r307', 'r309', 'r368', 'r370', 'r376', 'r379'}
led = {}
for l in open(f'{P}/main_exp_ledger.tsv'):
    if not l.startswith('r') or l.count('\t') < 5: continue
    f = l.rstrip('\n').split('\t'); led[f[0]] = f
runs = [r for r, f in led.items() if f[1] in ('t3', 't4', 't5', 't6', 't7') and r not in VOID and not f[5].lower().startswith(('void', 'trial')) and f[5] != 'no-finish']
bins = [(0, 500), (500, 800), (800, 900), (900, 1000), (1000, 1100), (1100, 2000), (2000, 3000), (3000, 1e9)]
h = collections.defaultdict(collections.Counter); lst = []; above = []; nlat0 = 0; maxbelow = 0; minabove = 1e9
for run in runs:
    blk = led[run][1]
    for r in csv.DictReader(open(f'{P}/trace_v7_{run}.csv')):
        p99 = float(r['lat_p99_us'] or 0); loss = float(r['e2e_pct'] or 0)
        if int(r['lat_n'] or 0) == 0: nlat0 += 1
        for a, b in bins:
            if a <= p99 < b: h[blk][f'[{a},{int(b) if b < 1e9 else "inf"})'] += 1; h['all'][f'[{a},{int(b) if b < 1e9 else "inf"})'] += 1
        if 900 <= p99 <= 1100: lst.append((blk, run, led[run][2], r['min'], p99, loss))
        if p99 > 1000 and loss <= 0.1: above.append((blk, run, led[run][2], r['min'], p99, loss))
        if p99 <= 1000: maxbelow = max(maxbelow, p99)
        else: minabove = min(minabove, p99)
for b in ('t3', 't4', 't5', 't6', 't7', 'all'): print('p99 hist', b, dict(h[b]))
print('minutes with lat_n == 0:', nlat0, '| max p99 <= 1000:', maxbelow, '| min p99 > 1000:', minabove)
print('p99 in [900,1100]:', lst)
print('violating on p99 alone (p99>1000, loss<=0.1):', above)
