#!/usr/bin/env python3
"""r63bf (spec §4.107 B, C, D, E, F-Minor4): log/CSV analysis only, read-only on all inputs.
Run: cd /home/user/experiment/qsim/r63bf && nice -n 19 taskset -c 13 python3 r63bf.py > r63bf_out.txt
Writes results.json next to this script."""
import sys, csv, re, json, math, collections, statistics as st
sys.path.insert(0, '/home/user/experiment/p2')
import classify_minutes as cm
P = '/home/user/experiment/p2'; Q = '/home/user/experiment/qsim'
RQ = '/home/user/experiment/paper_out_new/rq/rq_metrics.csv'
OPS = '/home/user/experiment/paper_out_new/ops/ops_per_run.csv'
OUT = {}

# ---------------- B1 risk fidelity ----------------
reg = {}
for l in open(f'{Q}/v8_predict_t345_2026-10-07.txt'):
    m = re.match(r'\s*(S4a|S4b)\s+(t\d)\s+\d+\s+(\d+)/60', l)
    if m: reg[(m[2], m[1])] = 60 - int(m[3])
for l in open(f'{Q}/v8_predict_v6_t345_2026-10-07.txt'):
    m = re.match(r"\s*v6\s+(t\d)\s+peakUE\s+\d+\s+\{'slo': (\d+)", l)
    if m: reg[(m[1], 'v6')] = 60 - int(m[2])
for l in open(f'{Q}/v8_predict_t67_2026-10-15.txt'):
    m = re.match(r'\s*(S4a|S4b|v6)\s+(t\d)\s+(\d+)/60', l)
    if m: reg[(m[2], m[1])] = 60 - int(m[3])
v11 = {}
for l in open(f'{Q}/m1/REPORT.md'):
    m = re.match(r'\| (t\d) \| (S4a|S4b|v6) \| D\d+ \| [^|]+\| [^|]+\| (\d+); ', l)
    if m: v11[(m[1], m[2])] = int(m[3])
rq = list(csv.DictReader(open(RQ)))
def grp(name): return [r for r in rq if r['group'] == name]
meas = {}
GN = {'S4a': 'S4a', 'S4b': 'S4b', 'v6': 'v6'}
for t in ('t3', 't4', 't6', 't7'):
    for a in ('S4a', 'S4b', 'v6'):
        rows = grp(f'MAIN {t} {a}')
        meas[(t, a)] = (sum(60 - int(r['slo']) for r in rows), len(rows), [r['run'] for r in rows])
def ratio(a, b):
    if b == 0: return 'n/a' if a == 0 else '∞'
    return f'{a / b:.2f}'
b1 = []
for t in ('t3', 't4', 't6', 't7'):
    for a in ('S4a', 'S4b', 'v6'):
        tot, n, runs = meas[(t, a)]; mm = tot / n
        b1.append(dict(trace=t, arm=a, registered=reg[(t, a)], v8sim11=v11[(t, a)], meas_total=tot, n=n, runs=runs, measured=round(mm, 2),
                       reg_over_meas=ratio(reg[(t, a)], mm), v11_over_meas=ratio(v11[(t, a)], mm),
                       meas_over_reg=ratio(mm, reg[(t, a)]), meas_over_v11=ratio(mm, v11[(t, a)])))
r381 = grp('MAIN t4 v6 confirm post-IRQ')
OUT['B1'] = b1; OUT['B1_r381'] = [(r['run'], r['slo']) for r in r381]
print('== B1'); [print(x) for x in b1]; print('r381', OUT['B1_r381'])

# ---------------- B2 reclassification (run selection + old class = cross_residual.py verbatim) ----------------
VOID = {'r302', 'r304', 'r307', 'r309', 'r368', 'r370', 'r376', 'r379'}
led = {}
for l in open(f'{P}/main_exp_ledger.tsv'):
    if not l.startswith('r') or l.count('\t') < 5: continue
    f = l.rstrip('\n').split('\t'); led[f[0]] = f
