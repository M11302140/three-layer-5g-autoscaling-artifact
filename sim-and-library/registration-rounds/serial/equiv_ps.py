#!/usr/bin/env python3
"""P1 (setting None) of serial/ps.run == frozen v8sim11.run for all seven arms on t3/t4/t6/t7/t8 (slo, viol, alloc_vm, events)."""
import sys, json; Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/serial')
import v8sim11 as V, ps as P
E='/home/user/experiment'; ok=True; n=0
f=lambda r:(r['slo'],r['viol'],r['alloc_vm'],r['events'])
for tn in ('t3','t4','t6','t7','t8'):
    ue=json.load(open(f"{E}/trace_ue_60min_v3_{tn}.json"))["ue"][:60]
    for arm in ('S4a','S4b','v6','B4c2','B5c1','B6','B1'):
        s=f(V.run(ue,arm))==f(P.run(ue,arm,None)); ok&=s; n+=1
        if not s: print("MISMATCH",tn,arm)
print(f"P1 vs frozen v8sim11: {n} cases -> {'IDENTICAL' if ok else 'MISMATCH'}"); sys.exit(0 if ok else 2)
