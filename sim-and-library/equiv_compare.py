#!/usr/bin/env python3
"""(docstring removed)"""
import sys, json, glob, os, collections
sys.path.insert(0,'/home/user/experiment/qsim'); import v8sim9 as Q, v8sim2 as S, v8sim7 as M, v8sim10 as Q2
lib=json.load(open('/home/user/experiment/qsim/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg)
ACT={('cancel-drain','up'):'CANCEL_DRAIN',('wait-position','up'):'SCALE_OUT_UP_NOPOS',('out','up'):'SCALE_OUT_UP',('in','up'):'SCALE_IN_UP',('out','vy'):'DEPLOY_VYOS',('in','vy'):'DELETE_VYOS',('out','wk'):'CREATE_WORKER',('in','wk'):'DELETE_WORKER',('blocked','up'):'SCALE_OUT_UP_NOPOS'}
D='/home/user/hhro-daemon/internal/hbo/testdata/equiv'
SIM=os.environ.get('EQUIV_SIM','nest2')
names=sys.argv[1:] or sorted(os.path.basename(p)[:-5] for p in glob.glob(f'{D}/*.json'))
for name in names:
    r=json.load(open(f'{D}/{name}.json')); grp,tn,tag=name.split('_',2)
    ue=Q.TR[tn];
    if tag.startswith('pps') and SIM!='nest2': ue=[u*0.993 for u in ue]
    ds=30 if '_d30' in tag else None
    LAMS=dict(Q.LAM); LAMS.update({'S4a':{'vy':2.83,'wk':2.83,'up':3.08},'S4b':{'vy':1.83,'wk':1.83,'up':2.00}})
    q=Q2.sim_nest2(ue,cfg,pr,LAMS[grp],drain_sec=ds) if SIM=='nest2' else Q.sim_nest_traj(ue,cfg,pr,LAMS[grp])
    qev=[(int(t)//60, ACT.get((a,k),a+':'+k)) for t,a,k in q['ev']]
    dev=[(int(e['t'])//60, e['act']) for e in r['events']]
    core=lambda evs: collections.Counter((m,a) for m,a in evs if a in ('SCALE_OUT_UP','SCALE_IN_UP','DEPLOY_VYOS','DELETE_VYOS','CREATE_WORKER','DELETE_WORKER','CREATE_WORKER*exec'))
    cq,cd=core(qev),core(dev)
    diff=sorted(set(cq)|set(cd), key=lambda k:(k[0],k[1]))
    nd=sum(1 for k in diff if cq.get(k,0)!=cd.get(k,0))
    print(f"=== {name}: qsim alloc {q['alloc']:.0f} SLO {q['slo']} | daemon alloc {r['alloc']:.0f} SLO {r['slo']} | acts qsim {sum(cq.values())} daemon {sum(cd.values())} | differing (min,act) cells {nd}")
    shown=0
    for k in diff:
        if cq.get(k,0)!=cd.get(k,0):
            print(f"   min{k[0]:2d} {k[1]:18s} qsim {cq.get(k,0)} daemon {cd.get(k,0)}")
            shown+=1
            if shown>=12: print("   ..."); break
    extra=[e for e in dev if e[1] not in ('SCALE_OUT_UP','SCALE_IN_UP','DEPLOY_VYOS','DELETE_VYOS','CREATE_WORKER','DELETE_WORKER')]
    if extra: print("   daemon non-core events:", extra[:10])
