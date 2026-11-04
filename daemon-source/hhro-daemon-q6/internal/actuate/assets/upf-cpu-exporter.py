#!/usr/bin/env python3
"""(docstring removed)"""
import subprocess as sp, time, json, threading, socket, re, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, WINDOW, INTERVAL = 9101, 10, 300
BPFTOOL = '/usr/sbin/bpftool'
IF_SLOT_ALL = {'user-worker-0': {'enp14s0': 38, 'enp13s0': 33},
               'worker-0': {'enp14s0': 38, 'enp13s0': 33},
               'worker-1': {'enp15s0': 31, 'enp14s0': 32},
               'worker-2': {'enp15s0': 34, 'enp14s0': 35},
               'worker-3': {'enp15s0': 37, 'enp14s0': 36}}
VF_KEYS = ('rx_out_of_buffer', 'rx_xdp_drop', 'rx_xdp_tx_full', 'rx_xdp_tx_err',
           'rx_xdp_tx_xmit', 'rx_xdp_redirect', 'rx_packets', 'rx_discards_phy')

STATE = {'ts': 0.0, 'slots': {}}
VF = {'ts': 0.0, 'rows': []}   # rows: (slot, iface, {key: val})
VF_LOCK = threading.Lock()

def run(cmd, timeout=15):
    return sp.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout).stdout

def if_slot():
    """iface -> slot octet. Dynamic: any iface carrying 10.0.1.X/24 with X in
    31..38 is that slot's VF. Fallback: static table by hostname."""
    m = {}
    out = run('ip -4 -o addr show 2>/dev/null', 5)
    for l in out.splitlines():
        mm = re.match(r'\d+:\s+(\S+)\s+inet\s+10\.10\.10\.(\d+)/', l)
        if mm and 31 <= int(mm.group(2)) <= 38:
            m[mm.group(1)] = int(mm.group(2))
    return m or IF_SLOT_ALL.get(socket.gethostname(), {})

def vf_read(iface):
    out = run(f'ethtool -S {iface} 2>/dev/null', 5)
    d = {}
    for l in out.splitlines():
        mm = re.match(r'\s*([A-Za-z0-9_]+):\s+(\d+)\s*$', l)
        if mm and mm.group(1) in VF_KEYS:
            d[mm.group(1)] = int(mm.group(2))
    return d

def vf_refresh():
    with VF_LOCK:
        if time.time() - VF['ts'] < 1.0:
            return
        rows = []
        for iface, slot in sorted(if_slot().items(), key=lambda x: x[1]):
            try:
                d = vf_read(iface)
            except Exception:
                d = {}
            if d:
                rows.append((slot, iface, d))
        VF['rows'], VF['ts'] = rows, time.time()

def snap():
    net = run(f'{BPFTOOL} net show 2>/dev/null')
    i2p = {}
    for l in net.splitlines():
        if 'driver id' in l:
            i2p[l.split('(')[0].strip()] = int(l.split('driver id')[1])
    out = run(f'{BPFTOOL} -j prog show 2>/dev/null')
    try:
        progs = json.loads(out[out.index('['):])
    except Exception:
        return time.time(), {}
    byid = {p['id']: (p.get('run_time_ns', 0), p.get('run_cnt', 0)) for p in progs}
    ifs = if_slot()
    return time.time(), {ifs[i]: byid[pid] for i, pid in i2p.items()
                         if i in ifs and pid in byid}

def sampler():
    while True:
        try:
            run('sysctl -q kernel.bpf_stats_enabled=1')
            t1, a = snap(); time.sleep(WINDOW); t2, b = snap()
            run('sysctl -q kernel.bpf_stats_enabled=0')
            dt = max(t2 - t1, 1e-3)
            slots = {}
            for o in a:
                if o in b:
                    dns, dcnt = b[o][0] - a[o][0], b[o][1] - a[o][1]
                    slots[o] = (dns / 1e9 / dt, (dns / dcnt) if dcnt > 100 else 0, dcnt / dt)
            STATE['slots'], STATE['ts'] = slots, time.time()
        except Exception:
            run('sysctl -q kernel.bpf_stats_enabled=0')
        time.sleep(max(INTERVAL - WINDOW, 5))

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        lines = [f'upf_cpu_sample_age_seconds {time.time() - STATE["ts"]:.1f}']
        for o, (core, nspkt, pps) in STATE['slots'].items():
            lab = f'{{slot="{o}"}}'
            lines += [f'upf_slot_cpu_cores{lab} {core:.4f}',
                      f'upf_slot_ns_per_pkt{lab} {nspkt:.0f}',
                      f'upf_slot_xdp_pps{lab} {pps:.0f}']
        try:
            vf_refresh()
        except Exception:
            pass
        for k in VF_KEYS:
            lines.append(f'# TYPE upf_vf_{k} counter')
            for slot, iface, d in VF['rows']:
                if k in d:
                    lines.append(f'upf_vf_{k}{{slot="{slot}",iface="{iface}"}} {d[k]}')
        body = ('\n'.join(lines) + '\n').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; version=0.0.4')
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    threading.Thread(target=sampler, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
