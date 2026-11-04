#!/usr/bin/env python3
"""v8sim_b6.py(10-08,審查第二十三輪):B6 = Toka et al. 2021 型「多預測器 + 主動式 HPA」的模擬實作(先驗庫訓練;各層以實測前置讀預測)。
 預測器集合(Toka:AR、HTM、LSTM;本機無 torch/sklearn → AR(p)、Holt、numpy MLP;LSTM 缺席要在論文註明):
   AR(3) on first differences(最小平方法,全庫擬合)、Holt(α=0.3, β=0.05,fit_holt.py)、MLP(輸入最近 8 tick 的相對水準,輸出 h∈{2,4,5} tick 的增量;numpy SGD,全庫訓練)
 選用器(Toka 回測):每 tick 以最近 W=10 tick 的回測 MAE(h 步)挑最佳預測器,逐層(各層 horizon 不同)。
 控制律(各層獨立,沿用 b4 的 HPA/DASA 形狀):desired_k = need_k(forecast(t+h_k) / u_k)(u = 容量利用目標 = 調參旋鈕,對應 HPA_TARGET_SESS/DASA_MU);
   out 若 desired > cur+pending(worker 位置不足先建 worker,同 v6);反應式保底:need_k(D_now) > cur → out;in 若 need_k(max(回看窗內實際與預測)/u) ≤ cur−1 且 dwell(UP 300 / VM 600)。
 評估同 sim_v6:loss_step、alloc=Σ cores×burn、slo=分鐘 loss≤0.1%。
用法:python3 v8sim_b6.py train   → 擬合並存 b6_models.json;python3 v8sim_b6.py eval [u ...] → t1/t2 + 整庫(⛔ 整庫只在 testbed 空檔跑)"""
import sys, json, math, random, time
import numpy as np
sys.path.insert(0, '/home/cyy/experiment/qsim')
import v8sim2 as S, v8sim7 as M
E = '/home/cyy/experiment'; Q = f'{E}/qsim'
import os
H_TICKS = {"up": 2, "vy": 5, "wk": int(os.environ.get("B6_WK_TICKS", "5"))}   # 實測 p90 lead → tick(UP 60 s、VY 150 s、WK 150 s;與 B5 manifest 同);10-09 審查第二十五輪:B6_WK_TICKS=7 檢查「worker 視野應含槽啟動」
FORECASTERS = os.environ.get("B6_FORECASTERS", "ar,holt,mlp").split(",")   # "holt" = B5 型(單一 Holt 預測器,同控制律)
TICKS_PER_MIN = 60 // S.TICK                  # 2
# ---------------- forecasters ----------------
class Holt:
    name = "holt"
    def __init__(s, a=0.3, b=0.05): s.a, s.b, s.L, s.T, s.init = a, b, 0.0, 0.0, False
    def update(s, x):
        if not s.init: s.L, s.T, s.init = x, 0.0, True
        else: Lp = s.L; s.L = s.a * x + (1 - s.a) * (s.L + s.T); s.T = s.b * (s.L - Lp) + (1 - s.b) * s.T
    def fc(s, hist, h): return s.L + h * s.T
class AR:
    name = "ar"
    def __init__(s, coef): s.c = np.array(coef)  # on first differences, p=len(coef)
    def update(s, x): pass
    def fc(s, hist, h):
        x = list(hist); p = len(s.c)
        if len(x) < p + 1: return x[-1]
        for _ in range(h):
            d = np.array([x[-1 - i] - x[-2 - i] for i in range(p)]); x.append(x[-1] + float(s.c @ d))
        return x[-1]
class MLP:
    name = "mlp"
    def __init__(s, W): s.W1, s.b1, s.W2, s.b2 = (np.array(W[k]) for k in ("W1", "b1", "W2", "b2")); s.hs = (2, 4, 5)
    def update(s, x): pass
    def feat(s, hist):
        x = np.array(hist[-8:], float)
        if len(x) < 8: x = np.concatenate([np.full(8 - len(x), x[0]), x])
        lvl = max(x[-1], 1.0); return (x / lvl - 1.0), lvl
    def fc(s, hist, h):
        f, lvl = s.feat(hist); z = np.tanh(f @ s.W1 + s.b1); out = z @ s.W2 + s.b2   # relative deltas at hs
        i = s.hs.index(h) if h in s.hs else min(range(3), key=lambda j: abs(s.hs[j] - h))
        return hist[-1] + out[i] * lvl
