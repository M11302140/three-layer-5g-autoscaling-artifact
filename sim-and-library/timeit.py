import json,time,cv,qsim
lib=json.load(open('prior_traces.json'))[:200]
prior={h:[] for h in qsim.HS}
for tr in lib:
    d=qsim.expand(tr['ue'])
    for h in qsim.HS: prior[h]+=cv.samples(d,h)
t=time.time(); P=cv.Prior(prior); print('prior build',round(time.time()-t,2))
t=time.time(); r=cv.simulate(lib[0]['ue'],cv.QModel(P,0.05,ctx=True)); print('sim',round(time.time()-t,2),r)
