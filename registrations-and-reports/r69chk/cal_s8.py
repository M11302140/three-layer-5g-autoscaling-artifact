#!/usr/bin/env python3
"""spec §4.137 item 3: nest2 six-split calibration of S8 = S4 (variant full) + R2 (w = 1600), using r68unif/cal.py's job unchanged
(ARMS replaced by S8 only). Output out/cal_s8.jsonl"""
import sys, os, json, time
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q+'/r68unif')
import cal as C
from concurrent.futures import ProcessPoolExecutor
C.ARMS.clear(); C.ARMS["S8"]=dict(variant="full",w=1600)
if __name__=="__main__":
    t0=time.time(); fn=f'{Q}/r69chk/out/cal_s8.jsonl'
    with ProcessPoolExecutor(2) as pool:
        for rows in pool.map(C.job,[("S8",s) for s in range(6)]):
            for r in rows:
                open(fn,"a").write(json.dumps(r)+"\n")
                print(f"[{time.strftime('%T')}] S8 split{r['seed']} {r['target']}: lam {r['a']}/{r['b']} inf {r['infeasible']} cal {r['cal_risk']:.4f} | ho risk {r['ho']['risk']:.4f} vm {r['ho']['alloc']:.1f} fl {r['ho']['flaps']:.2f}",flush=True)
    print(f"DONE {time.time()-t0:.0f}s")