runs = [r for r, f in led.items() if f[1] in ('t3', 't4', 't5', 't6', 't7') and r not in VOID and not f[5].lower().startswith(('void', 'trial')) and f[5] != 'no-finish']
runs = sorted(runs, key=lambda r: int(r[1:]))
slots = ['38', '31', '32', '33', '34', '35', '36', '37']
CAPUP, CAPVY, SPW = 5, 16, 2
mins = []; f4 = collections.defaultdict(collections.Counter); nruns = collections.Counter(); covbad = 0
for run in runs:
    blk, arm = led[run][1], led[run][2]; nruns[blk] += 1
    rows = list(csv.DictReader(open(f'{P}/trace_v7_{run}.csv'))); ends = cm.minute_ends(run); ds = cm.dists(run)
    prev_cap_slot = None; prev_min = None
    for r in rows:
        m = int(r['min']); loss = float(r['e2e_pct'] or 0); p99 = float(r['lat_p99_us'] or 0)
        # F-Minor4 counts over every scored minute
        f4[blk]['minutes'] += 1
        if 900 <= p99 <= 1100:
            f4[blk]['p99_900_1100'] += 1
            if loss > 0.1 or p99 > 1000: f4[blk]['p99_900_1100_viol'] += 1
            if p99 > 1000 and loss <= 0.1: f4[blk]['p99_900_1100_viol_p99_only'] += 1
            if p99 > 1000 and loss > 0.1: f4[blk]['p99_900_1100_viol_both'] += 1
            if p99 <= 1000 and loss > 0.1: f4[blk]['p99_900_1100_viol_loss_only'] += 1
        if 900 <= p99 < 1000:
            f4[blk]['p99_900_1000'] += 1
            if loss <= 0.1: f4[blk]['p99_900_1000_pass'] += 1
        if 1000 < p99 <= 1100: f4[blk]['p99_1000_1100'] += 1
        if p99 > 1000: f4[blk]['p99_gt_1000'] += 1
        if p99 > 1000 and loss <= 0.1: f4[blk]['viol_p99_only_all'] += 1
        if loss <= 0.1 and p99 <= 1000: continue
        oob = {s: float(r.get(f'slot_oob_{s}') or 0) for s in slots}; t = sum(oob.values()); top = max(oob, key=oob.get)
        te = ends.get(m); vue = cm.victim_ue(ds, te - 60, te, top) if te else None
        if t < 50000: cls = 'non-slot'; cap_slot = None
        elif vue is None: cls = 'nodist'; cap_slot = None
        elif vue >= 5: cls = 'capacity'; cap_slot = top
        elif prev_min == m - 1 and prev_cap_slot == top: cls = 'tail'; cap_slot = top
        else: cls = 'type2'; cap_slot = None
        prev_cap_slot = cap_slot; prev_min = m
        # fleet check
        cov = r['eupf_cov']; mm_ = re.match(r'(\d+)/(\d+)', cov or '')
        ready = int(mm_[1]) if mm_ else None
        if ready is None: covbad += 1
        tgt = int(r['target_ue']); act = int(r['active_ue']); vyn = int(r['vyos_n']); wkn = int(r['worker_n'])
        need_slots = math.ceil(tgt / CAPUP)
        sh_up = ready is not None and ready * CAPUP < tgt
        sh_vy = vyn * CAPVY < tgt
        sh_vy_exact = vyn * 4.45e6 * 0.93 / 250e3 < tgt
        sh_wk = wkn * SPW < need_slots
        sh_up_act = ready is not None and ready * CAPUP < act
        sh_vy_act = vyn * CAPVY < act
        newc = 'fleet' if (sh_up or sh_vy or sh_wk) else ('placement' if cls in ('capacity', 'tail', 'type2') else 'other')
        newc_act = 'fleet' if (sh_up_act or sh_vy_act or wkn * SPW < math.ceil(act / CAPUP)) else ('placement' if cls in ('capacity', 'tail', 'type2') else 'other')
        mins.append(dict(run=run, block=blk, arm=arm, min=m, old=cls, slot=top, vue=vue, loss=loss, p99=p99, target=tgt, active=act,
                         ready_slots=ready, eupf_cov=cov, vyos_n=vyn, worker_n=wkn, sh_up=sh_up, sh_vy=sh_vy, sh_vy_exact=sh_vy_exact, sh_wk=sh_wk,
                         new=newc, new_active=newc_act))
