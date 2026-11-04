#!/usr/bin/env python3
"""trace_run — trace-driven workload runner (v4, 2026-07-04).

v4: (a) per-UE keepalive (real UL via the nr-ue tun holds CM-CONNECTED —
run#3's idle-page-release death spiral) + (c) dead-session re-establish
(reap + same-minute respawn via the arrivals loop, guarded by slot
reachability and the agent's running-job set).

Plays a per-minute UE-count trace (trace_ue_60min.json: real Melbourne
pedestrian counts, 24h day compressed 24:1 into 60 experiment minutes)
against the live testbed:

  * all 32 gNBs are brought up ONCE and stay up for the whole run — the
    slow/fragile NG-setup layer never churns;
  * UE arrival  = start nr-ue only (registration + PDU via the standing gNB);
  * UE departure = nr-cli deregister (proper SMF/eUPF release — no pool
    leaks), then reap the process;
  * every experiment minute: reconcile membership to the trace target,
    refresh TEIDs, rebalance streams across the CURRENT VyOS fleet, and
    set_load(active, PPS_PER_UE) (offered==realized via the built-in servo);
  * one measurement Window per minute -> CSV row.

The hhro-daemon (autoscale enabled) and the rehome agent run alongside; the
shared /tmp/m32.json + /tmp/uemap.json are re-read every minute so daemon
rehomes and harness membership changes converge at minute boundaries.
"""
import sys, os, time, json, csv, re, shlex, subprocess as sp
sys.path.insert(0, '/home/user/experiment'); sys.path.insert(0, '/tmp')
import experiment_hbo as hbo
import trex_traffic as T
import mlib
from eupf_teids import teids_from_eupf

v22 = hbo.v22
NR_CLI = '/home/user/UERANSIM/build/nr-cli'
TRACE = json.load(open(sys.argv[1] if len(sys.argv) > 1 else
                       '/home/user/experiment/trace_ue_60min.json'))
PPS_PER_UE = TRACE.get('pps_per_ue', 150000)

REAPERS = os.environ.get('REAPERS', '0') == '1'

BOUNCE3_GAP_S = float(os.environ.get('BOUNCE3_GAP_S', '10'))
WARMIN_RUN = 'warmin' in (sys.argv[1] if len(sys.argv) > 1 else '')
_BOUNCE3_RESPAWNED = {}
_BOUNCE3_PENDING = {}
_VY_BOOT = {}

HAIRPIN_STATIC = os.environ.get('HAIRPIN_STATIC', '1') == '1'

UE_SEQ = TRACE['ue']
MAX_UE = TRACE.get('max_ue', 32)
DNNS = ['internet', 'internet2', 'internet3', 'internet4',
        'internet5', 'internet6', 'internet7', 'internet8']
OUT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/trace_run.csv'

