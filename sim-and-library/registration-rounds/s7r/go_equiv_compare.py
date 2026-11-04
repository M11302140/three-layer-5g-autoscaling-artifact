#!/usr/bin/env python3
"""s7r/go_equiv_compare.py: runs the frozen equiv_compare.py against the s7r worktree dumps (only D changes) and applies equiv_gate.sh's rule
(v7.1.3 scenarios: differing cells must be 0, pps scenarios <= 2, v712 scenarios skipped)."""
import sys, io, contextlib, re
sys.argv=['equiv_compare.py']; sys.path.insert(0,'/home/user/experiment/qsim')
D=sys.argv[1] if len(sys.argv)>1 else '/home/user/hhro-daemon-s7r/internal/hbo/testdata/equiv'
src=open('/home/user/experiment/qsim/equiv_compare.py').read().replace("D='/home/user/hhro-daemon/internal/hbo/testdata/equiv'",f"D='{D}'")
buf=io.StringIO()
with contextlib.redirect_stdout(buf): exec(compile(src,'equiv_compare.py','exec'),{'__name__':'__main__'})
bad=0
for l in buf.getvalue().splitlines():
    if not l.startswith('==='): continue
    print(l); f=l.split(); name=f[1]; cells=float(f[-1])
    if 'v712' in name: continue
    if cells>(2 if 'pps' in name else 0): bad+=1; print('  FAIL',name,cells)
print('EQUIV GATE:', 'PASS' if bad==0 else f'FAIL ({bad} scenarios)')