def train(lib_n=1615, seed=3):
    random.seed(seed); lib = json.load(open(f'{Q}/prior_traces.json')); ser = [np.repeat(np.array(t["ue"], float), TICKS_PER_MIN) for t in lib[:lib_n]]
    # AR(3) on differences, least squares over the whole library
    X, y = [], []
    for sq in ser:
        d = np.diff(sq)
        for i in range(3, len(d)): X.append(d[i - 3:i][::-1]); y.append(d[i])
    X = np.array(X); y = np.array(y); coef = np.linalg.lstsq(X, y, rcond=None)[0]
    # MLP: 8 -> 16 -> 3 (relative deltas at h=2,4,5), SGD on the library
    rng = np.random.default_rng(seed); W1 = rng.normal(0, 0.3, (8, 16)); b1 = np.zeros(16); W2 = rng.normal(0, 0.3, (16, 3)); b2 = np.zeros(3)
    feats, tgts = [], []
    for sq in ser:
        for i in range(8, len(sq) - 5):
            x = sq[i - 8:i]; lvl = max(x[-1], 1.0); feats.append(x / lvl - 1.0); tgts.append([(sq[i - 1 + h] - x[-1]) / lvl for h in (2, 4, 5)])
    feats = np.array(feats); tgts = np.array(tgts); n = len(feats); lr = 0.01
    for ep in range(30):
        idx = rng.permutation(n)
        for j in range(0, n, 64):
            b = idx[j:j + 64]; f = feats[b]; t = tgts[b]
            z = np.tanh(f @ W1 + b1); o = z @ W2 + b2; g = (o - t) / len(b)
            gW2 = z.T @ g; gb2 = g.sum(0); gz = g @ W2.T * (1 - z ** 2); gW1 = f.T @ gz; gb1 = gz.sum(0)
            W1 -= lr * gW1; b1 -= lr * gb1; W2 -= lr * gW2; b2 -= lr * gb2
    z = np.tanh(feats @ W1 + b1); mse = float(((z @ W2 + b2 - tgts) ** 2).mean())
    json.dump({"ar": coef.tolist(), "holt": [0.3, 0.05], "mlp": {"W1": W1.tolist(), "b1": b1.tolist(), "W2": W2.tolist(), "b2": b2.tolist()}, "mlp_mse_rel": mse, "n_series": len(ser)}, open(f'{Q}/b6_models.json', 'w'))
    print(f"trained on {len(ser)} series: AR(3) coef {np.round(coef,3).tolist()}  MLP rel-MSE {mse:.4f}")
def load_models():
    m = json.load(open(f'{Q}/b6_models.json'))
    def mk():
        all_ = {"ar": AR(m["ar"]), "holt": Holt(*m["holt"]), "mlp": MLP(m["mlp"])}
        return [all_[n] for n in FORECASTERS if n in all_]
    return mk