print('== B2 n_runs', sum(nruns.values()), dict(nruns), 'violating minutes', len(mins), 'eupf_cov unparsable', covbad)
OUT['B2_minutes'] = mins; OUT['nruns'] = dict(nruns)
tab = collections.defaultdict(collections.Counter)
for x in mins: tab[x['block']][x['new']] += 1; tab['all'][x['new']] += 1
for b in ('t3', 't4', 't5', 't6', 't7', 'all'): print(b, dict(tab[b]), sum(tab[b].values()))
xt = collections.Counter((x['old'], x['new']) for x in mins); print('old x new', dict(xt))
lay = collections.Counter((x['sh_up'], x['sh_vy'], x['sh_wk']) for x in mins if x['new'] == 'fleet'); print('fleet layers (up,vy,wk)', dict(lay))
print('wk shortage without slot shortage:', sum(1 for x in mins if x['sh_wk'] and not x['sh_up']))
print('vy exact-cap 16.55 differs from 16:', [(x['run'], x['min'], x['vyos_n'], x['target']) for x in mins if x['sh_vy'] != x['sh_vy_exact']])
tabA = collections.defaultdict(collections.Counter)
for x in mins: tabA[x['block']][x['new_active']] += 1; tabA['all'][x['new_active']] += 1
print('sensitivity active_ue:', {b: dict(tabA[b]) for b in tabA})
arm_tab = collections.defaultdict(collections.Counter)
for x in mins: arm_tab[(x['block'], x['arm'])][x['new']] += 1
OUT['B2_table'] = {b: dict(v) for b, v in tab.items()}; OUT['B2_table_active'] = {b: dict(v) for b, v in tabA.items()}
OUT['B2_by_arm'] = {f'{k[0]} {k[1]}': dict(v) for k, v in arm_tab.items()}
OUT['B2_crosstab'] = {f'{k[0]}->{k[1]}': v for k, v in xt.items()}
print('== fleet minutes detail')
for x in mins:
    if x['new'] == 'fleet': print(' ', x['run'], x['block'], x['arm'], 'min', x['min'], x['old'], 'tgt', x['target'], 'act', x['active'], 'cov', x['eupf_cov'], 'vy', x['vyos_n'], 'wk', x['worker_n'], 'up/vy/wk', x['sh_up'], x['sh_vy'], x['sh_wk'])

# ---------------- C burned / ops ----------------
ARMS = [('S4a', 'S4a'), ('S4b', 'S4b'), ('v6', 'v6'), ('B4c2', 'B4c2'), ('B5c1', 'B5c1 (q11)'), ('B6', 'B6 u=0.70'), ('B1', 'B1')]
ops = list(csv.DictReader(open(OPS)))
C = []
for t in ('t6', 't7'):
    for a, g in ARMS:
        rows = grp(f'MAIN {t} {g}'); rr = [r['run'] for r in rows]
        orow = [o for o in ops if o['run'] in rr]
        mean = lambda k, R=rows: st.mean(float(r[k]) for r in R)
        om = lambda k: st.mean(float(o[k]) for o in orow) if orow else float('nan')
        C.append(dict(trace=t, arm=a, n=len(rows), runs=rr, burned=round(mean('burned'), 1), burned_runs=[int(r['burned']) for r in rows],
                      burned_wk=round(mean('burned_wk'), 1), burned_vy=round(mean('burned_vy'), 1), alloc_vm=round(mean('alloc_vm'), 1),
                      viol_min=sum(60 - int(r['slo']) for r in rows), n_ops=len(orow), drain_moves=round(om('drain_moves'), 2),
                      relief_moves=round(om('relief_moves'), 2), hotslot_moves=round(om('hotslot_moves'), 2),
                      drains=round(om('drains'), 2), relief_calls=round(om('relief_calls'), 2) if orow else None))