def P(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def imsi_of(idx):
    return f"imsi-{999700000000001 + idx:015d}"

KEEPALIVE_DST = '10.0.1.16'   # DN — UL rides the REAL nr-ue -> gNB -> eUPF path
KA = {}                          # idx -> {'tun': str, 'proc': Popen}

def ensure_keepalive(idx, tun):
    """(a) UE keepalive: low-rate real UL through the UE's tun keeps RRC/CM
    CONNECTED, so the core never pages an "idle" UE and releases it (run#3
    root cause: TRex injects UL at the GTP layer, the real nr-ue never sees
    traffic -> CM-IDLE -> DDN/paging -> T3517 expiry -> AMF releases ~2min).
    ICMP replies are redirected to TRex by the measurement neighbors — 100%
    ping loss is expected and irrelevant (UL activity is what keeps CM state).
    Called every minute with a re-resolved tun: rehome (ps-establish) and
    respawn both allocate a NEW uesimtunN."""
    k = KA.get(idx)
    if k and k['tun'] == tun and k['proc'].poll() is None:
        return
    stop_keepalive(idx)
    KA[idx] = {'tun': tun,
               'proc': sp.Popen(['ping', '-I', tun, '-i', '2', '-q',
                                 KEEPALIVE_DST],
                                stdout=sp.DEVNULL, stderr=sp.DEVNULL)}

def stop_keepalive(idx):
    k = KA.pop(idx, None)
    if k:
        try:
            k['proc'].kill()
            k['proc'].wait(timeout=2)
        except Exception:
            pass

def agent_job_sig():
    """(running, last) job signature from the agent — used to detect a rehome
    finishing MID measurement window."""
    try:
        import urllib.request
        d = json.load(urllib.request.urlopen(
            'http://127.0.0.1:9801/status', timeout=3))
        return (d.get('running'), d.get('last'))
    except Exception:
        return ('_unreachable', None)

def m32_teids(ips):
    """{ue_ip: ul_teid} from /tmp/m32.json for the given ips. Rehome jobs
    change TEIDs without touching assign — a job completing inside the
    minute-boundary blind spot (after load_state, before win.open) leaves the
    window's streams on OLD teids with no signature the assign-compare can
    see; the old anchor then dies at release+30s and the UE goes dark for the
    rest of the window (run#12 min4: 13.2%)."""
    try:
        return {t['ue_ip']: t['ul_teid']
                for t in json.load(open('/tmp/m32.json'))
                if t.get('ue_ip') in ips}
    except Exception:
        return None

DRAIN_FILE = '/tmp/vy_drain.json'
UL_POOL_FILE = '/tmp/ul_pool.json'

def prime_dl_affinity(m, tl):
    """(docstring removed)"""
    if not tl:
        return

    prev = dict(getattr(m, '_vy_by_ip', {}) or {})
    m.active_ues = len(tl)
    m.balance_vyos()
    pre = dict(m.ue_vyos)
    sub = [t for i, t in enumerate(tl)
           if prev.get(t['ue_ip']) in (None, pre.get(i))]
    try:
        if sub:
            mlib.worker_repoint(sub, lambda t: mlib.VMAC[pre[tl.index(t)]])
    except Exception as e:
        P(f"  pre-repoint warn: {e}")

def _ul_pool_heartbeat(stop_evt):
    """(docstring removed)"""
    while not stop_evt.wait(2.0):
        try:
            d = json.load(open('/tmp/ul_pool.json'))
            d['ts'] = time.time()
            tmp = '/tmp/ul_pool.json.tmp'
            with open(tmp, 'w') as f:
                json.dump(d, f)
            os.replace(tmp, '/tmp/ul_pool.json')
        except Exception:
            pass

def publish_ul_pool(m):
    """Publish the VyOS set our UPLINK streams are actually built on.

    This is the acknowledgement half of the daemon's two-phase VyOS drain:
    the daemon will not destroy a VyOS until it has left this set. Must be
    called after EVERY set_load/stop — a stale file reads as 'still riding
    the victim' and merely costs the daemon its bounded wait."""
    try:
        pool = sorted({v for v in (getattr(m, 'ue_vyos', {}) or {}).values() if v})
        tmp = UL_POOL_FILE + '.tmp'
        json.dump({'pool': pool, 'ts': time.time()}, open(tmp, 'w'))
        os.replace(tmp, UL_POOL_FILE)
    except Exception as e:
        P(f"  ul_pool publish warn: {e}")

SLOT_DRAIN_FILE = '/tmp/slot_drain.json'

def agent_inflight_move_dnns():
    """(docstring removed)"""
    try:
        rr = sp.run("timeout 3 curl -s http://127.0.0.1:9801/status", shell=True,
                    capture_output=True, text=True)
        st = json.loads(rr.stdout or '{}')
        run = st.get('running') or []
        if isinstance(run, str):
            run = json.loads(run) if run.strip() else []
        return [str(mv[1]) for mv in run if isinstance(mv, (list, tuple)) and len(mv) >= 2]
    except Exception:
        return []

def slot_draining_dnns():
    """DNNs whose eUPF slot the daemon is draining right now (agent publishes
    on DrainAndDelete start/end). r9 min4-5 (2026-09-06): a draining slot has
    occupancy 0 and a live PFCP association, so the least-loaded placement
    steered a fresh arrival straight onto it (UE-6 → internet2, slot deleted
    58 s later). Stale file (>10 min) is ignored."""

    try:
        d = json.load(open(SLOT_DRAIN_FILE))
        now = time.time()
        if now - d.get('ts', 0) < 600:
            on_ts = d.get('on_ts')
            if not isinstance(on_ts, dict):
                return set()
            ttl = float(os.environ.get('SLOT_DRAIN_TTL_S', '360'))
            return {x for x in d.get('draining_dnns', []) if now - on_ts.get(x, 0) < ttl}
    except Exception:
        pass
    return set()

def vy_draining():
    """VyOS data-IPs the daemon has announced as draining (phase 1).

    Replaces the old discovery channel — two failed mgmt pings — which a
    dying KubeVirt VM defeats for tens of seconds (r29 min32: 33s late;
    min39: never inside the window -> 5/11 UEs dark for 63s = 45.44%)."""
    try:
        d = json.load(open(DRAIN_FILE))

        if time.time() - d.get('ts', 0) > 240:
            return set()
        return set(d.get('draining', []))
    except Exception:
        return set()

def uemap_assign():
    """Current assign map from /tmp/uemap.json — the agent rewrites it on
    /rehome AND /repath. A daemon delete_vyos repaths UEs mid-window WITHOUT a
    rehome job: their UL streams keep the dead VyOS MAC until the next
    set_load (run#10 min44: 26.7%). CONTENT comparison, not mtime: a repath
    landing during minute-boundary processing (after our save_state, before
    win.open) has the post-repath mtime already — an mtime baseline taken at
    window open silently swallows it (run#11 min42/54: 7.6%/9.2%, detection
    never fired)."""
    try:
        return json.load(open('/tmp/uemap.json')).get('assign', {})
    except Exception:
        return None

def agent_ue_ips():
    """(docstring removed)"""
    try:
        import urllib.request
        d = json.load(urllib.request.urlopen(
            'http://127.0.0.1:9801/ues?live=1', timeout=3))
        return {int(k): v.get('ue_ip') for k, v in d.get('ues', {}).items() if v.get('ue_ip')}
    except Exception:
        return {}

def agent_busy_ues():
    """UE idxs inside a rehome job running on the agent RIGHT NOW. A UE mid
    cli_move is sessionless for seconds (release->establish window); declaring
    it dead and reaping it would collide with the agent's job."""
    try:
        import urllib.request
        d = json.load(urllib.request.urlopen(
            'http://127.0.0.1:9801/status', timeout=3))
        if d.get('running'):
            return {int(u) for u, _ in json.loads(d['running'])}
    except Exception:
        pass
    return set()

def gnb_ip(idx):
    return f"10.0.1.{(100 + idx) if idx < 8 else (101 + idx)}"

_SEG_MISS = {'prev': None}

_SEG_MISS10 = {'prev': None, 't': 0.0}

def seg_health_kick10(minute):
    """(docstring removed)"""
    now = time.time()
    if now - _SEG_MISS10['t'] < 10:
        return
    dt = now - _SEG_MISS10['t'] if _SEG_MISS10['t'] else 0
    _SEG_MISS10['t'] = now
    try:
        out = sp.run(
            "echo $SUDO_PASS | sudo -S vppctl -s /run/vpp/cli-seg.sock "
            "show hardware-interfaces seg-esp",
            shell=True, capture_output=True, text=True, timeout=8).stdout
        m = re.search(r'rx_missed_errors\s+(\d+)', out or '')
        cur = int(m.group(1)) if m else None
    except Exception:
        cur = None
    prev, _SEG_MISS10['prev'] = _SEG_MISS10['prev'], cur
    if cur is None or prev is None or cur < prev or dt <= 0 or dt > 60:
        return
    rate = (cur - prev) / dt
    if rate > 1000:
        P(f"min{minute}: SEG dec-thread kick10 (rxmiss {rate:.0f}/s over {dt:.0f}s)")
        _SEG_MISS['prev'] = None
        sp.run(
            "echo $SUDO_PASS | sudo -S bash -c '"
            "V=\"vppctl -s /run/vpp/cli-seg.sock\"; "
            "$V ipsec sa bind 131 2; $V ipsec sa bind 131 1; "
            "$V ipsec sa bind 132 4; $V ipsec sa bind 132 3; "
            "$V ipsec sa bind 133 3; $V ipsec sa bind 133 2; "
            "$V ipsec sa bind 134 4; $V ipsec sa bind 134 5'",
            shell=True, capture_output=True, timeout=20)

def seg_health_kick(minute):
    """(docstring removed)"""
    try:
        out = sp.run(
            "echo $SUDO_PASS | sudo -S vppctl -s /run/vpp/cli-seg.sock "
            "show hardware-interfaces seg-esp",
            shell=True, capture_output=True, text=True, timeout=12).stdout
        m = re.search(r'rx_missed_errors\s+(\d+)', out or '')
        cur = int(m.group(1)) if m else None
    except Exception:
        cur = None
    prev, _SEG_MISS['prev'] = _SEG_MISS['prev'], cur
    if cur is None or prev is None or cur < prev:
        return
    rate = (cur - prev) / 60.0

    if rate > 1000 or minute % 10 == 5:
        P(f"min{minute}: SEG dec-thread kick (rxmiss {rate:.0f}/s)")
        sp.run(
            "echo $SUDO_PASS | sudo -S bash -c '"
            "V=\"vppctl -s /run/vpp/cli-seg.sock\"; "
            "$V ipsec sa bind 131 2; $V ipsec sa bind 131 1; "
            "$V ipsec sa bind 132 4; $V ipsec sa bind 132 3; "
            "$V ipsec sa bind 133 3; $V ipsec sa bind 133 2; "
            "$V ipsec sa bind 134 4; $V ipsec sa bind 134 5'",
            shell=True, capture_output=True, timeout=20)

def _preserve_gnb_log(idx):
    """(docstring removed)"""
    try:
        src = f"/tmp/hbo-gnb-{idx}.log"
        if os.path.exists(src) and os.path.getsize(src) > 0:
            import shutil
            shutil.copyfile(src, f"/tmp/hbo-gnb-{idx}.{time.strftime('%H%M%S')}.lost.log")
    except Exception:
        pass

def _live_ngap_gnbs():
    """gNB IPs with an ESTABLISHED SCTP association to the AMF (ss ground
    truth — log markers go stale across AMF restarts)."""
    # ESTAB only — a COOKIE_WAIT zombie (mass-bounce INIT loss, init-retrans
    # exhausted) still shows an ss entry and used to false-positive this check.
    out = sp.run("ss -S -n 2>/dev/null | grep ':38412' | grep ESTAB || true",
                 shell=True, capture_output=True, text=True).stdout
    ips = set(re.findall(r'(10\.10\.10\.\d+):\d+\s+10\.10\.10\.10:38412', out))

    alive_idx = set()
    ps = sp.run("ps -eo args 2>/dev/null | grep -E 'nr-gnb(\\.real)? -c' "
                "| grep -v grep || true",
                shell=True, capture_output=True, text=True).stdout
    for mm in re.finditer(r'mgnb-(\d+)\.yaml', ps):
        alive_idx.add(int(mm.group(1)))
    return {ip for ip in ips
            if _gnb_idx_of_ip(ip) is None or _gnb_idx_of_ip(ip) in alive_idx}

def _gnb_idx_of_ip(ip):
    try:
        o = int(ip.rsplit('.', 1)[1])
    except ValueError:
        return None
    if 100 <= o <= 107:
        return o - 100
    if 109 <= o <= 145:
        return o - 101
    return None

def _departures_not_released(leave_ip, tries=2, gap=3):
    """UE idx whose ip is STILL held by some slot `tries` polls after dereg."""
    ips = [ip for ip in leave_ip.values() if ip]
    if not ips:
        return []
    stuck = []
    for k in range(tries):
        held = {t['ue_ip'] for t in (teids_from_eupf(ips) or [])}
        stuck = [i for i, ip in leave_ip.items() if ip and ip in held]
        if not stuck:
            return []
        if k < tries - 1:
            time.sleep(gap)
    return stuck

def _recover_lost_departure(idx, dnn, old_ip):
    """dereg was dropped by a dead-NG gNB: bounce gNB → same-imsi re-register
    (fresh context replaces the stale one at AMF/SMF) → switch-off → verify."""
    try:
        # keep the evidence: fire_and_forget truncates the gNB log on respawn
        try:
            sp.run(f"tail -c 65536 /tmp/hbo-gnb-{idx}.log > /tmp/hbo-gnb-{idx}.lost.log 2>/dev/null; "
                   f"tail -c 65536 /tmp/hbo-ue-{idx}.log > /tmp/hbo-ue-{idx}.lost.log 2>/dev/null",
                   shell=True, timeout=5)
        except Exception:
            pass
        v22._pkill_pattern_root(rf"nr-ue(\.real)? -c .*mue-{idx}\.yaml")
        _preserve_gnb_log(idx)
        v22._pkill_pattern_root(rf"nr-gnb(\.real)? -c .*mgnb-{idx}\.yaml")
        time.sleep(1)
        v22.fire_and_forget(
            f"{hbo.UERANSIM_DIR}/build/nr-gnb -c {hbo.GNB_CFG_TMPL.format(i=idx)}",
            log_path=f"/tmp/hbo-gnb-{idx}.log")
        for _ in range(8):
            time.sleep(1)
            if gnb_ip(idx) in _live_ngap_gnbs():
                break
        try:
            spawn_ue_only(idx, dnn, timeout=20)
        except Exception as e:  # noqa: BLE001
            P(f"  UE-{idx} re-register for release failed: {e}")
        time.sleep(1)
        sp.run([NR_CLI, imsi_of(idx), '-e', 'deregister switch-off'],
               capture_output=True, timeout=10)
        time.sleep(3)
        held = {t['ue_ip'] for t in (teids_from_eupf([old_ip]) or [])}
        P(f"  UE-{idx} recovery: old {old_ip} {'STILL held — zombie' if old_ip in held else 'released ✓'}")
    except Exception as e:  # noqa: BLE001
        P(f"  UE-{idx} departure recovery error: {e}")

def _gnb_ng_dead_by_log(i):
    """NG-layer liveness from the gNB's own log: a failure marker AFTER the last
    successful NG Setup = the association is gone even though ss still shows
    the SCTP socket ESTABLISHED (r8 mgnb-17: `AMF selection ... failed`,
    `AMF context not found with id: 0` while every departure's dereg was dropped)."""
    try:
        with open(f"/tmp/hbo-gnb-{i}.log", 'rb') as f:
            f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 65536))
            tail = f.read().decode(errors='ignore')
    except Exception:
        return False
    ok = max(tail.rfind('NG Setup procedure is successful'), -1)
    bad = max(tail.rfind('AMF selection for UE'), tail.rfind('AMF context not found'),
              tail.rfind('Association terminated for AMF'),      # ngap/interface.cpp handleAssociationShutdown
              tail.rfind('Initial NAS transport failure. AMF is not in connected state'),
              tail.rfind('NG Setup procedure is failed'))
    return bad > ok

def _gnb_pdu_lost_by_log(i, min_hits=20):
    """(docstring removed)"""
    try:
        with open(f"/tmp/hbo-gnb-{i}.log", 'rb') as f:
            f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 65536))
            tail = f.read().decode(errors='ignore')
    except Exception:
        return False
    ok = tail.rfind('NG Setup procedure is successful')
    seg = tail[ok:] if ok >= 0 else tail
    return seg.count('Uplink data failure, PDU session not found') >= min_hits

def _ue_proc_exists(i):
    try:
        n = int(sp.run(['pgrep', '-cf', rf'nr-ue\.real -c .*mue-{i}\.yaml'],
                       capture_output=True, text=True, timeout=5).stdout.strip() or 0)
    except Exception:
        n = 0
    return n > 0