# ---------------- controller + sim ----------------
def sim_b6(ue, cfg, u=None, models=None, W=10, dwell=None, safety=True, ev=None):
    """u: per-layer capacity-utilization target (dict or float); models: factory returning fresh forecasters."""
    u = u if isinstance(u, dict) else {k: (u or 0.93) for k in ("up", "vy", "wk")}
    dwell = dwell or {"up": 300, "vy": 600, "wk": 600}
    d = S.expand(ue) * cfg.scale; n = len(d); DT, TICK = S.DT, S.TICK
    fcs = models() if models else load_models()()
    hist = []                       # sessions per tick (UE units)
    pred_log = {f.name: {} for f in fcs}   # (tick_index+h) -> predicted value, for backtest
    cur = {k: cfg.need(k, d[0]) for k in cfg.h}; cur["wk"] = max(cur["wk"], math.ceil(cur["up"] / cfg.spw))
    infl, dying = [], []; burn = dict(cur); last_out = {k: -1e9 for k in cur}; last_in = {k: -1e9 for k in cur}
    alloc = 0.0; acts = 0; flaps = 0; last_dir = {k: (None, -1e9) for k in cur}; lossmin = np.zeros(60); offmin = np.zeros(60); chosen = {k: {} for k in cur}
    def need_u(k, x): return cfg.need(k, x / u[k])
    ti = 0
    for i in range(n):
        t = i * DT
        for x in [x for x in infl if x[0] <= t]: cur[x[1]] += 1; infl.remove(x)
        for x in [x for x in dying if x[0] <= t]: burn[x[1]] -= 1; dying.remove(x)
        l = S.loss_step(cfg, cur, d[i]); lossmin[i * DT // 60] += l * d[i] * DT; offmin[i * DT // 60] += d[i] * DT
        alloc += sum(cfg.cores[k] * burn[k] for k in burn) * DT / 60
        if t % TICK == 0:
            x = float(d[i] / cfg.scale); hist.append(x)
            for f in fcs: f.update(x)
            # forecasts for each horizon + backtest selection
            fc = {}
            for k in ("vy", "wk", "up"):
                h = H_TICKS[k]
                errs = {}
                for f in fcs:
                    e = [abs(pred_log[f.name].get((j, h), hist[j]) - hist[j]) for j in range(max(0, ti - W), ti)]
                    errs[f.name] = sum(e) / len(e) if e else 0.0
                best = min(fcs, key=lambda f: errs[f.name]); chosen[k][best.name] = chosen[k].get(best.name, 0) + 1
                fc[k] = max(0.0, best.fc(hist, h))
                for f in fcs: pred_log[f.name][(ti + h, h)] = f.fc(hist, h)
            pend = {k: sum(1 for z in infl if z[1] == k) for k in cur}
            for k in ("vy", "wk", "up"):
                want = max(need_u(k, fc[k]), need_u(k, x) if safety else 0)
                if want > cur[k] + pend[k] and cur[k] + pend[k] < S.FMAX[k]:
                    if k == "up" and cur["up"] + pend["up"] + 1 > (cur["wk"] + pend["wk"]) * cfg.spw: continue
                    teff = t + cfg.h[k]
                    if k == "up" and cur["up"] + pend["up"] + 1 > cur["wk"] * cfg.spw and any(z[1] == "wk" for z in infl): teff = max(teff, max(z[0] for z in infl if z[1] == "wk") + cfg.h["up"])
                    infl.append((teff, k)); burn[k] += 1; acts += 1; last_out[k] = t
                    if ev is not None: ev.append((t, "out", k))
                    if last_dir[k][0] == -1 and t - last_dir[k][1] <= 600: flaps += 1
                    last_dir[k] = (+1, t)
            for k in ("up", "vy", "wk"):
                if cur[k] <= S.FMIN[k] or pend[k] > 0: continue
                if k == "wk" and (cur["wk"] - 1) * cfg.spw < cur["up"] + pend["up"]: continue
                j0 = max(0, ti - W); ref = max(max(hist[j0:ti + 1]), fc[k])
                if need_u(k, ref) <= cur[k] - 1 and t - last_out[k] >= dwell[k] and t - last_in[k] >= dwell[k]:
                    cur[k] -= 1; dying.append((t + cfg.d[k], k)); acts += 1; last_in[k] = t
                    if ev is not None: ev.append((t, "in", k))
                    if last_dir[k][0] == +1 and t - last_dir[k][1] <= 600: flaps += 1
                    last_dir[k] = (-1, t)
            ti += 1
    pct = 100 * lossmin / np.maximum(offmin, 1e-9)
    return dict(slo=int((pct <= 0.1).sum()), alloc=alloc, acts=acts, flaps=flaps, chosen=chosen, worst=float(pct.max()))
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "eval"
    if mode == "train": train(); sys.exit()
    cfg = M.cfg_measured(); mk = load_models()
    TR = {t: json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60] for t, f in (("t1", "40"), ("t2", "pm"))}
    if os.environ.get("PRED") == "1": TR.update({t: json.load(open(f"{E}/trace_ue_60min_v3_{t}.json"))["ue"][:60] for t in ("t3", "t4", "t5")})
    us = [float(a) for a in sys.argv[2:] if a != "lib"] or [0.93, 0.85, 0.78, 0.70]
    print(f"=== B6 (Toka-type) sim {time.strftime('%F %T')}; u = capacity-utilization target (HPA_TARGET analogue); objective: ≥58/60 on t1&t2 then min alloc")
    print(f" forecasters={FORECASTERS} wk_ticks={H_TICKS['wk']}")
    for u in us:
        rs = {t: sim_b6(TR[t], cfg, u, mk) for t in TR}
        print(f" u={u:.2f}  " + " | ".join(f"{t} SLO {r['slo']}/60 alloc {r['alloc']:.0f} worst {r['worst']:.2f}%" for t, r in rs.items()), flush=True)
    if "lib" in sys.argv:
        lib = json.load(open(f'{Q}/prior_traces.json'))
        for u in us:
            rs = [sim_b6(tr["ue"][:60], cfg, u, mk) for tr in lib]
            risk = sum(60 - r['slo'] for r in rs) / (60 * len(rs)); print(f" u={u:.2f} library({len(rs)}): risk {risk:.4f} alloc {np.mean([r['alloc'] for r in rs]):.1f}", flush=True)