OUT['C'] = C
print('== C'); [print(x) for x in C]

# ---------------- D: calibration runtimes from logs ----------------
def last_bracket_s(path):
    v = [int(x) for x in re.findall(r'\[(\d+)s\]', open(path).read())]; return v
D = {}
for f in ('v8sim10_CAL_2026-10-05.txt', 'v8sim10_CAL_nosensor_2026-10-10.txt', 'v8sim10_FULL_2026-10-06.txt'):
    v = last_bracket_s(f'{Q}/{f}'); D[f] = dict(n_stamps=len(v), last_s=v[-1] if v else None)
txt = open(f'{Q}/v8sim10_FULL_2026-10-06.txt').read()
a_part = [int(x) for x in re.findall(r'split\d: λ [^\n]*\[(\d+)s\]', txt)]
D['FULL_part_a_6split_s'] = a_part[-1] if a_part else None
ab = open(f'{Q}/abl/progress.log').read()
D['abl_header'] = re.search(r'=== ablation start: ([^\n]*)', ab)[1]; D['abl_done'] = re.search(r'=== DONE ([^\n]*)', ab)[1]
etimes = re.findall(r'\(e\) full\s+target [^\n]*\[(\d+)s, total (\d+)s\]', ab); D['abl_e_split_s'] = [int(a) for a, b in etimes]
cp = [l for l in open(f'{Q}/r62cf/calib_progress.log')]
ph = []
for l in cp:
    m = re.match(r'\[(\d\d):(\d\d):(\d\d) \+\s*(\d+)s\] === phase (\S+)', l)
    if m: ph.append((m[5], int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])))
m = re.match(r'\[(\d\d):(\d\d):(\d\d)', [l for l in cp if l.rstrip().endswith('done')][-1]); tend = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
dur = collections.Counter()
for i, (p, t0) in enumerate(ph):
    t1 = ph[i + 1][1] if i + 1 < len(ph) else tend; dur[p] += t1 - t0
D['r62cf_phase_s'] = dict(dur); D['r62cf_total_s'] = tend - ph[0][1]
OUT['D'] = D; print('== D', json.dumps(D, ensure_ascii=False, indent=1))
hh = [r for r in rq if re.match(r'HHRO t[12]$', r['group'])]; OUT['D_v6_groups'] = [(r['group'], r['run']) for r in hh]
n_sep = sum(1 for i in range(1, 120) if __import__('os').path.exists(f'{P}/trace_v7_r{i}.csv')); OUT['D_v6_csv_r1_r119'] = n_sep
print('v6 formal groups', OUT['D_v6_groups'], 'trace_v7_rN.csv N<=119:', n_sep)

# ---------------- E: leads ----------------
E = json.load(open(f'{Q}/r62de/E_leads.json'))
OUT['E'] = {'primary': E['primary'], 'inflight': E['inflight']}
print('== E'); print(json.dumps(OUT['E'], indent=1))

# ---------------- F-Minor4 ----------------
OUT['F4'] = {b: dict(v) for b, v in f4.items()}
tot = collections.Counter()
for b in f4: tot.update(f4[b])
OUT['F4']['all'] = dict(tot)
print('== F4'); [print(b, OUT['F4'][b]) for b in ('t3', 't4', 't5', 't6', 't7', 'all')]
json.dump(OUT, open('/home/user/experiment/qsim/r63bf/results.json', 'w'), indent=1, ensure_ascii=False, default=str)
