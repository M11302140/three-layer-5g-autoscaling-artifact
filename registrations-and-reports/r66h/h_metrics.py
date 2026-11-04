# spec §4.116 H judgement: B6 offline same-target knob (u=0.775) vs S4b on t3/t6; per-run metrics via rq_metrics.py functions (unchanged); does not touch rq_metrics.csv.
import csv
src=open('/home/user/experiment/paper_out_new/rq_metrics.py').read(); src=src[:src.index('GROUPS=[')]
g={}; exec(src,g)
TR={'t3':'trace_ue_60min_v3_t3.json','t6':'trace_ue_60min_v3_t6.json'}
H={'t3':['r493','r495'],'t6':['r498','r499']}   # 10-25 rerun (r34b)
S4B={'t3':(4.67,1137.0),'t6':(0.0,1390.3)}          # S4b 3-run means (rq_metrics.csv)
B6DEP={'t3':(3.33,1227.7),'t6':(0.0,1447.3)}        # deployed B6 u=0.70 3-run means
PRED={'t3':(3,1173,5,1175),'t6':(0,1435,0,1431)}    # sim_b6 viol/alloc(dispatch), v8sim11 viol/alloc_vm (v8_predict_h_2026-10-24.txt)
rows=[]
for t,rs in H.items():
    ms=[g['metrics'](r,TR[t]) for r in rs]
    viol=sum(60-m['slo'] for m in ms)/len(ms); av=sum(m['alloc_vm'] for m in ms)/len(ms); bu=sum(m['burned'] for m in ms)/len(ms)
    sv,sa=S4B[t]; dcost=100*(av/sa-1); dviol=viol-sv
    verdict='(a) same cost level' if abs(dcost)<=2 and abs(dviol)<=2 else ('(b) S4b cheaper' if dcost>2 else '(c) baseline cheaper')
    rows.append((t,[(r,m['slo'],m['alloc_vm'],m['burned']) for r,m in zip(rs,ms)],viol,av,bu,sv,sa,dcost,dviol,verdict))
print('| trace | runs (SLO/alloc_vm/burned) | H viol/run | H alloc_vm | S4b viol/run | S4b alloc_vm | Δcost | Δviol | verdict | B6 deployed | prediction sim_b6 / v8sim11 |\n|---|---|---|---|---|---|---|---|---|---|---|')
for t,per,viol,av,bu,sv,sa,dc,dv,vd in rows:
    print(f'| {t} | {per} | {viol:.2f} | {av:.1f} | {sv:.2f} | {sa:.1f} | {dc:+.2f}% | {dv:+.2f} | {vd} | {B6DEP[t][0]:.2f} @ {B6DEP[t][1]:.1f} | {PRED[t][0]} @ {PRED[t][1]} / {PRED[t][2]} @ {PRED[t][3]} |')
