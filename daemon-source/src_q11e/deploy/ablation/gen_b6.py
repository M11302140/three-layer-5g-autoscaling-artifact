#!/usr/bin/env python3
"""(docstring removed)"""
import json, re, sys
D = '/home/user/hhro-daemon/deploy/ablation'
tag = sys.argv[1]; us = [float(a) for a in sys.argv[2:]] or [0.93, 0.85, 0.78]
models = json.load(open('/home/user/experiment/qsim/b6_models.json'))
mj = json.dumps({k: models[k] for k in ("ar", "holt", "mlp")}, separators=(',', ':'))
mj = json.dumps(mj)  # YAML double-quoted scalar
tpl = open(f'{D}/B5c1_slo.yaml').read()
tpl = re.sub(r'image: hhro-daemon:6\.0-\S+', f'image: hhro-daemon:6.0-{tag}', tpl, count=1)
start = tpl.index('        - {name: BASELINE_MODE,')
end = tpl.index('\n', tpl.index('- {name: HOLT_BETA')) + 1
for i, u in enumerate(us, 1):
    env = (f'        - {{name: BASELINE_MODE,       value: "b6"}}\n'
           f'        - {{name: B6_U, value: "{u}"}}\n'
           f'        - {{name: B6_DWELL_UP, value: "300s"}}\n        - {{name: B6_DWELL_VM, value: "600s"}}\n        - {{name: B6_BACKTEST_W, value: "10"}}\n'
           f'        - {{name: B5_LEAD_TICKS_UP, value: "2"}}\n        - {{name: B5_LEAD_TICKS_VY, value: "5"}}\n        - {{name: B5_LEAD_TICKS_WK, value: "5"}}\n'
           f'        - {{name: DASA_N0, value: "1"}}\n        - {{name: DASA_K_MAX, value: "2"}}\n        - {{name: HPA_MIN, value: "2"}}\n        - {{name: HPA_MAX, value: "8"}}\n'
           f'        - {{name: B6_MODELS, value: {mj}}}\n')
    out = tpl[:start] + env + tpl[end:]
    open(f'{D}/B6c{i}_slo.yaml', 'w').write(out); print(f'B6c{i}_slo.yaml u={u} tag={tag}')