def ensure_gnbs(quiet=False):
    """(docstring removed)"""
    if _BOUNCE3_PENDING:
        _live0 = _live_ngap_gnbs()
        for i in list(_BOUNCE3_PENDING):
            if gnb_ip(i) in _live0 and not _ue_proc_exists(i):
                cmd = f"{hbo.UERANSIM_DIR}/build/nr-ue -c {hbo.UE_CFG_TMPL.format(i=i)} -n 1"
                v22.fire_and_forget(f"echo {shlex.quote(v22.SUDO_PW)} | sudo -S -p '' {cmd}",
                                    log_path=f"/tmp/hbo-ue-{i}.log")
                _BOUNCE3_RESPAWNED[i] = time.time(); _BOUNCE3_PENDING.pop(i, None)
                P(f"bounce3: UE-{i} respawned (deferred; gNB NG live now, +{time.time() - _BOUNCE3_RESPAWNED[i]:.0f}s)")
            elif time.time() - _BOUNCE3_PENDING[i] > 600:
                _BOUNCE3_PENDING.pop(i, None)
                P(f"bounce3: UE-{i} deferred respawn expired (gNB never live) — left to reaper/arrivals")
    """All MAX_UE gNBs up with a LIVE NG association.
    A standing gNB whose SCTP died (AMF restart) never retries on its own —
    bounce it. Also called once per trace minute (quiet=True): daemon vyos
    scale-in can flap NGAP SCTP and UERANSIM gNB aborts on association loss
    ("terminate called recursively", never returns) — without in-run healing
    the idx's arrivals fail for the rest of the run (2026-08-22: 8 dead gNBs,
    10-UE arrival backlog by min14). Healthy cost = one ss scan."""
    for round_ in range(3):
        live = _live_ngap_gnbs()
        bad = [i for i in range(MAX_UE) if gnb_ip(i) not in live]

        for i in range(MAX_UE):
            if i in bad:
                continue
            try:
                n = int(sp.run(['pgrep', '-cf',
                                rf'nr-gnb\.real -c .*mgnb-{i}\.yaml'],
                               capture_output=True, text=True,
                               timeout=5).stdout.strip() or 0)
            except Exception:
                n = 1
            if n > 1:
                P(f"gNB-{i}: {n} duplicate instances — killing all, respawning one")
                bad.append(i)
            elif _gnb_ng_dead_by_log(i):

                P(f"gNB-{i}: NG dead by log marker (SCTP still ESTAB) — bouncing")
                bad.append(i)
            elif (_gnb_pdu_lost_by_log(i) and _ue_proc_exists(i)
                  and time.time() - _BOUNCE3_RESPAWNED.get(i, 0) > 180):
                P(f"gNB-{i}: stale PDU session by log marker (UE alive, uplink PDU-not-found) — bounce3")
                bad.append(i)
        bad.sort()
        if not bad:
            if not quiet:
                P("all gNBs NG-established")
            return
        P(f"gNBs without live NG (round {round_}): {bad} — bouncing")

        b3 = [i for i in bad if _ue_proc_exists(i)]
        procs = []
        for i in b3:
            try:
                import shutil as _sh
                if os.path.exists(f"/tmp/hbo-ue-{i}.log"):
                    _sh.copyfile(f"/tmp/hbo-ue-{i}.log", f"/tmp/hbo-ue-{i}.{time.strftime('%H%M%S')}.lost.log")
            except Exception:
                pass
            try:
                procs.append(sp.Popen([NR_CLI, imsi_of(i), '-e', 'deregister switch-off'],
                                      stdout=sp.DEVNULL, stderr=sp.DEVNULL))
            except Exception:
                pass
        if b3:
            P(f"bounce3: switch-off UE {b3} before gNB bounce")
            time.sleep(3)
            for pr in procs:
                try:
                    pr.kill()
                except Exception:
                    pass
            for i in b3:
                v22._pkill_pattern_root(rf"nr-ue(\.real)? -c .*mue-{i}\.yaml")

        try:
            _b3_old = {i: load_state()[1].get(i) for i in b3}
        except Exception:
            _b3_old = {}
        ng_t = {}
        for i in bad:
            _preserve_gnb_log(i)
            v22._pkill_pattern_root(rf"nr-gnb(\.real)? -c .*mgnb-{i}\.yaml")
        time.sleep(1)
        for i in bad:
            v22.fire_and_forget(
                f"{hbo.UERANSIM_DIR}/build/nr-gnb -c {hbo.GNB_CFG_TMPL.format(i=i)}",
                log_path=f"/tmp/hbo-gnb-{i}.log")
            # SERIAL: wait this gNB's NG before starting the next. A mass
            # bounce (0.3s stagger) loses 30-50% of the simultaneous INITs
            # and SCTP init-retrans exhaustion closes the socket for good
            # (the gNB never retries); one-at-a-time establishes in <1s each.
            for _ in range(8):
                time.sleep(1)
                if gnb_ip(i) in _live_ngap_gnbs():
                    break
            ng_t[i] = time.time()

        for i in b3:
            _oip = _b3_old.get(i)
            if not _oip:
                continue
            if _departures_not_released({i: _oip}, tries=2, gap=3):
                _dnn = {0: 'internet', 2: 'internet2', 3: 'internet3', 4: 'internet4', 5: 'internet5', 6: 'internet6', 7: 'internet7', 8: 'internet8'}.get(int(_oip.split('.')[2]), 'internet')
                P(f"bounce3: UE-{i} old session {_oip} STILL on slot after switch-off — recovering (re-register + switch-off)")
                _recover_lost_departure(i, _dnn, _oip)
            else:
                P(f"bounce3: UE-{i} old session {_oip} released ✓")

        for i in b3:
            wait = BOUNCE3_GAP_S - (time.time() - ng_t.get(i, time.time()))
            if wait > 0:
                time.sleep(wait)
            if gnb_ip(i) not in _live_ngap_gnbs():
                _BOUNCE3_PENDING[i] = time.time()
                P(f"bounce3: gNB-{i} NG not up after wait — UE-{i} respawn deferred")
                continue
            cmd = f"{hbo.UERANSIM_DIR}/build/nr-ue -c {hbo.UE_CFG_TMPL.format(i=i)} -n 1"
            v22.fire_and_forget(f"echo {shlex.quote(v22.SUDO_PW)} | sudo -S -p '' {cmd}",
                                log_path=f"/tmp/hbo-ue-{i}.log")
            _BOUNCE3_RESPAWNED[i] = time.time()
            P(f"bounce3: UE-{i} respawned at NG+{time.time() - ng_t.get(i, time.time()):.0f}s")
        time.sleep(2)
    live = _live_ngap_gnbs()
    bad = [i for i in range(MAX_UE) if gnb_ip(i) not in live]
    if bad:
        P(f"WARN gNBs still without NG after 3 rounds: {bad}")

_MEAS_OK = {}

def ensure_vyos_measurement_mode(pool, force=False):
    """(docstring removed)"""
    import concurrent.futures as _f

    def one(v):
        mgmt = mlib.VYOS.get(v)
        if not mgmt:
            return
        if not force and _MEAS_OK.get(v):
            chk = sp.run(
                f"timeout 12 sshpass -p $VYOS_PASS ssh -n -o StrictHostKeyChecking=no "
                f"-o UserKnownHostsFile=/dev/null vyos@{mgmt} "
                f"'sudo vppctl show ip fib 10.0.1.144/32 2>/dev/null | grep -c ipip'",
                shell=True, capture_output=True, text=True)
            if chk.returncode == 0 and (chk.stdout.strip() or '0') != '0':
                return   # routes present — no config writes this minute
            P(f"  vyos {v}: gnb tunnel route missing on verify — re-asserting")
        if T.SECGW_MODE:
            # SecGW(Phase-2 IPsec): DL for the measurement gnb range rides the
            # ESP tunnel to the SEG (encrypt), NOT a plaintext neighbor pin —
            # the SEG decrypts and forwards to the TRex VF. CLI /32 routes
            # outrank adj-fib so any stale TRex-MAC neighbors are inert.
            # .100 stays split by ABF below (TCP/ICMP/SCTP -> PF); only its
            # UDP (GTP-U DL of eupf-0's UEs) follows the tunnel route.

            neigh = 'T=$(sudo vppctl show ipsec tunnel | grep -o "^ipip[0-9]*" | head -1)\n'
            neigh += '[ -z "$T" ] && { echo NO-TUNNEL; exit 3; }\n'
            neigh += '\n'.join(
                f'sudo vppctl ip route add 10.0.1.{n}/32 via $T'
                for n in range(100, 145) if n != 108)
        else:
            neigh = '\n'.join(
                f"sudo vppctl set ip neighbor eth1 10.0.1.{n} "
                f"{mlib.TREX_VF_MAC} static"
                for n in range(100, 145) if n != 108)
        # ABF v2: the policy's next-hop must be the phantom .99 (pinned to the
        # sender PF MAC, never touched by measurement mode) — anchoring it on
        # .100 poisons the adjacency the moment the line above rewrites the
        # .100 neighbor to TRex, blackholing ALL NGAP DL + every API reply
        # that rides this VyOS (run#3's 2-min-death real mechanism). acl also
        # returns TCP/ICMP replies bound for the dev box (.100) to the PF —
        # eupf API and diagnostics — while UDP (GTP-U DL) stays on the
        # measurement neighbors.
        script = f"""{neigh}
sudo vppctl set ip neighbor eth1 10.0.1.99 {mlib.SENDER_PF_MAC} static
if ! sudo vppctl show abf policy | grep -q 10.0.1.99; then
  sudo vppctl set acl-plugin acl permit proto 132 dst 10.0.1.96/27, permit proto 132 dst 10.0.1.128/28, permit proto 6 dst 10.0.1.100/32, permit proto 1 dst 10.0.1.100/32 tag ngap-api-pf-v2
  A=$(sudo vppctl show acl-plugin acl | grep ngap-api-pf-v2 | tail -1 | awk '{{print $2}}')
  sudo vppctl abf attach ip4 del policy 10 eth1
  sudo vppctl abf policy del id 10 acl 0 via 10.0.1.100 eth1
  sudo vppctl abf policy add id 10 acl "$A" via 10.0.1.99 eth1
  sudo vppctl abf attach ip4 policy 10 eth1
fi
"""
        import base64
        b64 = base64.b64encode(script.encode()).decode()
        r = sp.run(
            f"timeout 30 sshpass -p $VYOS_PASS ssh -o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null vyos@{mgmt} "
            f"'echo {b64} | base64 -d | bash'",
            shell=True, capture_output=True)
        _MEAS_OK[v] = (r.returncode == 0)
    with _f.ThreadPoolExecutor(3) as ex:
        list(ex.map(one, pool))

def regen_hairpin():
    """(docstring removed)"""
    try:
        r = sp.run([sys.executable, '/home/user/experiment/p2/gen_hairpin_rules.py'],
                   capture_output=True, text=True, timeout=120)
        P(f'  hairpin regen: {(r.stdout or r.stderr).strip()[-100:]}')
    except Exception as e:
        P(f'  hairpin regen failed: {e}')

OCT_DNN = ((38, 'internet'), (31, 'internet2'), (32, 'internet3'),
           (33, 'internet4'), (34, 'internet5'), (35, 'internet6'),
           (36, 'internet7'), (37, 'internet8'))
OCT_DNN_NAME = dict(OCT_DNN)

