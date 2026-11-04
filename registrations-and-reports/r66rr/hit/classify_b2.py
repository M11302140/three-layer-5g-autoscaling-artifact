import sys, csv, re, math, collections
sys.path.insert(0,'/home/user/experiment/p2')
import classify_minutes as cm
P='/home/user/experiment/p2'
def classify(run):
    """verbatim minute classification of qsim/r66rr/b2/r63bf_rr.py (B2 rule); returns {minute: class}"""
    import collections
    _f4=collections.Counter(); out={}
    slots = ['38', '31', '32', '33', '34', '35', '36', '37']; CAPUP, CAPVY, SPW = 5, 16, 2
    prev_cap_slot = None; prev_min = None
    rows = list(csv.DictReader(open(f'{P}/trace_v7_{run}.csv'))); ends = cm.minute_ends(run); ds = cm.dists(run)
    prev_cap_slot = None; prev_min = None
    for r in rows:
        m = int(r['min']); loss = float(r['e2e_pct'] or 0); p99 = float(r['lat_p99_us'] or 0)
        # F-Minor4 counts over every scored minute
        _f4['minutes'] += 1
        if 900 <= p99 <= 1100:
            _f4['p99_900_1100'] += 1
            if loss > 0.1 or p99 > 1000: _f4['p99_900_1100_viol'] += 1
            if p99 > 1000 and loss <= 0.1: _f4['p99_900_1100_viol_p99_only'] += 1
            if p99 > 1000 and loss > 0.1: _f4['p99_900_1100_viol_both'] += 1
            if p99 <= 1000 and loss > 0.1: _f4['p99_900_1100_viol_loss_only'] += 1
        if 900 <= p99 < 1000:
            _f4['p99_900_1000'] += 1
            if loss <= 0.1: _f4['p99_900_1000_pass'] += 1
        if 1000 < p99 <= 1100: _f4['p99_1000_1100'] += 1
        if p99 > 1000: _f4['p99_gt_1000'] += 1
        if p99 > 1000 and loss <= 0.1: _f4['viol_p99_only_all'] += 1
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
        out[m]=newc
    return out
