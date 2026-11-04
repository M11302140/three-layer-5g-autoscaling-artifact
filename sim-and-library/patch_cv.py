s=open("cv.py").read()
if "class Prior:" in s: raise SystemExit("already patched")
old_cls=s[s.index("class QModel:"):s.index("def simulate(")]
new_cls='''class Prior:
    """(docstring removed)"""
    def __init__(s, prior):
        s.tab={}
        for h in HS:
            a=np.array(prior[h],float)   # (ctx, level, rise)
            for rel in (False,True):
                v=a[:,2]/np.maximum(a[:,1],LMIN) if rel else a[:,2]
                if rel: v=np.round(v,3)
                for c in (None,0,1,2):
                    vv=v if c is None else v[a[:,0]==c]
                    u,cnt=np.unique(vv,return_counts=True)
                    s.tab[(h,c,rel)]=(u,np.cumsum(cnt))
class QModel:
    def __init__(s, P, eps, rel=False, ctx=False, aci=True, gamma=None, amin=None):
        s.P=P; s.rel=rel; s.ctx=ctx; s.aci=aci; s.eps=eps
        s.gamma=gamma if gamma is not None else max(0.005, eps/5)
        s.amin=amin if amin is not None else eps/4
        s.on={}
        s.alpha={h:eps for h in HS}; s.pending={h:[] for h in HS}; s.err={h:[] for h in HS}
    def margin(s,h,level,c):
        key=(h,c if s.ctx else None,s.rel); u,cum=s.P.tab[key]
        on=s.on.get(key[:2],[])
        a=min(max(s.alpha[h],s.amin),1.0)
        n=cum[-1]+len(on); k=max(1, math.ceil((1-a)*n))
        cand=np.union1d(u,on) if on else u
        cp=np.searchsorted(u,cand,side="right"); cp=np.where(cp>0,cum[np.maximum(cp-1,0)],0)
        if on:
            o=np.sort(on); cp=cp+np.searchsorted(o,cand,side="right")
        i=int(np.searchsorted(cp,k,side="left")); i=min(i,len(cand)-1); m=float(cand[i])
        return m*max(level,LMIN) if s.rel else m
    def tick(s,t,d,i):
        c=ctx_of(d,i)
        for h in HS:
            k=h//DT
            while s.pending[h] and s.pending[h][0][0]+h<=t:
                t0,base,m,c0=s.pending[h].pop(0); i0=t0//DT
                real=d[i0+1:i0+k+1].max()-base
                e=1.0 if real>m+1e-9 else 0.0; s.err[h].append(e)
                if s.aci: s.alpha[h]=min(1.0,max(-0.5,s.alpha[h]+s.gamma*(s.eps-e)))
                v=round(real/max(base,LMIN),3) if s.rel else real
                s.on.setdefault((h,c0 if s.ctx else None),[]).append(v)
            s.pending[h].append((t,d[i],s.margin(h,d[i],c),c))
        return c
'''
s=s.replace(old_cls,new_cls)
s=s.replace("for e in EPS: add((name,e),simulate(ue,QModel(prior,e,**kw)),fl)","for e in EPS: add((name,e),simulate(ue,QModel(PR,e,**kw)),fl)")
s=s.replace('        for tr in test:\n            ue=tr["ue"]; fl=oracle_alloc(ue,5)','        PR=Prior(prior)\n        for tr in test:\n            ue=tr["ue"]; fl=oracle_alloc(ue,5)')
open("cv.py","w").write(s); print("patched")