def host_cpu_snap():
    """HOST-truth per-VM CPU from the Harvester-side sampler (v2, 5s cadence).
    Guest jiffy accounting loses 40-60% of wall time under softirq storm
    (2026-07-05 finding: node_exporter undercounts ~4x), so per-VM and
    per-datapath-vCPU cores are read from qemu /proc on the host instead.
    Returns {} on any failure — the run must never stall on this."""
    r = sp.run("timeout 5 sshpass -p $SSH_PASS ssh -o StrictHostKeyChecking=no "
               "rancher@10.0.0.193 cat /tmp/hostcpu_now.json",
               shell=True, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {}

def probe_slots():
    """{octet: dnn} of eupf slots whose API answers right now. Serves both as
    the DNN pool for arrivals AND as the reachability set for dead-UE
    detection: a UE may only be declared dead if its slot RESPONDED yet holds
    no session for it — teids_from_eupf silently skips unreachable slots, so
    treating a missing teid alone as death would mass-reap healthy UEs during
    an eupf pod restart/drain."""
    return {o: d for o, d in OCT_DNN if mlib.xs_safe(o, tries=1, timeout=2)}

def slot_octet(ue_ip):
    n = int(ue_ip.split('.')[2])
    return 38 if n == 0 else 29 + n

def spawn_ue_only(idx, dnn, timeout=40):
    """Arrival: nr-ue via the standing gNB. Returns (ue_ip, teid, tun) or raises."""
    hbo.set_ue_dnn(idx, dnn)
    logf = f"/tmp/hbo-ue-{idx}.log"
    # fire_and_forget opens log_path with mode "w" — the log is truncated on
    # every spawn, so the fresh registration's TUN line is simply the first
    # one in the file (counting against the OLD file's line count deadlocked).
    cmd = f"{hbo.UERANSIM_DIR}/build/nr-ue -c {hbo.UE_CFG_TMPL.format(i=idx)} -n 1"
    v22.fire_and_forget(f"echo {shlex.quote(v22.SUDO_PW)} | sudo -S -p '' {cmd}",
                        log_path=logf)
    t0 = time.time()
    ip = tun = None
    while time.time() - t0 < timeout:
        time.sleep(2)
        lg = open(logf).read() if os.path.exists(logf) else ''
        hits = re.findall(r'TUN interface\[(uesimtun\d+), (10\.45\.[0-9.]+)\]', lg)
        if hits:
            tun, ip = hits[-1]
            break
    if not ip:
        raise RuntimeError(f'UE {idx} tun timeout')
    for _ in range(8):
        ts = teids_from_eupf([ip])
        if ts:
            t = ts[0]
            t['gnb_ip'] = gnb_ip(idx)
            return ip, t, tun
        time.sleep(2)
    raise RuntimeError(f'UE {idx} teid not found')

_VY_DP_READY = {}   # v -> seen-timestamp of the VM instance that passed verify

_VY_PING_FAIL = {}

def ready_pool_verified(seen, prev_pool):
    """(docstring removed)"""
    pool = vyos_ready_pool(seen)
    out = []
    for v in pool:
        if v in (prev_pool or ()) or vyos_dataplane_ready(v, seen.get(v), force=True):
            out.append(v)
    return out

def vyos_dataplane_ready(v, seen_ts, force=False):
    """(docstring removed)"""
    if not force and _VY_DP_READY.get(v) == seen_ts:
        return True
    ensure_vyos_measurement_mode([v], force=True)

    mgmt = mlib.VYOS.get(v)

    fix = ' '.join(f'sudo vppctl ip route del 10.0.1.{n}/32 via ;' for n in range(100, 145) if n != 108)
    r = sp.run(
        f"timeout 40 sshpass -p $VYOS_PASS ssh -n -o StrictHostKeyChecking=no "
        f"-o UserKnownHostsFile=/dev/null vyos@{mgmt} "
        f"'d=$(sudo vppctl show ip fib 10.0.1.144/32 2>/dev/null | grep -c deag); "
        f"if [ \"$d\" != 0 ]; then {fix} echo ECMP-FIXED; fi; "
        f"[ -f /run/hhro-vyos-provisioned ] && echo PROV; "
        f"echo BOOT=$(cat /proc/sys/kernel/random/boot_id); "
        f"echo $(sudo vppctl show ip fib 10.0.1.144/32 2>/dev/null | grep -c ipip) "
        f"$(sudo vppctl show ip fib 10.0.1.144/32 2>/dev/null | grep -c deag)'",
        shell=True, capture_output=True, text=True)
    parts = (r.stdout.split() or ['0', '1'])
    if 'ECMP-FIXED' in r.stdout:
        P(f"  vyos {v}: ECMP poison (deag path on gnb /32) removed")
    ok = r.returncode == 0 and len(parts) >= 2 and parts[-2] != '0' and parts[-1] == '0'

    if ok and 'PROV' not in r.stdout and v != '10.0.1.4':
        ok = False
        P(f"  vyos {v}: provisioning not finished (no marker) — held out")
    elif not ok:
        P(f"  vyos {v}: dataplane NOT ready (gnb routes missing) — held out")
    mb = re.search(r'BOOT=([0-9a-f-]+)', r.stdout or '')
    if mb:
        _VY_BOOT[v] = mb.group(1)
    if ok:
        _VY_DP_READY[v] = seen_ts
        P(f"  vyos {v}: dataplane ready (marker {'present' if 'PROV' in r.stdout else 'absent/anchor'}, boot {mb.group(1)[:8] if mb else '?'})")
    return ok

def vyos_enc_sentinel(pool, ue_vyos, prev, ue_gnb=None):
    """(docstring removed)"""
    cur = {}
    assigned = {}
    for i, v in (ue_vyos or {}).items():
        assigned[v] = assigned.get(v, 0) + 1
    _live_ng = _live_ngap_gnbs() if ue_vyos else set()
    for v in list(pool):
        mgmt = mlib.VYOS.get(v)

        r = sp.run(
            f"timeout 10 sshpass -p $VYOS_PASS ssh -n -o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null vyos@{mgmt} "
            "'I=$(sudo vppctl show ipsec sa 2>/dev/null | grep \"spi 71\" "
            "| head -1 | tr -d \"[]\" | cut -d\" \" -f1); "
            "sudo vppctl show ipsec sa $I 2>/dev/null | grep \"outbound seq\"; "
            "echo BOOT=$(cat /proc/sys/kernel/random/boot_id)'",
            shell=True, capture_output=True, text=True)
        mb = re.search(r'BOOT=([0-9a-f-]+)', r.stdout or '')
        if mb:
            if _VY_BOOT.get(v) not in (None, mb.group(1)):
                P(f"  vyos {v}: boot_id changed (VM recreated on same IP) — evicting for re-verify")
                _VY_BOOT[v] = mb.group(1)
                _VY_DP_READY.pop(v, None)
                pool.remove(v)
                continue
            _VY_BOOT[v] = mb.group(1)
        m2 = re.search(r'outbound seq\s+(\d+)', r.stdout or '')
        if not m2:
            continue
        cur[v] = int(m2.group(1))
        if (v in prev and assigned.get(v, 0) > 0
                and cur[v] == prev[v] and v != '10.0.1.4'):

            alive = sum(1 for i, vv in (ue_vyos or {}).items()
                        if vv == v and (ue_gnb or {}).get(i) in _live_ng)
            if WARMIN_RUN or alive == 0:
                P(f"  vyos {v}: enc seq FROZEN with {assigned[v]} UEs assigned "
                  f"(alive-NG {alive}; {'warm-in' if WARMIN_RUN else 'no live UE'}) — record-only, not evicted")
                continue
            P(f"  vyos {v}: enc seq FROZEN with {assigned[v]} UEs assigned (alive-NG {alive}) "
              f"— evicting from pool (dataplane re-verify next minute)")
            _VY_DP_READY.pop(v, None)
            pool.remove(v)
    return cur

def vyos_ready_pool(seen):
    """VyOS data-IPs eligible for stream affinity. mgmt ping alone is NOT
    readiness — a booting VyOS answers mgmt ~60-90s before its ABF/NAT
    config converges (run#13 min17: one UE affinitied to a ping-ready
    vyos-1 = 60s DL blackhole, a 7.92% minute; min21-22 same with vyos-2).
    Admission: pingable for >=90s continuously, OR the agent's uemap
    already routes UEs through it (the daemon's readiness gate passed),
    OR it is vyos-0 (permanent anchor)."""
    now = time.time()
    for v in mlib.VYOS:
        ok = sp.run(f"timeout 2 ping -c1 -W1 {mlib.VYOS[v]}", shell=True,
                    capture_output=True).returncode == 0
        if ok:
            seen.setdefault(v, now)
            _VY_PING_FAIL[v] = 0
        else:

            _VY_PING_FAIL[v] = _VY_PING_FAIL.get(v, 0) + 1
            if _VY_PING_FAIL[v] >= 3 and v in seen:
                P(f"  vyos {v}: mgmt ping failed x{_VY_PING_FAIL[v]} — evicting from ready pool")
            if _VY_PING_FAIL[v] >= 3:
                seen.pop(v, None)
                _VY_DP_READY.pop(v, None)
    try:
        assigned = set(json.load(open('/tmp/uemap.json'))
                       .get('assign', {}).values())
    except Exception:
        assigned = set()

    #

    #

    #

    #

    settle = float(os.environ.get('VY_SETTLE_S', 5))
    draining = vy_draining()
    for v in draining:
        seen.pop(v, None)
        _VY_DP_READY.pop(v, None)
    pool = [v for v in mlib.VYOS
            if v in seen and v not in draining
            and (v == '10.0.1.4'
                 or (now - seen[v] >= settle
                     and vyos_dataplane_ready(v, seen[v])))]

    _ready = pool or ['10.0.1.4']
    _drn = vy_draining()
    return [v for v in _ready if v not in _drn]

def slot_all_ips(slots):
    """ALL session ue_ips across the answering slots — UNFILTERED. This is
    the zombie-visibility source: teids_from_eupf(known_ips) can never show
    a session no live UE owns (it filters to the ips you ask about), which
    is exactly what a leaked old-anchor session is."""
    import urllib.request
    ips = {}
    for o in slots:
        try:
            d = json.load(urllib.request.urlopen(
                f'http://10.0.1.{o}:8080/api/v1/pfcp_sessions', timeout=4)) or []
        except Exception:
            continue
        for s in d:
            for p in (s.get('PDRs') or {}).values():
                ip = p.get('Ipv4')
                if ip:
                    ips.setdefault(ip, o)
    return ips

def zombie_owner(stale_ip, active, busy):
    """Which live UE's ps-list still carries the stale session for stale_ip?
    Returns (idx, [stale PDU session ids]) or (None, [])."""
    for i in active:
        if i in busy:
            continue
        try:
            r = sp.run([NR_CLI, imsi_of(i), '-e', 'ps-list'],
                       capture_output=True, text=True, timeout=8)
        except Exception:
            continue
        out = r.stdout or ''
        if stale_ip not in out:
            continue
        stale, cur = [], None
        for ln in out.splitlines():
            mm = re.match(r'PDU Session(\d+):', ln.strip())
            if mm:
                cur = mm.group(1)
            if 'address:' in ln and cur and \
                    ln.split('address:')[1].strip() == stale_ip:
                stale.append(cur)
        return i, stale
    return None, []

def deregister_ue(idx):
    """Departure: proper NAS deregistration, then reap the process."""
    imsi = imsi_of(idx)
    # SWITCH-OFF, not normal: UERANSIM auto RE-REGISTERS ~500ms after a
    # 'deregister normal' (dereg 204 -> fresh registration + PDU) — every
    # departure then got pkilled mid-new-session = the zombie-session factory
    # behind run#11's scale-in deadlock and every parking orphan. switch-off
    # deregisters AND exits the UE process itself (verified: sessions=0,
    # proc gone, no respawn).
    sp.run([NR_CLI, imsi, '-e', 'deregister switch-off'],
           capture_output=True, timeout=10)
    time.sleep(3)
    v22._pkill_pattern_root(rf"nr-ue(\.real)? -c .*mue-{idx}\.yaml")  # backstop only

def load_state():
    try:
        teids = json.load(open('/tmp/m32.json'))
        um = json.load(open('/tmp/uemap.json'))
        return teids, {int(k): v for k, v in um['idx_ip'].items()}
    except Exception:
        return [], {}

def save_state(teids, idx_ip, assign):
    json.dump(teids, open('/tmp/m32.json', 'w'))
    json.dump({'assign': {str(k): v for k, v in assign.items()},
               'idx_ip': {str(k): v for k, v in idx_ip.items()}},
              open('/tmp/uemap.json', 'w'))

def main():
    ensure_gnbs()
    m = T.TRexTrafficManager(vyos_mac="02:00:00:0a:0a:04")
    m.connect()
    # unified 1 Hz sidecar: ue/tx/dl/pf/e2e/latency on one time base
    m.sample_ue = 0
    m.start_sampler_1s(OUT.replace('.csv', '_1s.csv'))
    import threading as _th
    _hb_stop = _th.Event()
    _th.Thread(target=_ul_pool_heartbeat, args=(_hb_stop,), daemon=True).start()

    teids, idx_ip = load_state()
    # ground truth: which of our UEs actually hold sessions right now
    live_ips = {t['ue_ip'] for t in teids_from_eupf(list(idx_ip.values()))} \
        if idx_ip else set()
    active = [i for i, ip in idx_ip.items() if ip in live_ips]
    m.sample_ue = len(active)
    P(f"start: {len(active)} UEs already active")
    # reap stale nr-ue procs for idxs we are NOT resuming — a leftover process
    # would double-register the imsi when the arrivals loop reuses that idx
    for i in range(MAX_UE):
        if i not in active:
            v22._pkill_pattern_root(rf"nr-ue(\.real)? -c .*mue-{i}\.yaml")

    w = csv.writer(open(OUT, 'w', buffering=1))
    w.writerow(['min', 'target_ue', 'active_ue', 'offered_pps', 'txreal',
                'dl', 'pf_rx', 'e2e_pct', 'eupf_cov', 'spawn_fail', 'dead',
                'lat_avg_us', 'lat_p50_us', 'lat_p95_us', 'lat_p99_us',
                'lat_max_us', 'lat_n',
                # v6: replicas + HOST-truth CPU (cores; dp = pinned datapath
                # vCPUs only). w0 is the CP host: its dp = eupf slots 0/3.
                'vyos_n', 'worker_n',
                'host_w0', 'host_w1', 'host_w2', 'host_w3',
                'hostdp_w0', 'hostdp_w1', 'hostdp_w2', 'hostdp_w3',
                'host_vyos_sum',

                'vy_miss_4', 'vy_miss_5', 'vy_miss_6',
                'vy_drop_4', 'vy_drop_5', 'vy_drop_6',

                *[f'slot_oob_{o}' for o in mlib.UPFS],
                *[f'slot_txf_{o}' for o in mlib.UPFS],
                'slot_miss_pct', 'covered_s'])

    dnn_of = {}
    for i in active:
        t = next((x for x in teids if x['ue_ip'] == idx_ip.get(i)), None)
        if t:
            oct_ = int(t['upf_ip'].rsplit('.', 1)[1])
            dnn_of[i] = {38: 'internet', 31: 'internet2', 32: 'internet3',
                         33: 'internet4', 34: 'internet5', 35: 'internet6',
                         36: 'internet7', 37: 'internet8'}[oct_]

    t0 = time.time()
    teid_cache = {}   # ue_ip -> last known teid entry (carry-forward)
    zstrikes = {}     # stale ue_ip -> consecutive sightings (zombie sweeper)
    reaped_recently = set()

    pg_map, pg_base, dp_black = [], {}, set()

    def pg_snapshot():

        try:
            st = m.client.get_pgid_stats() or {}
            fs = st.get('flow_stats', {})
        except Exception:
            return {}
        out = {}
        for k, v in fs.items():
            try:
                ki = int(k)
            except Exception:
                continue
            if ki < 100:
                continue
            try:
                out[ki] = ((v.get('tx_pkts') or {}).get('total', 0),
                           (v.get('rx_pkts') or {}).get('total', 0))
            except Exception:
                pass
        return out
    arr_fails = {}
    missing_slot_since = {}
    dead_strikes = {}
    prev_hairpin_ips = set()
    prev_vy_ready = set()
    # vyos warm-up quarantine state: anything alive NOW predates the run and
    # is converged — backdate so vyos_ready_pool admits it immediately
    vy_seen = {}
    vy_encseq = {}
    vyos_ready_pool(vy_seen)
    for v in list(vy_seen):
        vy_seen[v] = time.time() - 9999
    prev_win_end = None
    for minute, target in enumerate(UE_SEQ):
        t_min = time.time()
        deadline = t0 + 60 * (minute + 1)

        win = mlib.Window(m)
        m.clear_latency()
        win.open(carry=prev_win_end)
        ensure_gnbs(quiet=True)   # in-run self-heal, see docstring
        # agent-job baseline BEFORE boundary work: our boundary save_state can
        # stomp an agent write that lands mid-boundary (B3 min1: rehome done
        # during boundary -> uemap/m32 overwritten with pre-move state -> all
        # in-window detectors blind, 10.7% minute). With the baseline taken
        # here, that job still flips the signature for the in-window poll.
        pre_boundary_job = agent_job_sig()
        # Ground-truth rebuild (run#2 died on a shared-file race: an agent
        # rehome job rewrote uemap.json between our read and use, dropping a
        # just-arrived UE). The UE logs + the eUPF PDR maps ARE the truth:
        #   ip[i]  = last TUN line of /tmp/hbo-ue-i.log
        #   teids  = teids_from_eupf(ips)  (absorbs daemon rehomes too)
        idx_ip = {}
        idx_tun = {}
        for i in list(active):
            try:
                lg = open(f"/tmp/hbo-ue-{i}.log").read()
                hits = re.findall(r'TUN interface\[(uesimtun\d+), (10\.45\.[0-9.]+)\]', lg)
                if hits:
                    idx_tun[i], idx_ip[i] = hits[-1]
            except Exception:
                pass

        nas_dead = set()
        def _nas_sess(i):
            try:
                r = sp.run([NR_CLI, imsi_of(i), '-e', 'ps-list'],
                           capture_output=True, text=True, timeout=8)
                sess = []
                for m2 in re.finditer(
                        r'PDU Session(\d+):\s*\n(.*?)(?=PDU Session\d+:|\Z)',
                        r.stdout or '', re.S):
                    blk = m2.group(2)
                    ad = re.search(r'address:\s*(10\.45\.[0-9.]+)', blk)
                    st = re.search(r'state:\s*(\S+)', blk)
                    sess.append((m2.group(1),
                                 ad.group(1) if ad else None,
                                 st.group(1) if st else '?'))
                return i, sess
            except Exception:
                return i, None
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=8) as _ex:
                nas_res = list(_ex.map(_nas_sess, list(active)))
        except Exception:
            nas_res = []
        _busy_now = agent_busy_ues()
        _ag_ips_b = agent_ue_ips()
        seg_health_kick(minute)

        def _slot_held(ips, only=None):
            q = [ip for ip in dict.fromkeys(ips or [])
                 if ip and (only is None or slot_octet(ip) in only)]
            if not q:
                return {}
            try:
                return {t['ue_ip']: t for t in teids_from_eupf(q)}
            except Exception:
                return {}
        nas_ips = {}
        for i, sess in nas_res:
            if sess is None:
                nas_ips[i] = None
                continue
            acts = [(sid, ad) for sid, ad, st in sess
                    if st == 'PS-ACTIVE' and ad]
            nips = [ad for _, ad in acts]
            nas_ips[i] = nips
            if not nips:
                if REAPERS:
                    nas_dead.add(i)
                    P(f"min{minute}: UE-{i} NAS has no PDU session — will reap")
                else:
                    P(f"min{minute}: [record-only] UE-{i} NAS has no PDU session")
                continue
            if idx_ip.get(i) not in nips:

                _aip = _ag_ips_b.get(i)
                if _aip in nips:
                    _to, _why = _aip, ' (agent)'
                else:
                    _h = _slot_held(nips)
                    _to = next((ip for ip in nips if ip in _h), nips[-1])
                    _why = ' (slot-held)' if _to in _h else ' (last-seen)'
                P(f"min{minute}: UE-{i} idx_ip {idx_ip.get(i)} ∉ NAS {nips}"
                  f" — healed to {_to}{_why}")
                idx_ip[i] = _to

            if len(acts) > 1 and i not in _busy_now:

                keep = None
                try:
                    import urllib.request
                    _ag = json.load(urllib.request.urlopen(
                        'http://127.0.0.1:9801/ues?live=1', timeout=3))
                    keep = (_ag.get('ues', {}).get(str(i)) or {}).get('ue_ip')
                except Exception:
                    pass
                if not keep:
                    keep = idx_ip.get(i)
                if keep in nips and idx_ip.get(i) != keep:
                    P(f"min{minute}: UE-{i} 本尊={keep}(agent)— idx_ip healed")
                    idx_ip[i] = keep
                for sid, ad in acts:
                    if ad != keep:
                        if not REAPERS:
                            P(f"min{minute}: [record-only] UE-{i} phantom session "
                              f"{ad} (sid {sid}) — NOT released")
                            continue
                        P(f"min{minute}: UE-{i} phantom session {ad} "
                          f"(sid {sid}) — releasing")
                        try:
                            sp.run([NR_CLI, imsi_of(i), '-e',
                                    f'ps-release {sid}'],
                                   capture_output=True, timeout=8)
                        except Exception:
                            pass
        teids = teids_from_eupf(list(idx_ip.values())) if idx_ip else []
        by_ip = {t['ue_ip']: t for t in teids}
        for i, ipx in idx_ip.items():
            if ipx in by_ip:
                by_ip[ipx]['gnb_ip'] = gnb_ip(i)
                # dnn_of must track agent moves, or the arrivals' least-loaded
                # pick reads a stale ledger: every rehome off internet made
                # .38 look empty, so arrivals re-piled it — .38 ran 5-6 UEs
                # (cap 4) in EVERY controller run; at ring 1024 that transient
                # concentration is hard oob loss (#13 min25 9.49%), where 8192
                # buffers absorbed it (run#12).
                oct_ = int(by_ip[ipx]['upf_ip'].rsplit('.', 1)[1])
                dnn_of[i] = OCT_DNN_NAME[oct_]
        slots = probe_slots()
        busy = agent_busy_ues()
        # teid carry-forward: a slot mid-restart/scale-churn answers nothing —
        # its UEs' sessions are almost always intact, just unobservable this
        # minute. Reuse the last known teid so their streams stay up (run#4:
        # churn minutes silently dropped up to 10 UEs' offered load — the
        # TX-vs-UE-count gap in the workload figure). Never applied when the
        # slot DID answer (a missing teid there means dead/rehomed).
        for i in list(active):
            ipx = idx_ip.get(i)
            if ipx and ipx not in by_ip and slot_octet(ipx) not in slots \
                    and i not in busy and ipx in teid_cache:
                by_ip[ipx] = teid_cache[ipx]
                teids.append(teid_cache[ipx])
        for t in teids:
            teid_cache[t['ue_ip']] = t
        # (c) dead-session handling: reap + let the arrivals loop below
        # re-establish (same minute, within the arrival budget). Guards:
        #   * only if the UE's slot API ANSWERED yet holds no session — an
        #     unreachable slot is measurement blindness, not death: keep the
        #     UE, it just contributes no stream this minute;
        #   * never a UE the agent is mid-rehome on (sessionless window).
        # A UE with no TUN line at all (broken process) is dead regardless.

        _now = time.time()
        for i in list(active):
            _ipx = idx_ip.get(i)
            if _ipx and slot_octet(_ipx) not in slots:
                missing_slot_since.setdefault(i, _now)
            else:
                missing_slot_since.pop(i, None)

        def _nas_alive(i):
            n = nas_ips.get(i)
            if n is None:
                return None
            for ip in n:
                if ip in by_ip:
                    if idx_ip.get(i) != ip:
                        P(f"min{minute}: UE-{i} idx_ip {idx_ip.get(i)} → {ip}"
                          f" (NAS session held by slot .{slot_octet(ip)}) — healed, not dead")
                        idx_ip[i] = ip
                    return True

            _h = _slot_held(n, only=slots)
            for ip in n:
                if ip in _h:
                    P(f"min{minute}: UE-{i} idx_ip {idx_ip.get(i)} → {ip}"
                      f" (NAS ip 實際由槽 .{slot_octet(ip)} 持有,by_ip 未涵蓋)"
                      f" — healed, not dead")
                    idx_ip[i] = ip
                    _h[ip]['gnb_ip'] = gnb_ip(i)
                    by_ip[ip] = _h[ip]
                    teids.append(_h[ip])
                    return True
            return False
        def _old_rule(i):
            return (idx_ip.get(i) is None
                    or (REAPERS and i in nas_dead)
                    or (REAPERS and i in dp_black)
                    or (slot_octet(idx_ip[i]) in slots
                        and idx_ip[i] not in by_ip)
                    or (_now - missing_slot_since.get(i, _now) > 120))
        dead = []
        for i in list(active):
            if i in busy:
                continue
            if time.time() - _BOUNCE3_RESPAWNED.get(i, 0) < 150 or i in _BOUNCE3_PENDING:
                continue
            al = _nas_alive(i)
            if al is True:
                dead_strikes.pop(i, None)
                continue
            if not _old_rule(i):
                dead_strikes.pop(i, None)
                continue
            if al is None and idx_ip.get(i) is not None:
                dead_strikes[i] = dead_strikes.get(i, 0) + 1
                if dead_strikes[i] < 2:
                    P(f"min{minute}: UE-{i} looks dead but NAS unknown — strike 1, keep")
                    continue
            dead_strikes.pop(i, None)
            dead.append(i)
        deaths = len(dead)
        for i in dead:
            missing_slot_since.pop(i, None)
            dp_black.discard(i)
        reaped_recently.update(dead)
        for i in dead:
            P(f"min{minute}: UE-{i} session dead (ground truth) — reaping for "
              f"re-establishment [idx_ip={idx_ip.get(i)} nas={nas_ips.get(i)} "
              f"agent={_ag_ips_b.get(i)} slot_in_slots={slot_octet(idx_ip[i]) in slots if idx_ip.get(i) else None} "
              f"in_by_ip={idx_ip.get(i) in by_ip} missing_for={int(_now - missing_slot_since.get(i, _now))}s]")
            stop_keepalive(i)
            # switch-off BEFORE pkill: a bare pkill leaves whatever SMF still
            # holds for this imsi as an ownerless zombie session (B2 min28:
            # 10.45.4.100/102, unkillable — no live UE to release through)
            try:
                sp.run([NR_CLI, imsi_of(i), '-e', 'deregister switch-off'],
                       capture_output=True, timeout=8)
            except Exception:
                pass
            v22._pkill_pattern_root(rf"nr-ue(\.real)? -c .*mue-{i}\.yaml")
            active.remove(i)
            m.sample_ue = len(active)
            dnn_of.pop(i, None)
            idx_ip.pop(i, None)
            idx_tun.pop(i, None)
        # (a) keepalive maintenance for survivors (tun re-resolved above —
        # rehome/respawn allocate a new uesimtunN)
        for i in active:
            if i in idx_tun:
                ensure_keepalive(i, idx_tun[i])

        # (d) zombie-session sweeper: a failed old-anchor release after a
        # rehome leaves a stale PFCP session behind (a ue_ip no live UE owns).
        # ONE zombie inflates every session-count controller and blinds their
        # scale-in thresholds (B4 dip: real 22 counted as 23 = no bite).
        # Ladder — 3 consecutive sightings: find the owner via ps-list and
        # retry the release; 5: switch-off rebuild of the owner (SMF drops
        # ALL its sessions, arrivals loop re-establishes it this minute).
        # Strikes make mid-rehome deferred releases (~30-90s legit) immune.
        cur_ips = set(idx_ip.values())
        swept = False
        zall = slot_all_ips(slots)   # unfiltered: sees sessions we don't own
        for zip_ in list(zstrikes):
            if zip_ not in zall or zip_ in cur_ips:
                zstrikes.pop(zip_, None)
        for zip_ in zall:
            if zip_ in cur_ips:
                continue
            zstrikes[zip_] = zstrikes.get(zip_, 0) + 1
            zn = zstrikes[zip_]
            # Ladder tightened 3/5 -> 1/3: the daemon's relief cycle is
            # 90-150s — with a 3-minute detection lag, one wedged-release UE
            # (UE-4's immortal psi-1) feeds phantom per-slot load faster than
            # the sweeper drains it, and the rebalancer chases the phantom
            # imbalance in a self-exciting move loop (attempt4: UE-4 ping-
            # ponged 6 slots, one zombie per hop, two slots pushed to 5 real
            # UEs). Phantoms must die inside ONE relief cycle.
            zowner, zstale = zombie_owner(zip_, active, busy)
            if zowner is None:
                P(f"min{minute}: zombie {zip_} (x{zn}) — no live owner found")
                continue
            if not REAPERS:
                P(f"min{minute}: [record-only] zombie {zip_} (x{zn}) on UE-{zowner}"
                  f" stale={zstale} — no action")
                continue
            if zn < 3:
                P(f"min{minute}: zombie {zip_} (x{zn}) on UE-{zowner} — "
                  f"ps-release {zstale}")
                for sid in zstale:
                    try:
                        sp.run([NR_CLI, imsi_of(zowner), '-e',
                                f'ps-release {sid}'],
                               capture_output=True, timeout=10)
                        swept = True
                    except Exception:
                        pass
            else:
                P(f"min{minute}: zombie {zip_} (x{zn}) on UE-{zowner} — "
                  f"switch-off rebuild")
                stop_keepalive(zowner)
                try:
                    deregister_ue(zowner)
                except Exception:
                    pass
                v22._pkill_pattern_root(rf"nr-ue(\.real)? -c .*mue-{zowner}\.yaml")
                if zowner in active:
                    active.remove(zowner)
                m.sample_ue = len(active)
                dnn_of.pop(zowner, None)
                idx_ip.pop(zowner, None)
                idx_tun.pop(zowner, None)
                zstrikes.pop(zip_, None)
                swept = True
                reaped_recently.add(zowner)
        fails = 0

        # --- departures (LIFO: most recent arrivals leave first) ---
        # switch-offs fire in PARALLEL then share ONE settle: the serial
        # per-UE 3s settle made 8 departures take ~24s, so session-count
        # controllers never saw the trough before the next ramp registered
        # (their scale-in window starved on tick alignment).
        leaving = []
        while len(active) > target:
            leaving.append(active.pop())
        if leaving:

            _leave_set = set(leaving)
            _leave_ips = {idx_ip.get(i) for i in leaving}
            _keep = [t for t in (m.teids or [])
                     if t.get('idx') not in _leave_set and t['ue_ip'] not in _leave_ips]
            if len(_keep) != len(m.teids or []):
                try:
                    m.teids = _keep
                    if _keep:
                        m.set_load(ues=len(_keep), pps_per_ue=PPS_PER_UE)
                    else:
                        m.stop()
                    P(f"min{minute}: streams withdrawn for {len(leaving)} departing UEs")
                except Exception as e:
                    P(f"  stream withdraw warn: {e}")
            for idx in leaving:
                P(f"min{minute}: UE-{idx} departs (dereg)")
                stop_keepalive(idx)
                try:
                    sp.run([NR_CLI, imsi_of(idx), '-e',
                            'deregister switch-off'],
                           capture_output=True, timeout=10)
                except Exception as e:
                    P(f"  dereg UE-{idx} failed: {e}")
            time.sleep(3)

            _leave_ip = {i: idx_ip.get(i) for i in leaving}
            _leave_dnn = {i: dnn_of.get(i) for i in leaving}
            stuck = _departures_not_released(_leave_ip)
            for idx in stuck:
                if time.time() > deadline - 25:
                    P(f"min{minute}: UE-{idx} dereg lost, no budget to recover — zombie {_leave_ip[idx]} left")
                    continue
                P(f"min{minute}: UE-{idx} dereg lost ({_leave_ip[idx]} still on slot; gNB NG dead?) — "
                  f"bounce mgnb-{idx} + re-register + switch-off")
                _recover_lost_departure(idx, _leave_dnn.get(idx) or 'internet', _leave_ip[idx])
            for idx in leaving:
                v22._pkill_pattern_root(rf"nr-ue(\.real)? -c .*mue-{idx}\.yaml")
                teids = [t for t in teids if t['ue_ip'] != idx_ip.get(idx)]
                idx_ip.pop(idx, None)
                dnn_of.pop(idx, None)
            m.sample_ue = len(active)

        # --- arrivals (lowest free idx; least-loaded active DNN) ---

        pool = [i for i in range(MAX_UE) if i not in active]
        pool.sort(key=lambda i: (i not in reaped_recently, i))
        adnns = list(slots.values()) or ['internet']

        pool.sort(key=lambda i: (arr_fails.get(i, 0) >= 2, i not in reaped_recently, i))
        while len(active) < target and pool:
            cutoff = 8 if pool[0] in reaped_recently else 20
            if time.time() > deadline - cutoff:
                P(f"min{minute}: arrival budget exhausted "
                  f"({target - len(active)} deferred to next minute)")
                break
            idx = pool.pop(0)
            if arr_fails.get(idx, 0) == 2:

                P(f"min{minute}: UE-{idx} fail streak — bouncing mgnb-{idx}")
                try:
                    v22._pkill_pattern_root(rf"nr-gnb(\.real)? -c .*mgnb-{idx}\.yaml")
                    time.sleep(1)
                    v22.fire_and_forget(
                        f"{hbo.UERANSIM_DIR}/build/nr-gnb -c {hbo.GNB_CFG_TMPL.format(i=idx)}",
                        log_path=f"/tmp/hbo-gnb-{idx}.log")
                    time.sleep(4)
                except Exception as e:
                    P(f"  gnb bounce warn: {e}")
            # occupancy from the slots' REAL pfcp sessions, not the dnn_of
            # ledger: a fresh slot's API can lag the boundary scrape, leaving
            # moved UEs booked on their OLD dnn — the ledger then under-counts
            # the new slot and over-counts the old one, and arrivals pile onto
            # a slot that is already full (min4 attempt3: .33 got 5 = 1.5M =
            # sustained oob). Refresh once per arrival (~100ms/slot).

            occ = {d: 0 for d in adnns}
            _live_ips = set(idx_ip.get(i) for i in active)
            for _t in teids:
                if _t['ue_ip'] in _live_ips:
                    _d2 = OCT_DNN_NAME.get(int(_t['upf_ip'].rsplit('.', 1)[1]))
                    if _d2 in occ:
                        occ[_d2] += 1

            for _mv_dnn in agent_inflight_move_dnns():
                if _mv_dnn in occ:
                    occ[_mv_dnn] += 1

            assoc_ok = []
            for d in adnns:
                _oct = next((o for o, n in OCT_DNN if n == d), None)
                try:
                    rr = sp.run(f"timeout 3 curl -s http://10.0.1.{_oct}:8080/api/v1/pfcp_associations",
                                shell=True, capture_output=True, text=True)
                    if 'NextSess' in (rr.stdout or ''):
                        assoc_ok.append(d)
                except Exception:
                    pass
            cand = [d for d in (assoc_ok or adnns)]
            _drn = slot_draining_dnns()
            if _drn and [d for d in cand if d not in _drn]:

                P(f"min{minute}: slot-drain exclude {sorted(set(cand) & _drn)}")
                cand = [d for d in cand if d not in _drn]   # never land on a slot being drained
            under = [d for d in cand if occ[d] < 4]
            dnn = min(under or cand, key=lambda d: occ[d])
            P(f"min{minute}: UE-{idx} arrives on {dnn}")
            try:
                ip, t, tun = spawn_ue_only(idx, dnn)
                idx_ip[idx] = ip
                teids = [x for x in teids if x['ue_ip'] != ip] + [t]
                dnn_of[idx] = dnn
                active.append(idx)
                reaped_recently.discard(idx)
                arr_fails.pop(idx, None)
                m.sample_ue = len(active)
                ensure_keepalive(idx, tun)
            except Exception as e:
                P(f"  UE-{idx} arrival failed: {e}")
                fails += 1
                arr_fails[idx] = arr_fails.get(idx, 0) + 1
                # the failed spawn may have registered + established before
                # dying (tun-parse/teid timeout) — dereg first or its session
                # leaks as an ownerless zombie
                try:
                    sp.run([NR_CLI, imsi_of(idx), '-e',
                            'deregister switch-off'],
                           capture_output=True, timeout=8)
                except Exception:
                    pass
                v22._pkill_pattern_root(rf"nr-ue(\.real)? -c .*mue-{idx}\.yaml")

        # --- rebuild streams + DL affinity on the CURRENT vyos fleet ---

        if swept and idx_ip:
            try:
                fresh = teids_from_eupf(list(idx_ip.values()))
                if fresh:
                    teids = fresh
                    P(f"min{minute}: post-sweep teid re-refresh ({len(teids)})")
            except Exception as e:
                P(f"min{minute}: post-sweep teid re-refresh failed: {e}")

        try:
            _ag_b2 = agent_ue_ips()
            _adopt = [(i, _ag_b2[i]) for i in active
                      if _ag_b2.get(i) and _ag_b2[i] != idx_ip.get(i)]
            if _adopt:
                _ft = {t['ue_ip']: t for t in teids_from_eupf([a for _, a in _adopt])}
                for i, a in _adopt:
                    if a in _ft:
                        _ft[a]['gnb_ip'] = gnb_ip(i)
                        P(f"min{minute}: UE-{i} idx_ip {idx_ip.get(i)} → {a}"
                          f" (agent 本尊,槽 .{slot_octet(a)} 持有)— adopted")
                        idx_ip[i] = a
                        teids = [t for t in teids if t['ue_ip'] != a] + [_ft[a]]
        except Exception as e:
            P(f"  agent-adopt warn: {e}")
        by_ip = {t['ue_ip']: t for t in teids}  # absorb this minute's arrivals
        act_teids = []
        for i in active:
            _t = by_ip.get(idx_ip.get(i))
            if _t:
                _t = dict(_t); _t['idx'] = i; act_teids.append(_t)
        act_idx = [i for i in active if by_ip.get(idx_ip.get(i))]
        # aliveness via MGMT ping + warm-up quarantine (vyos_ready_pool):
        # the data IP can't answer in measurement mode, and a freshly booted
        # VyOS pings on mgmt long before it forwards
        m.vyos_pool = ready_pool_verified(vy_seen, m.vyos_pool)
        ensure_vyos_measurement_mode(m.vyos_pool)

        vy_encseq = vyos_enc_sentinel(m.vyos_pool, getattr(m, 'ue_vyos', {}),
                                      vy_encseq,
                                      ue_gnb={k: t.get('gnb_ip') for k, t in enumerate(getattr(m, 'teids', []) or [])})

        cur_vy_ready = set(m.vyos_pool)
        if cur_vy_ready - prev_vy_ready:
            try:

                _bind_of = {'10.0.1.4': 'ipsec sa bind 111 0; ipsec sa bind 131 1',
                            '10.0.1.5': 'ipsec sa bind 112 5; ipsec sa bind 132 3',
                            '10.0.1.6': 'ipsec sa bind 113 2; ipsec sa bind 133 2',
                            '10.0.1.7': 'ipsec sa bind 114 3; ipsec sa bind 134 5'}
                binds = '; '.join(_bind_of[v] for v in sorted(cur_vy_ready - prev_vy_ready)
                                  if v in _bind_of)
                if binds:
                    sp.run("echo $SUDO_PASS | sudo -S bash -c " + shlex.quote(
                           '; '.join(f"vppctl -s /run/vpp/cli-seg.sock {c}"
                                     for c in binds.split('; '))),
                           shell=True, capture_output=True, timeout=30)
                P(f"  SEG SA rebind (new vyos: {sorted(cur_vy_ready - prev_vy_ready)}; only their SAs)")
            except Exception as e:
                P(f"  SEG SA rebind warn: {e}")
        prev_vy_ready = cur_vy_ready

        if len(act_teids) < len(active):
            miss = [i for i in active if not by_ip.get(idx_ip.get(i))]
            P(f"  ⚠mapping deficit: active={len(active)} mapped={len(act_teids)} "
              f"missing_idx={miss}")
        m.teids = act_teids
        m.ue_vyos = {}
        if act_teids:
            prime_dl_affinity(m, act_teids)
            m.set_load(ues=len(act_teids), pps_per_ue=PPS_PER_UE)
            pg_map = list(act_idx)
            pg_base = pg_snapshot()
            assign = {i: m.ue_vyos.get(i) for i in range(len(act_teids))}

            _tpos = {t['ue_ip']: k for k, t in enumerate(teids)}
            assign_save = {_tpos[t['ue_ip']]: assign[j]
                           for j, t in enumerate(act_teids)
                           if t['ue_ip'] in _tpos
                           and assign.get(j) is not None}
            save_state(teids, idx_ip, assign_save)
            assign_save_str = {str(k): v for k, v in assign_save.items()}
            try:
                mlib.worker_repoint(act_teids,
                                    lambda t: mlib.VMAC[assign[act_teids.index(t)]])
            except Exception as e:
                P(f"  repoint warn: {e}")

            publish_ul_pool(m)
        else:
            m.stop()
            publish_ul_pool(m)
            save_state(teids, idx_ip, {})
            assign_save_str = {}

        cur_ips = {t['ue_ip'] for t in teids}
        if cur_ips != prev_hairpin_ips and not HAIRPIN_STATIC:
            regen_hairpin()
            prev_hairpin_ips = cur_ips
        # inactive-gnb neighbor default -> sender PF MAC (2026-08-22): the w0
        # gnb-routes pin (.101-.145 -> enp14s0) makes the NEIGHBOR the decider
        # for NGAP DL too. A parked/inactive idx keeps its last assigned-vyos
        # MAC; when the daemon deletes that vyos the gNB's SCTP blackholes ->
        # UERANSIM aborts ("terminate called recursively") and that idx's
        # arrivals fail all run. Default every gnb WITHOUT an active teid to
        # the PF MAC (July NGAP-via-PF design); active ones keep their vyos
        # (ABF routes their non-UDP back to the PF). w0 only — workers w1-3
        # carry no NGAP and their GTP repoint is handled above.
        try:
            act_gnbs = {t['gnb_ip'] for t in act_teids}
            idle_cmds = '; '.join(
                f"ip neigh replace 10.0.1.{n} lladdr {mlib.SENDER_PF_MAC} dev {ifc}"
                for n in range(100, 145) if n != 108
                and f"10.0.1.{n}" not in act_gnbs
                for ifc in ('enp13s0', 'enp14s0'))
            sp.run(f"timeout 15 sshpass -p $SSH_PASS ssh -o StrictHostKeyChecking=no "
                   f"user@10.0.0.52 {shlex.quote('echo $SUDO_PASS | sudo -S bash -c ' + shlex.quote(idle_cmds))}",
                   shell=True, capture_output=True)
        except Exception as e:
            P(f"  idle-gnb neigh warn: {e}")

        # --- boundary work done; window has been open since minute top ---
        settle = time.time() - t_min
        # Mid-window rehome absorption: when a daemon rehome/drain job
        # finishes, the moved UEs' UL streams still carry their OLD teids
        # until the next set_load — up to 60s of per-UE blackhole that
        # dominated run#5's non-capacity loss (41% @ 8 UE). Poll the agent
        # and rebuild streams within ~5s of job completion, restarting the
        # window (shorter but honest measurement).
        base_job = pre_boundary_job
        # baseline = the assignment our streams were actually built with; any
        # divergence in the file (repath during boundary OR mid-window) is a
        # live UL-path change our streams don't reflect yet

        base_assign = dict(assign_save_str)
        base_teids = {t['ue_ip']: t['ul_teid'] for t in act_teids}
        # idx->ip mapping at build time: a DNN-changing rehome REPLACES the
        # UE's ip, so the old ip vanishes from m32 and the teid-compare above
        # never fires (B3 min1/min5: ~10%/scale-out-minute blind window).
        base_idxip = {str(i): idx_ip.get(i) for i in active}

        base_pool = list(m.vyos_pool)
        pool_miss = {}
        last_grow_chk = time.time()
        while True:
            rest = deadline - 2 - time.time()
            if rest <= 1:
                if rest > 0:
                    time.sleep(rest)
                break
            time.sleep(min(2, rest))

            grown = False
            if time.time() - last_grow_chk >= 5:
                last_grow_chk = time.time()
                try:
                    cand = set(vyos_ready_pool(vy_seen)) - set(m.vyos_pool)

                    cand = {v for v in cand if vyos_dataplane_ready(v, vy_seen.get(v), force=True)}
                    if cand:
                        grown = True
                        P(f"min{minute}: vyos-pool grow {sorted(cand)} mid-window")
                except Exception as e:
                    P(f"  grow check warn: {e}")
            seg_health_kick10(minute)
            sig = agent_job_sig()
            cur_assign = uemap_assign()
            job_done = (sig != base_job and sig[0] is None
                        and sig[1] is not None)
            cur_teids = m32_teids(set(base_teids))
            repathed = (cur_assign is not None and sig[0] is None
                        and any(cur_assign.get(k) != v
                                for k, v in base_assign.items()
                                if k in cur_assign))
            reteided = (cur_teids is not None and sig[0] is None
                        and any(cur_teids.get(ip) != t
                                for ip, t in base_teids.items()
                                if ip in cur_teids))
            try:
                cur_idxip = json.load(open('/tmp/uemap.json')).get('idx_ip', {})
            except Exception:
                cur_idxip = None

            remapped = (cur_idxip is not None
                        and any(cur_idxip.get(k) not in (None, v)
                                for k, v in base_idxip.items()))

            draining_now = vy_draining() & set(m.vyos_pool)
            shrunk = False
            for v in base_pool:
                alive = sp.run(f"timeout 2 ping -c1 -W1 {mlib.VYOS[v]}",
                               shell=True, capture_output=True).returncode == 0
                if alive:
                    pool_miss.pop(v, None)
                else:
                    pool_miss[v] = pool_miss.get(v, 0) + 1
                    if pool_miss[v] >= 2:
                        shrunk = True
            # rebuild guard 8s (was 15): a move landing in the guard shadow
            # stays a per-UE blackhole until the boundary rebuild — B3 min5
            # paid 17s of one UE for a move at minute-48s. 8s still leaves a
            # >=5s honest window after the ~2-3s rebuild.

            if (draining_now or job_done or repathed or reteided or remapped
                    or shrunk or grown) and ((deadline - 2 - time.time())
                                             >= (3 if (draining_now or grown) else 8)):

                why = ('vyos drain announced ' + ','.join(sorted(draining_now))
                       if draining_now else
                       'vyos-pool grow' if grown else
                       'rehome job' if job_done else
                       'repath' if repathed else
                       'teid change' if reteided else
                       'ip remap' if remapped else 'vyos-pool shrink')
                P(f"min{minute}: {why} mid-window — rebuilding streams now")
                base_job = sig
                # a delete_vyos repath means the pool changed too — re-check
                # (quarantined: a booting VyOS must not re-enter early)
                m.vyos_pool = ready_pool_verified(vy_seen, m.vyos_pool)
                # re-derive ips from UE logs: a DNN-move changed the UE's ip
                # and the shared files may have been stomped by our own
                # boundary write — the TUN log lines are the truth
                _ag_ips = agent_ue_ips()
                for i2 in list(active):
                    try:
                        lg2 = open(f"/tmp/hbo-ue-{i2}.log").read()
                        h2 = re.findall(
                            r'TUN interface\[(uesimtun\d+), (10\.45\.[0-9.]+)\]', lg2)
                        aip = _ag_ips.get(i2)
                        if aip and any(ip_ == aip for _, ip_ in h2):
                            idx_tun[i2] = [tn for tn, ip_ in h2 if ip_ == aip][-1]
                            idx_ip[i2] = aip
                        elif h2:
                            idx_tun[i2], idx_ip[i2] = h2[-1]
                    except Exception:
                        pass
                fresh = teids_from_eupf(list(idx_ip.values())) if idx_ip else []
                fb = {t['ue_ip']: t for t in fresh}
                oct_dnn = dict(OCT_DNN)
                for i2 in active:
                    ip2 = idx_ip.get(i2)
                    if ip2 in fb:
                        fb[ip2]['gnb_ip'] = gnb_ip(i2)
                        teid_cache[ip2] = fb[ip2]
                        dnn_of[i2] = oct_dnn.get(slot_octet(ip2), dnn_of.get(i2))
                act2 = []
                for i2 in active:
                    _t = fb.get(idx_ip.get(i2)) or teid_cache.get(idx_ip.get(i2))
                    if _t:
                        _t = dict(_t); _t['idx'] = i2; act2.append(_t)
                if act2:
                    m.teids = act2
                    m.ue_vyos = {}
                    prime_dl_affinity(m, act2)
                    m.set_load(ues=len(act2), pps_per_ue=PPS_PER_UE)
                    pg_map = [i2 for i2 in active
                              if (fb.get(idx_ip.get(i2))
                                  or teid_cache.get(idx_ip.get(i2)))]
                    pg_base = pg_snapshot()
                    assign2 = {j: m.ue_vyos.get(j) for j in range(len(act2))}
                    try:
                        mlib.worker_repoint(
                            act2, lambda t: mlib.VMAC[assign2[act2.index(t)]])
                    except Exception as e:
                        P(f"  repoint warn: {e}")
                    publish_ul_pool(m)
                    act_teids = act2

                    try:
                        _m32c = json.load(open('/tmp/m32.json'))
                        _tp2 = {t['ue_ip']: k for k, t in enumerate(_m32c)}
                        _a2 = {str(_tp2[t['ue_ip']]): assign2[j]
                               for j, t in enumerate(act2)
                               if t['ue_ip'] in _tp2
                               and assign2.get(j) is not None}
                        _um = json.load(open('/tmp/uemap.json'))
                        _um['assign'] = _a2
                        json.dump(_um, open('/tmp/uemap.json', 'w'))
                        base_assign = _a2
                    except Exception as e:
                        P(f"  assign-sync warn: {e}")
                        base_assign = {}
                    base_teids = {t['ue_ip']: t['ul_teid'] for t in act2}
                    base_idxip = {str(i2): idx_ip.get(i2) for i2 in active}
                    base_pool = list(m.vyos_pool)
                    pool_miss = {}

                    pass
        r = win.close()
        prev_win_end = r

        _pg = pg_snapshot()
        _hits = []
        for _uei in pg_map:
            b = pg_base.get(100 + _uei); c2 = _pg.get(100 + _uei)
            if not b or not c2:
                continue
            d_tx, d_rx = c2[0] - b[0], c2[1] - b[1]
            if d_tx > 1500 and d_rx < d_tx * 0.5 and _uei in active:
                _hits.append((_uei, d_rx, d_tx))
        if len(_hits) > max(2, len(active) // 3):
            P(f"min{minute}: {len(_hits)}/{len(active)} UEs below 50% loop "
              f"— SHARED-CAUSE (capacity/path), skipping per-UE reap")
        else:
            for _uei, d_rx, d_tx in _hits:
                P(f"min{minute}: UE-{_uei} datapath black "
                  f"(loop {d_rx}/{d_tx}={d_rx/max(1,d_tx):.0%}) — force reap")
                dp_black.add(_uei)
        # native latency streams ride the same set_load lifecycle: counters
        # are cumulative since this minute's rebuild = this minute's window
        ls = (m.latency_stats() or {}).get('all') or {}
        if time.time() > deadline + 30:
            P(f"min{minute}: WALL-CLOCK DRIFT {time.time()-deadline:.0f}s past deadline")
        e2e = max(0, (r['txr'] - r['dl'] - r['pf_rx'])) / r['txr'] * 100 \
            if r['txr'] else 0
        hc = host_cpu_snap()
        hw = [round(hc.get(f'worker-{i}', {}).get('c', 0) / 100, 2)
              for i in range(4)]
        hd = [round(hc.get(f'worker-{i}', {}).get('dp', 0) / 100, 2)
              for i in range(4)]
        hv = round(sum(v.get('c', 0) for k, v in hc.items()
                       if k.startswith('vyos')) / 100, 2)
        w.writerow([minute, target, len(active), len(act_teids)*PPS_PER_UE,
                    round(r['txr']), round(r['dl']), round(r['pf_rx']),
                    round(e2e, 2), r['eupf_cov'], fails, deaths,
                    round(ls.get('avg') or 0), ls.get('p50') or '',
                    ls.get('p95') or '', ls.get('p99') or '',
                    ls.get('max') or '', ls.get('n') or 0,
                    len(m.vyos_pool), sum(1 for i in range(4) if f'worker-{i}' in hc),
                    *hw, *hd, hv,
                    *[(r['vy'].get(f'10.0.1.{o}') or {}).get('miss', '')
                      for o in (4, 5, 6)],
                    *[(r['vy'].get(f'10.0.1.{o}') or {}).get('drops', '')
                      for o in (4, 5, 6)],
                    *[(r['slot_vf'].get(o) or {}).get('rx_out_of_buffer', '')
                      for o in mlib.UPFS],
                    *[(r['slot_vf'].get(o) or {}).get('rx_xdp_tx_full', '')
                      for o in mlib.UPFS],
                    round(sum((v or {}).get('rx_out_of_buffer', 0) +
                              (v or {}).get('rx_xdp_tx_full', 0)
                              for v in r['slot_vf'].values())
                          / max(1.0, r['txr'] * r['dtf']) * 100, 3),
                    round(r['dtf'], 1)])
        P(f"min{minute}: target={target} active={len(active)} "
          f"tx={r['txr']/1e6:.2f}M e2e={e2e:.2f}% "
          f"lat p50={ls.get('p50')}us p95={ls.get('p95')}us "
          f"settle={settle:.0f}s")

    for i in list(KA):
        stop_keepalive(i)
    _hb_stop.set()
    m.stop_sampler_1s()
    m.stop()
    m.disconnect()
    P(f"TRACE-RUN-DONE -> {OUT}")

def _autoscale_disable():
    """(docstring removed)"""
    try:
        r = sp.run(["sshpass", "-p", "<REDACTED>", "ssh", "-n", "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null", "user@10.0.0.50",
                    "curl -s -X POST http://10.102.132.80:8080/autoscale/disable"],
                   capture_output=True, text=True, timeout=20)
        P(f"autoscale disable -> {(r.stdout or r.stderr).strip()[:80]}")
    except Exception as e:  # noqa: BLE001
        P(f"autoscale disable FAILED: {e}")

if __name__ == '__main__':
    try:
        main()
    finally:
        _autoscale_disable()
