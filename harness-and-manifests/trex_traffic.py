"""TRex-based GTP-U traffic generator.

Replaces nr-ue's data-plane GTP encap (single-threaded, ~150 Mbps/UE cap) with
pre-encapsulated GTP-U pushed directly from sender NIC via DPDK. UERANSIM is
still used for control plane (PDU establishment) — we capture the resulting
UL TEIDs and SMF-assigned UPF GTPU IPs by sniffing a brief ping pulse, then
TRex sends per-UE streams at independently controllable pps.

Architecture & spike validation: see docs/handoff/10-trex-integration.md.
"""
import json
import os
import struct
import re
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from typing import Optional

sys.path.insert(0, "/home/user/trex/v3.08/automation/trex_control_plane/interactive")
from trex.common.trex_types import PortProfileID  # noqa: E402
from trex.stl.api import (  # noqa: E402
    STLClient,
    STLStream,
    STLPktBuilder,
    STLTXCont,
    STLFlowLatencyStats,
    STLFlowStats,
)
from scapy.all import Ether, IP, UDP, Raw, PcapReader  # noqa: E402
from scapy.contrib.gtp import GTP_U_Header  # noqa: E402

VF1_MAC_DEFAULT = "02:00:00:00:0c:01"
TREX_PORT = 0  # only one real port (the other is "dummy" per trex_cfg.yaml)

# SecGW mode (Phase-2 IPsec, 2026-07-14): SECGW=1 reroutes ALL UL through the
# SEG box (VPP on sender cores 6/7) — dst MAC becomes the constant seg-plain
# VF, and per-UE VyOS selection moves into the outer-IP DSCP: the SEG's ip4
# input classifier maps DSCP d -> fib d -> ESP tunnel to the VyOS whose data
# IP is 10.0.1.(3+d). DSCP = last_octet-3 (NOT -4) so vyos-0 (.4) gets
# DSCP 1 — DSCP 0 is the classifier's fall-through and cannot select.
# Repoint therefore changes a header byte, not the neighbor table — same
# ue_vyos map, same balance_vyos, zero daemon interaction on the UL side.
SECGW_MODE = os.environ.get("SECGW", "") == "1"
SEG_PLAIN_MAC = "02:00:00:00:0c:02"

def secgw_tos_for_vyos(vyos_ip: str) -> int:
    """Outer-IP TOS byte steering vyos_ip's traffic at the SEG (DSCP<<2)."""
    return (int(vyos_ip.rsplit(".", 1)[1]) - 3) << 2

# DN echo server — see docs/handoff/10 §M7. Replaces dst=10.45.0.1 (which
# triggered kernel ICMP-Port-Unreachable rate-limit, drowning the DL test).
# dn-echo VM runs /usr/local/bin/udpecho on UDP 12345 → batched echo, every
# UL packet round-trips, forcing UPF to do real bidirectional GTP-U encap.
DN_IP_DEFAULT = "10.0.1.16"  # eUPF topology: DN data-plane enp10s0 10.0.1.16 MTU3000 (was 10.20.0.50 dual-leg / 10.0.1.50 orig). eUPF decaps then route_ipv4(inner dst); a stale DN → no route → XDP_PASS (looks like "no decap" but GTP WAS removed).
DN_PORT_DEFAULT = 12345

def _build_gtpu_packet(ue_ip: str, gnb_ip: str, upf_ip: str, ul_teid: int,
                       vyos_mac: str, vf_mac: str, marker: bytes,
                       dn_ip: str = DN_IP_DEFAULT, dn_port: int = DN_PORT_DEFAULT,
                       tos: int = 0) -> bytes:
    """Construct one UL GTP-U packet with PDU Session Container (UL, QFI=1).

    Inner: IP(src=ue_ip, dst=DN_IP)/UDP(12345,DN_PORT)/marker
    Outer: Ether/IP(gnb→upf)/UDP(2152,2152)/GTPU(E=1, next=0x85)/PSC(type=1, QFI=1)/inner

    Bytes-level construction (instead of scapy.contrib.gtp.GTPPDUSessionContainer)
    because TRex bundles scapy 2.4.3 which doesn't have that class.
    """
    # src port MUST differ from dn_port and be per-UE unique: (a) the DN
    # reflector swaps ports, so with sport==dport==12345 any reflected packet
    # that bounces off a router re-matches the reflector -> a TTL-less XDP
    # ping-pong loop (DN<->VyOS) that inflated DN load ~50% at 4.8M+; (b) a
    # distinct sport per UE feeds RSS (udp4 sdfn) so the DN's rx queues spread
    # evenly instead of hashing 32 same-port flows onto 2 of 4 queues.
    o3, o4 = int(ue_ip.split('.')[2]), int(ue_ip.split('.')[3])
    sport = 20000 + (o3 * 256 + o4) % 8000
    inner = IP(src=ue_ip, dst=dn_ip) / UDP(sport=sport, dport=dn_port) / marker
    inner_bytes = bytes(inner)
    flags = 0x34  # ver=1, PT=1, E=1
    mtype = 0xFF  # T-PDU
    total_len = 4 + 4 + len(inner_bytes)  # seq/npdu/next (4) + PSC (4) + inner
    gtp_base = struct.pack("!BBHIHBB", flags, mtype, total_len, ul_teid, 0, 0, 0x85)
    psc = struct.pack("!BBBB", 0x01, 0x10, 0x01, 0x00)  # ExtHdrLen=1, PDU type=1(UL)<<4, QFI=1, next=0
    pld = gtp_base + psc + inner_bytes
    return Ether(src=vf_mac, dst=vyos_mac) / IP(src=gnb_ip, dst=upf_ip, tos=tos, flags='DF', id=0) / UDP(sport=2152, dport=2152) / Raw(load=pld)

def _fix_inner_udp_cksum(buf: bytearray, udp_off: int) -> None:
    """Recompute the inner UDP checksum in-place after patching the payload.

    buf is the full Ethernet frame; udp_off is the byte offset of the inner UDP
    header (which sits 8 bytes before the LAT marker). The preceding 20 bytes are
    the inner IPv4 header. Required because the DN validates the inner UDP checksum
    and drops packets whose checksum doesn't match the (patched) payload."""
    ip_off = udp_off - 20
    src = buf[ip_off + 12:ip_off + 16]
    dst = buf[ip_off + 16:ip_off + 20]
    ulen = struct.unpack(">H", buf[udp_off + 4:udp_off + 6])[0]
    buf[udp_off + 6] = 0  # zero the checksum field before summing
    buf[udp_off + 7] = 0
    seg = bytes(buf[udp_off:udp_off + ulen])
    pseudo = bytes(src) + bytes(dst) + b"\x00\x11" + struct.pack(">H", ulen)
    data = pseudo + seg
    if len(data) % 2:
        data += b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) | data[i + 1]
    s = (s >> 16) + (s & 0xFFFF)
    s += (s >> 16)
    ck = (~s) & 0xFFFF
    if ck == 0:
        ck = 0xFFFF
    buf[udp_off + 6] = (ck >> 8) & 0xFF
    buf[udp_off + 7] = ck & 0xFF

def _udp_cksum_base(buf: bytearray, udp_off: int) -> int:
    """Unfolded inner-UDP checksum sum over (pseudo-header + UDP segment) with the
    checksum field and the seq+ts marker words = 0. A probe then folds in only its
    6 changed 16-bit words (seq:2, ts:4). udp_off = inner UDP header offset."""
    ip_off = udp_off - 20
    src = bytes(buf[ip_off + 12:ip_off + 16])
    dst = bytes(buf[ip_off + 16:ip_off + 20])
    ulen = struct.unpack(">H", buf[udp_off + 4:udp_off + 6])[0]
    buf[udp_off + 6] = 0
    buf[udp_off + 7] = 0
    data = src + dst + b"\x00\x11" + struct.pack(">H", ulen) + bytes(buf[udp_off:udp_off + ulen])
    if len(data) % 2:
        data += b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) | data[i + 1]
    return s

def _is_gnb_ip(ip: str) -> bool:
    """gNB linkIps are 10.0.1.100-140 (mgnb-0..31 → .100-.132 at 32 UE + probe
    .108 + headroom). v4.46: was capped at 130 — for 32 UE the 31st/32nd gNB are
    .131/.132, so their UL GTP-U was SILENTLY dropped by this extractor filter →
    TEIDs for UE-30/31 never captured → consistent '2 STILL MISSING' (the UEs were
    perfectly healthy, ping 5/5; only the parser's range was wrong)."""
    o = ip.split(".")
    return o[:3] == ["10", "10", "10"] and 100 <= int(o[3]) <= 140

def _is_upf_ip(ip: str) -> bool:
    """UPF GTP-U externalIPs: base .11, daemon clones .21-.29 (EXTERNALIP_BASE=20
    + idx). The old string-prefix filter ("10.0.1.1") matched .11-.19 only and
    SILENTLY dropped clone UL flows at .22+ → TEIDs missing → those UPFs carried
    no TRex load."""
    o = ip.split(".")
    # eUPF topology (2026-07-01): 7 eUPF N3 at .31-.37 (+ .38 future base eUPF).
    # Keep legacy open5gs ranges (.11, .21-.29) for back-compat.
    return o[:3] == ["10", "10", "10"] and (
        int(o[3]) == 11 or 21 <= int(o[3]) <= 29 or 31 <= int(o[3]) <= 38)

def extract_teids_from_pcap(pcap_path: str) -> list[dict]:
    """Parse a pcap of GTP-U traffic and return one entry per distinct UL flow.

    Each entry: {ue_ip, gnb_ip, upf_ip, ul_teid}.
    """
    # Stream packet-by-packet (PcapReader), never rdpcap: an unexpectedly fat
    # capture must degrade to "slow", not to a multi-GB in-memory parse that
    # hangs the run for an hour (v44 attempt-5). Hard cap as a second fuse.
    ul = {}
    n = 0
    for p in PcapReader(pcap_path):
        n += 1
        if n > 2_000_000:
            print(f"    [teid] WARNING: pcap exceeds 2M packets, stopping parse early")
            break
        if GTP_U_Header not in p:
            continue
        g = p[GTP_U_Header]
        if g.fields.get("gtp_type") != 255:
            continue
        teid = g.fields.get("teid", 0)
        if teid == 0:
            continue
        outer_src, outer_dst = p[IP].src, p[IP].dst
        if not (_is_gnb_ip(outer_src) and _is_upf_ip(outer_dst)):
            continue
        psc_len = 4 if g.fields.get("E", 0) == 1 and g.fields.get("next_ex", 0) == 0x85 else 0
        try:
            inner = IP(bytes(g.payload)[psc_len:])
            ue_ip = inner.src
        except Exception:
            continue
        ul[(outer_src, outer_dst, teid)] = ue_ip
    out = [{"ue_ip": ip, "gnb_ip": gnb, "upf_ip": upf, "ul_teid": teid}
           for (gnb, upf, teid), ip in ul.items()]
    out.sort(key=lambda r: r["ue_ip"])
    return out

def _arp_lookup(vyos_ip: str):
    out = subprocess.run(["arp", "-n", vyos_ip], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == vyos_ip and ":" in parts[2]:
            return parts[2]
    return None

# Last successfully resolved MAC per VyOS IP. A VyOS interface MAC is STABLE for
# the lifetime of its VM (test-vyos .1 never changes; a scaled vyos keeps its MAC
# until deleted), so a transient ARP miss must NOT crash the run — fall back to
# the last-known-good MAC. v4.14 full run crashed here at the peak boundary when
# even .1 (the fallback target) briefly failed ARP during a data-plane blip.
_last_good_mac: dict = {}

def resolve_vyos_mac(iface: str = "enp5s0f0np0", vyos_ip: str = "10.0.1.1",
                     retries: int = 6) -> str:
    """Resolve the VyOS next-hop MAC via ARP, robust to a JUST-deployed VyOS and
    to transient ARP misses mid-run.

    A VyOS the daemon scaled out seconds ago may not answer ARP yet when the
    rebalancer immediately routes a UPF through it (v4.13 run crashed here on
    .5). Retry ping+ARP a few times; if a SCALED vyos still won't resolve, fall
    back to test-vyos (.1). If even .1 transiently fails, fall back to the
    last-known-good MAC (stable per VM) rather than killing the whole run."""
    mac = _arp_lookup(vyos_ip)
    if mac:
        _last_good_mac[vyos_ip] = mac
        return mac
    for _ in range(retries):
        subprocess.run(["ping", "-c", "1", "-W", "1", vyos_ip], capture_output=True)
        mac = _arp_lookup(vyos_ip)
        if mac:
            _last_good_mac[vyos_ip] = mac
            return mac
        time.sleep(1)
    if vyos_ip != "10.0.1.1":
        print(f"    [trex] WARN: {vyos_ip} not ARP-ready after {retries}s, "
              f"falling back to test-vyos .1 (re-resolved next set_load)")
        fb = _arp_lookup("10.0.1.1")
        if not fb:
            subprocess.run(["ping", "-c", "1", "-W", "1", "10.0.1.1"], capture_output=True)
            fb = _arp_lookup("10.0.1.1")
        if fb:
            _last_good_mac["10.0.1.1"] = fb
            return fb
    # Last resort: transient ARP failure — MAC is stable, so reuse last-known-good
    # for this IP (preferred) or for .1, instead of crashing the whole run.
    if vyos_ip in _last_good_mac:
        print(f"    [trex] WARN: {vyos_ip} ARP transiently failed, reusing "
              f"last-known-good MAC {_last_good_mac[vyos_ip]}")
        return _last_good_mac[vyos_ip]
    if "10.0.1.1" in _last_good_mac:
        print(f"    [trex] WARN: {vyos_ip} ARP failed, reusing last-known-good "
              f".1 MAC {_last_good_mac['10.0.1.1']}")
        return _last_good_mac["10.0.1.1"]
    raise RuntimeError(f"could not resolve MAC for {vyos_ip} via ARP")

def vyos_mac_for_upf(upf_ip: str, _cache: dict = {}) -> str:
    """Resolve the NEXT-HOP VyOS MAC for a given UPF externalIP by following the
    sender's kernel route (which the daemon's tickVyosRebalance updates to
    spread per-UPF paths across the VyOS pool). TRex bypasses the kernel, so
    without this every stream was built with test-vyos's MAC and ALL DPDK
    traffic ignored the rebalanced routes — test-vyos saturated at 100% while
    scaled VyOS sat idle. Cache per gateway; reload_trex/set_load re-resolves
    each stage + scale event, tracking route moves at those boundaries."""
    out = subprocess.run(["ip", "route", "get", upf_ip],
                         capture_output=True, text=True).stdout
    m = re.search(r"via (\d+\.\d+\.\d+\.\d+)", out)
    gw = m.group(1) if m else "10.0.1.1"
    if gw not in _cache:
        _cache[gw] = resolve_vyos_mac(vyos_ip=gw)
    return _cache[gw]

def vyos_sel_for_upf(upf_ip: str) -> tuple:
    """(dst_mac, outer_tos) for a probe frame following upf_ip's kernel route.
    SecGW mode steers by DSCP through the SEG instead of direct VyOS MAC, so
    probes measure the same encrypted path the load rides."""
    if not SECGW_MODE:
        return vyos_mac_for_upf(upf_ip), 0
    out = subprocess.run(["ip", "route", "get", upf_ip],
                         capture_output=True, text=True).stdout
    m = re.search(r"via (\d+\.\d+\.\d+\.\d+)", out)
    gw = m.group(1) if m else "10.0.1.4"
    return SEG_PLAIN_MAC, secgw_tos_for_vyos(gw)

class TRexTrafficManager:
    """Stateful TRex driver: connect once, then set_load() per stage.

    Usage:
        m = TRexTrafficManager(vyos_mac="56:a9:...")
        m.connect()
        m.load_teids("/tmp/teids.json")
        m.set_load(ues=8, pps_per_ue=2000)   # streams 0..7 at 2000 pps each
        ...
        m.set_load(ues=4, pps_per_ue=500)    # reduce
        m.stop()
        m.disconnect()
    """

    def __init__(self, server: str = "127.0.0.1", vyos_mac: Optional[str] = None,
                 vf_mac: str = VF1_MAC_DEFAULT,
                 dn_ip: str = DN_IP_DEFAULT, dn_port: int = DN_PORT_DEFAULT):
        self.client = STLClient(server=server)
        self.vyos_mac = vyos_mac or resolve_vyos_mac()
        self.vf_mac = vf_mac
        self.dn_ip = dn_ip
        self.dn_port = dn_port
        self.teids: list[dict] = []
        self.active_ues = 0
        self._connected = False
        self._running = False
        # continuous-servo state: the one-shot _servo_tx converged in the
        # first ~10s of a minute, but TRex's per-stream under-realization
        # DRIFTS (0.7x right after start -> ~1.0x tens of seconds later), so
        # an early mult=1.4 became a sustained +40% overshoot with nobody
        # correcting (run#4 min27, run#5 min21/27). A daemon thread nudges
        # mult every ~3s for as long as the load runs.
        self._api_lock = threading.Lock()
        self._servo_stop: Optional[threading.Event] = None
        self._servo_mult = 1.0
        self._lat_stop: Optional[threading.Event] = None
        # ── per-UE VyOS session balancing (item1) ───────────────────────────
        # Each UE's UL stream is sent (L2-direct via DPDK) to a chosen VyOS's MAC.
        # ue_vyos[idx] = that VyOS's DATA IP. balance_vyos() places each UE on the
        # least-session VyOS (every UE = equal 50k pps, so session COUNT is the
        # sole load metric). vyos_pool = live VyOS data IPs (refreshed from prom
        # by the experiment). Replaces the daemon's per-UPF route rebalancer.
        self.ue_vyos: dict[int, str] = {}
        self.vyos_pool: list[str] = ["10.0.1.1"]  # test-vyos until pool synced
        self._vyos_mac_cache: dict[str, str] = {}
        # test-vyos (10.0.1.1) is the SCTP control anchor. Instead of excluding
        # it from data entirely (wastes its headroom + over-loads the scaled VyOS
        # → over-scaling + a delete-time concentration spike → rebound), give it a
        # DISCOUNTED share like run43's VyosCtrlShare: it counts as CTRL_SHARE of a
        # scaled VyOS, so it carries ~half the sessions of a scaled node, never
        # exceeding CTRL_MAX (control-plane safety ceiling).
        self.vyos_ctrl_ip = "10.0.1.1"
        # v4.69: 0.5→0.85 share, 8→13 cap. The old 0.5 discount + cap-8 forced the 2
        # scaled VyOS to each carry ~13 sessions (650k pps) at peak (32 UE / 3 VyOS) →
        # busiest VyOS hit 97% CPU and dropped ~80k pps (sess3 loss 3.66%). An EVEN
        # split is 32/3≈11 sessions (550k, ~70% CPU) — safe. 0.85 keeps test-vyos just
        # under an even share (control-plane headroom) while the scaled nodes drop from
        # 13→~11. cap 13 stops cap-8 from re-concentrating the overflow onto scaled.
        self.vyos_ctrl_share = float(os.environ.get("VYOS_CTRL_SHARE", "0.85"))
        self.vyos_ctrl_max = int(os.environ.get("VYOS_CTRL_MAX_SESS", "13"))

    def connect(self) -> None:
        self.client.connect()
        # Force-acquire + stop + reset to clear any leftover streams from a
        # prior run that was killed (SIGKILL skips cleanup → the DPDK port
        # keeps transmitting stale-TEID GTP-U, flooding the UPF with Error
        # Indications and breaking every subsequent run's data plane).
        self.client.acquire(ports=[TREX_PORT], force=True)
        try:
            self.client.stop(ports=[TREX_PORT])
        except Exception:
            pass
        self.client.reset(ports=[TREX_PORT])
        self._connected = True

    def disconnect(self) -> None:
        if self._connected:
            try:
                self.client.disconnect()
            finally:
                self._connected = False

    def load_teids(self, path: str) -> int:
        with open(path) as f:
            self.teids = json.load(f)
        return len(self.teids)

    def _mac_for_vyos(self, vyos_ip: str) -> str:
        if vyos_ip not in self._vyos_mac_cache:
            self._vyos_mac_cache[vyos_ip] = resolve_vyos_mac(vyos_ip=vyos_ip)
        return self._vyos_mac_cache[vyos_ip]

    def _l2sel(self, vyos_ip: str) -> tuple:
        """(dst_mac, outer_tos) selecting this UE's VyOS. SecGW mode: constant
        SEG MAC + DSCP steering (no ARP — the SEG VF MAC is deterministic)."""
        if SECGW_MODE:
            return SEG_PLAIN_MAC, secgw_tos_for_vyos(vyos_ip)
        return self._mac_for_vyos(vyos_ip), 0

    def balance_vyos(self, pool: Optional[list] = None) -> bool:
        """Assign each active UE to the lowest-EFFECTIVE-load VyOS, where effective
        load = session count / capacity weight (every UE = equal 50k pps so count
        IS the load). Returns True if any assignment changed (caller reloads).

        test-vyos (10.0.1.1) is the SCTP control anchor — it is NOT excluded but
        given a DISCOUNTED weight (vyos_ctrl_share≈0.5), so it carries ~half a
        scaled node's sessions: uses its headroom WITHOUT pegging the control plane
        (hard-capped at vyos_ctrl_max). This avoids (a) wasting test-vyos, (b) the
        scaled VyOS running hot → over-scaling, (c) the delete-time concentration
        spike that caused ramp-down rebound. New UEs go to the lowest resulting
        eff-load node (each checked independently); periodic rebalance moves one UE
        max-eff→min-eff ONLY while it strictly lowers the pool's worst eff load
        (convergent → no back-and-forth churn)."""
        if pool is not None:
            self.vyos_pool = list(pool) if pool else [self.vyos_ctrl_ip]
        targets = list(self.vyos_pool)
        ctrl = self.vyos_ctrl_ip
        scaled = [v for v in targets if v != ctrl]
        n = self.active_ues
        changed = False

        def weight(v):
            return self.vyos_ctrl_share if (v == ctrl and scaled) else 1.0

        def counts():
            c = {v: 0 for v in targets}
            for v in self.ue_vyos.values():
                if v in c:
                    c[v] += 1
            return c

        def capped(v, c):  # control-plane safety: don't overload test-vyos
            return v == ctrl and scaled and c[v] >= self.vyos_ctrl_max

        def eff(v, c):
            return c[v] / weight(v)

        # drop stale assignments (UE gone or VyOS vanished)
        for idx in list(self.ue_vyos):
            if idx >= n or self.ue_vyos[idx] not in targets:
                del self.ue_vyos[idx]; changed = True

        mem = getattr(self, "_vy_by_ip", None) or {}

        fair = -(-n // max(1, len(targets)))
        before = dict(self.ue_vyos)
        for idx in range(n):
            if idx not in self.ue_vyos and idx < len(self.teids):
                v = mem.get(self.teids[idx].get("ue_ip"))
                if v in targets and counts()[v] < fair:
                    self.ue_vyos[idx] = v
        # place unassigned UEs on the lowest resulting effective-load node
        for idx in range(n):
            if idx not in self.ue_vyos:
                c = counts()
                cand = [v for v in targets if not capped(v, c)] or targets
                self.ue_vyos[idx] = min(cand, key=lambda v: (c[v] + 1) / weight(v))
                changed = True
        # rebalance: move max-eff → min-eff while it strictly lowers the worst eff
        for _ in range(2 * n):
            c = counts()
            live = [v for v in targets if c[v] > 0]
            if not live:
                break
            hi = max(live, key=lambda v: eff(v, c))
            dest = [v for v in targets if not capped(v, c)] or targets
            lo = min(dest, key=lambda v: (c[v] + 1) / weight(v))
            if lo == hi:
                break
            cur = max(eff(v, c) for v in targets)
            c2 = dict(c); c2[hi] -= 1; c2[lo] += 1
            if max(eff(v, c2) for v in targets) >= cur - 1e-9:
                break  # no strict improvement → stop (deadband, no churn)
            for idx, v in self.ue_vyos.items():
                if v == hi:
                    self.ue_vyos[idx] = lo; changed = True; break
        self._vy_by_ip = {self.teids[i].get("ue_ip"): v for i, v in self.ue_vyos.items()
                          if i < len(self.teids)}
        if changed:
            c = counts()
            moved = [(i, before.get(i), v) for i, v in self.ue_vyos.items() if i in before and before[i] != v]
            new = [i for i in self.ue_vyos if i not in before]
            print(f"  balance_vyos: counts={ {k.rsplit('.', 1)[1]: c[k] for k in targets} } "
                  f"new={new} moved={[(i, a.rsplit('.', 1)[1], b.rsplit('.', 1)[1]) for i, a, b in moved]}",
                  flush=True)
        return changed

    def vyos_session_counts(self) -> dict:
        """Current UE-session count per VyOS (the sole balance metric)."""
        c: dict[str, int] = {}
        for v in self.ue_vyos.values():
            c[v] = c.get(v, 0) + 1
        return c

    #   desired = {profile_id: key};key = (ue_ip, teid, gnb, upf, mac, tos, pps, pg)

    def set_load(self, ues: int, pps_per_ue: int) -> None:
        if os.environ.get("TREX_INCR", "1") != "1":
            return self._set_load_rebuild(ues, pps_per_ue)
        if ues > 0 and ues > len(self.teids):
            raise ValueError(f"requested {ues} UEs but only {len(self.teids)} TEIDs loaded")
        if ues <= 0 or pps_per_ue <= 0:
            self.stop()
            return
        self.active_ues = ues
        self._vyos_mac_cache.clear()
        self.balance_vyos()
        desired: dict = {}
        for i, t in enumerate(self.teids[:ues]):
            mac_i, tos_i = self._l2sel(self.ue_vyos.get(i, "10.0.1.1"))
            pg = self._pg_for(t)
            key = ("ue", t["ue_ip"], t["ul_teid"], t["gnb_ip"], t["upf_ip"], mac_i, tos_i, pps_per_ue, pg)
            desired[f"u{pg}"] = key

        probe = getattr(self, "_probe_ue", None)
        if probe is None:
            probe = self._probe_ue = {}
        by_oct: dict = {}
        for i, t in enumerate(self.teids[:ues]):
            by_oct.setdefault(int(t["upf_ip"].rsplit(".", 1)[1]), []).append((i, t))
        for oct_, lst in by_oct.items():
            pick = next(((i, t) for i, t in lst if t["ue_ip"] == probe.get(oct_)), lst[0])
            i, t = pick
            probe[oct_] = t["ue_ip"]
            mac_l, tos_l = self._l2sel(self.ue_vyos.get(i, "10.0.1.1"))
            desired[f"lat{oct_}"] = ("lat", oct_, t["ue_ip"], t["ul_teid"], t["gnb_ip"], t["upf_ip"], mac_l, tos_l)
        for oct_ in list(probe):
            if oct_ not in by_oct:
                probe.pop(oct_, None)
        live = getattr(self, "_live", None)
        if live is None:
            live = self._live = {}
            self._live_pid = {}
        self._servo_target = float(ues * pps_per_ue)

        _new_ue = sum(1 for b, k in desired.items()
                      if k[0] == "ue" and live.get(b) != k and not (self._live_pid.get(b) or []))
        _stagger = float(os.environ.get("ARRIVE_STAGGER_S", "0")) if _new_ue > 2 else 0.0

        if _stagger > 0:
            self._servo_hold_until = time.time() + _stagger * _new_ue + 3.5
        _batch = []
        with self._api_lock:
            # 1. add new/changed profiles first (make-before-break)
            for base, key in desired.items():
                if live.get(base) == key:
                    continue
                n = self._live_seq = getattr(self, "_live_seq", 0) + 1
                old_pids = self._live_pid.get(base) or []
                pids = []
                if old_pids and os.environ.get("PROFILE_CHURN_LOG", "1") == "1":

                    ok_ = live.get(base) or ()
                    diff = [j for j in range(max(len(ok_), len(key))) if (ok_[j] if j < len(ok_) else None) != (key[j] if j < len(key) else None)]
                    print(f"  [churn] {base} rebuilt: fields {diff} old={ok_} new={key}", flush=True)
                if key[0] == "ue" and old_pids:

                    pid_l = f"{base}x{n}l"
                    pp = PortProfileID(f"{TREX_PORT}.{pid_l}")
                    self.client.add_streams(self._build_profile(key, part="load"), ports=[pp])
                    self.client.start(ports=[pp], mult=f"{self._servo_mult:.4f}")
                    for op in old_pids:
                        self._profile_drop(op)
                    pid_h = f"{base}x{n}h"
                    pp = PortProfileID(f"{TREX_PORT}.{pid_h}")
                    self.client.add_streams(self._build_profile(key, part="health"), ports=[pp])
                    self.client.start(ports=[pp], mult=f"{self._servo_mult:.4f}")
                    pids = [pid_l, pid_h]
                else:
                    if old_pids:
                        for op in old_pids:
                            self._profile_drop(op)
                    pid = f"{base}x{n}"
                    pp = PortProfileID(f"{TREX_PORT}.{pid}")
                    self.client.add_streams(self._build_profile(key), ports=[pp])
                    if key[0] == "ue" and not old_pids:

                        _batch.append(pp)
                    else:
                        self.client.start(ports=[pp], mult=f"{self._servo_mult:.4f}")
                    pids = [pid]
                live[base] = key
                self._live_pid[base] = pids
            if _batch:

                ramp = [float(x) for x in os.environ.get("ARRIVE_RAMP", "0.2,0.4,0.6,0.8,1.0").split(",")]
                self._servo_hold_until = time.time() + 0.5 * len(ramp) + 3.5
                self.client.start(ports=_batch, mult=f"{self._servo_mult * ramp[0]:.4f}")
                for f_ in ramp[1:]:
                    time.sleep(0.5)
                    self.client.update(ports=_batch, mult=f"{self._servo_mult * f_:.4f}")
            # 2. drop profiles no longer desired
            for base in list(live):
                if base not in desired:
                    for op in (self._live_pid.pop(base, None) or []):
                        self._profile_drop(op)
                    del live[base]
        self._running = bool(live)
        self._ensure_servo()

    def _pg_for(self, t: dict) -> int:
        if "idx" in t:
            return 100 + int(t["idx"])
        alloc = getattr(self, "_pg_alloc", None)
        if alloc is None:
            alloc = self._pg_alloc = {}
        ip = t["ue_ip"]
        if ip not in alloc:
            used = set(alloc.values())
            alloc[ip] = next(k for k in range(100, 100 + 4096) if k not in used)
        return alloc[ip]

    def _build_profile(self, key: tuple, part: str = "all") -> list:
        if key[0] == "ue":
            _, ue_ip, teid, gnb, upf, mac, tos, pps, pg = key
            marker = f"PG{pg}-{ue_ip}-".encode() + b"PAYLOAD" * 4
            pkt = _build_gtpu_packet(dn_ip=self.dn_ip, dn_port=self.dn_port, ue_ip=ue_ip, gnb_ip=gnb,
                                     upf_ip=upf, ul_teid=teid, vyos_mac=mac, tos=tos, vf_mac=self.vf_mac,
                                     marker=marker)
            upkt = _build_gtpu_packet(dn_ip=self.dn_ip, dn_port=self.dn_port, ue_ip=ue_ip, gnb_ip=gnb,
                                      upf_ip=upf, ul_teid=teid, vyos_mac=mac, tos=tos, vf_mac=self.vf_mac,
                                      marker=b"UEPG!" + b"U" * 123)
            load = STLStream(packet=STLPktBuilder(pkt=pkt), mode=STLTXCont(pps=pps))
            health = STLStream(packet=STLPktBuilder(pkt=upkt), mode=STLTXCont(pps=50),
                               flow_stats=STLFlowLatencyStats(pg_id=pg))
            return {"load": [load], "health": [health]}.get(part, [load, health])
        _, oct_, ue_ip, teid, gnb, upf, mac, tos = key
        lpkt = _build_gtpu_packet(dn_ip=self.dn_ip, dn_port=self.dn_port, ue_ip=ue_ip, gnb_ip=gnb,
                                  upf_ip=upf, ul_teid=teid, vyos_mac=mac, tos=tos, vf_mac=self.vf_mac,
                                  marker=b"LATPG" + b"L" * 123)
        return [STLStream(packet=STLPktBuilder(pkt=lpkt), mode=STLTXCont(pps=LAT_PG_PPS),
                          flow_stats=STLFlowLatencyStats(pg_id=oct_))]

    def _port_stop_all(self) -> None:
        """(docstring removed)"""
        port = self.client.ports[TREX_PORT]
        for pid in [k for k, v in list(port.profile_state_list.items()) if port.is_profile_active(k)]:
            try:
                port.stop(force=True, profile_id=pid)
            except Exception:
                pass
        try:
            self.client.stop(ports=[TREX_PORT])
        except Exception:
            pass

    def _profile_drop(self, pid) -> None:
        """(docstring removed)"""
        if not pid:
            return
        pp = PortProfileID(f"{TREX_PORT}.{pid}")
        port = self.client.ports[TREX_PORT]
        try:
            if port.is_profile_active(pid):
                port.stop(force=True, profile_id=pid)
                if port.has_profile_rx_enabled(pid):
                    time.sleep(0.11)          # rx_delay_ms=100(virtual port)
                    port.remove_rx_filters(profile_id=pid)
        except Exception:
            pass
        try:
            self.client.remove_all_streams(ports=[pp])
        except Exception:
            pass

    def _ensure_servo(self) -> None:
        """(docstring removed)"""
        if self._servo_stop is not None and not self._servo_stop.is_set():
            return
        self._start_servo(self._servo_target)

    def _set_load_rebuild(self, ues: int, pps_per_ue: int) -> None:
        """Stop any running stream then push fresh ones for the first `ues`
        UEs at `pps_per_ue`. Each UE gets its own stream tag (UE00, UE01, ...)
        so DL responses can be attributed back per UE."""
        if ues > 0 and ues > len(self.teids):
            raise ValueError(f"requested {ues} UEs but only {len(self.teids)} TEIDs loaded")
        if ues > 0 and pps_per_ue > 0:
            # Skip-if-unchanged (2026-07-05): trace_run calls set_load every
            # minute; a full stop/reset/rebuild costs a 2-5s port-dark window
            # (the 1 Hz series gaps). When membership/teids/assignment/rate
            # are identical, keep the port running seamlessly.
            self.active_ues = ues  # balance_vyos assigns over teids[:active_ues]
            self._vyos_mac_cache.clear()
            self.balance_vyos()
            sig = (pps_per_ue, tuple(sorted(
                (t['ue_ip'], t['ul_teid'], t['gnb_ip'],
                 self.ue_vyos.get(i, ''))
                for i, t in enumerate(self.teids[:ues]))))
            if self._running and sig == getattr(self, '_load_sig', None):
                return
            self._load_sig = sig
        else:
            self._load_sig = None
        self._stop_servo()
        # _api_lock: the 1 Hz latency sampler keeps polling get_stats() across
        # set_load calls — unserialized concurrent RPC corrupts the (non
        # thread-safe) STLClient session and the sampler then swallows
        # exceptions forever (first sampler smoke: 0 rows).
        with self._api_lock:
            if self._running:
                self._port_stop_all()
                self._running = False

            self.client.remove_all_streams(ports=[TREX_PORT])
        if ues <= 0 or pps_per_ue <= 0:
            return
        self.active_ues = ues  # v4.49: the continuous LatencySampler probes teids[:active_ues]
        streams = []
        for i, t in enumerate(self.teids[:ues]):
            marker = f"UE{i:02d}-{t['ue_ip']}-".encode() + b"PAYLOAD" * 4
            mac_i, tos_i = self._l2sel(self.ue_vyos.get(i, "10.0.1.1"))
            pkt = _build_gtpu_packet(
                dn_ip=self.dn_ip, dn_port=self.dn_port,
                ue_ip=t["ue_ip"], gnb_ip=t["gnb_ip"], upf_ip=t["upf_ip"],
                ul_teid=t["ul_teid"], vyos_mac=mac_i, tos=tos_i,
                vf_mac=self.vf_mac,
                marker=marker,
            )
            # 2026-07-23: optional phase stagger (TREX_ISG_STAGGER=1) — spread the
            # N same-rate CBR streams evenly across one packet period so their
            # packets interleave instead of firing in phase every 1/pps (burst of
            # N → burst of 1). Only shifts each stream's start by <1 period; no
            # semantic change to rates or latency streams. Default OFF to keep
            # the historical offered-burst profile.
            isg_us = (i * 1e6 / pps_per_ue / max(ues, 1)) if os.environ.get("TREX_ISG_STAGGER") == "1" else 0.0
            streams.append(STLStream(packet=STLPktBuilder(pkt=pkt), mode=STLTXCont(pps=pps_per_ue), isg=isg_us))
        # Native TRex latency streams (2026-07-04, option A): one per ACTIVE
        # eUPF slot, riding a representative UE's real TEID through the full
        # GTP loop (TRex UL -> VyOS -> eUPF -> DN reflect -> DL back to this
        # port). Validated: TRex's RX latency engine recognizes the reflected
        # frames under GTP (~100% match, GTP untouched, avg 91us idle).
        # pg_id = slot octet; ~200pps each (scaled by the servo mult with all
        # streams) is noise vs the load. Stats via latency_stats(); cumulative
        # per set_load (reset() wipes them each rebuild = per-minute windows).
        seen_slots = set()
        for i, t in enumerate(self.teids[:ues]):
            oct_ = int(t["upf_ip"].rsplit(".", 1)[1])
            if oct_ in seen_slots:
                continue
            seen_slots.add(oct_)
            mac_l, tos_l = self._l2sel(self.ue_vyos.get(i, "10.0.1.1"))
            lpkt = _build_gtpu_packet(
                dn_ip=self.dn_ip, dn_port=self.dn_port,
                ue_ip=t["ue_ip"], gnb_ip=t["gnb_ip"], upf_ip=t["upf_ip"],
                ul_teid=t["ul_teid"],
                vyos_mac=mac_l, tos=tos_l,
                vf_mac=self.vf_mac, marker=b"LATPG" + b"L" * 123)
            streams.append(STLStream(
                packet=STLPktBuilder(pkt=lpkt),
                mode=STLTXCont(pps=LAT_PG_PPS),
                flow_stats=STLFlowLatencyStats(pg_id=oct_)))

        for i, t in enumerate(self.teids[:ues]):
            mac_u, tos_u = self._l2sel(self.ue_vyos.get(i, "10.0.1.1"))
            upkt = _build_gtpu_packet(
                dn_ip=self.dn_ip, dn_port=self.dn_port,
                ue_ip=t["ue_ip"], gnb_ip=t["gnb_ip"], upf_ip=t["upf_ip"],
                ul_teid=t["ul_teid"],
                vyos_mac=mac_u, tos=tos_u,
                vf_mac=self.vf_mac, marker=b"UEPG!" + b"U" * 123)
            streams.append(STLStream(
                packet=STLPktBuilder(pkt=upkt),
                mode=STLTXCont(pps=50),
                flow_stats=STLFlowLatencyStats(pg_id=100 + i)))
        with self._api_lock:
            self.client.add_streams(streams, ports=[TREX_PORT])
            self.client.start(ports=[TREX_PORT])  # runs until stop()
        self._running = True
        # TRex's cont-stream scheduler under-realizes low per-stream rates
        # (2026-07-03: 32x150k -> 69-77% realized) AND the realization drifts
        # over tens of seconds — run a CONTINUOUS closed-loop servo for the
        # lifetime of this load instead of a one-shot calibration.
        self._start_servo(float(ues * pps_per_ue))

    SERVO_WARM_S = 5.0
    SERVO_UP_CAP = 1.05

    def _start_servo(self, target: float, win: float = 2.0,
                     tol: float = 0.02) -> None:
        self._stop_servo()
        stop = threading.Event()
        self._servo_stop = stop
        self._servo_mult = 1.0

        self._servo_target = target

        def loop():
            if stop.wait(self.SERVO_WARM_S):
                return
            while not stop.is_set():
                try:
                    with self._api_lock:
                        s0 = self.client.get_stats(ports=[TREX_PORT])[TREX_PORT]["opackets"]
                    t0 = time.time()
                    if stop.wait(win):
                        return
                    with self._api_lock:
                        s1 = self.client.get_stats(ports=[TREX_PORT])[TREX_PORT]["opackets"]
                    tx = (s1 - s0) / (time.time() - t0)
                    tgt = self._servo_target
                    if time.time() < getattr(self, "_servo_hold_until", 0.0):
                        tx = tgt
                    if tx > 0 and tgt > 0 and abs(tx - tgt) / tgt > tol:
                        # damped step: transient reads must not slam mult;
                        # upward capped hard (overshoot = AMBR-policed loss)
                        step = max(0.7, min(self.SERVO_UP_CAP, tgt / tx))
                        self._servo_mult = max(0.2, min(6.0, self._servo_mult * step))
                        with self._api_lock:
                            if os.environ.get("TREX_INCR", "1") == "1":
                                self.client.update(ports=None, mult=f"{self._servo_mult:.4f}")
                            else:
                                self.client.update(ports=[TREX_PORT],
                                                   mult=f"{self._servo_mult:.4f}")
                except Exception:
                    pass  # port stopping/reset mid-measure: exit on next check
                if stop.wait(1.0):
                    return
        threading.Thread(target=loop, daemon=True).start()

    def _stop_servo(self) -> None:
        if self._servo_stop is not None:
            self._servo_stop.set()
            self._servo_stop = None

    def start_sampler_1s(self, path: str, period: float = 1.0) -> None:
        """Unified 1 Hz sampler, one row per second on a single time base:
        ts, ue, tx_pps, dl_pps, pf_pps, e2e_pct, lat_n, lat_p50/p95/p99 (usec).
        tx/dl from the TRex port counters (delta/s), pf from the sender PF
        kernel counter, e2e = (tx-dl-pf)/tx of THAT second, latency from the
        cumulative TRex histograms diffed per tick (interpolated pcts).
        `ue` mirrors self.sample_ue (the harness updates it on every arrival/
        departure/death). Counter resets (set_load) are detected per source:
        negative deltas skip the rate row for that second. Stop via
        stop_sampler_1s()."""
        self.stop_sampler_1s()
        stop = threading.Event()
        self._lat_stop = stop
        f = open(path, 'a', buffering=1)
        if f.tell() == 0:
            f.write('ts,ue,tx_pps,dl_pps,pf_pps,e2e_pct,'
                    'lat_n,lat_p50_us,lat_p95_us,lat_p99_us,black\n')

        pf_file = '/sys/class/net/enp1s0f0np0/statistics/rx_packets'

        def loop():
            prev_h = {}
            _hist = deque()
            prev_pg = {}
            po = pi = pp = None
            pt = None
            while not stop.is_set():
                try:
                    with self._api_lock:
                        st = self.client.get_stats()
                    now = time.time()
                    port = st.get(TREX_PORT, {})
                    o, i2 = port.get('opackets'), port.get('ipackets')
                    try:
                        pf = int(open(pf_file).read())
                    except Exception:
                        pf = None
                    tx = dl = pfr = ''
                    # counter-reset seconds (set_load stream swap) used to
                    # leave e2e blank -> line breaks in the 1s loss figure.
                    # make-before-break keeps the datapath lossless across
                    # swaps, so report 0 instead of a gap (user call
                    # 2026-07-05); rates stay blank (delta undefined).
                    e2e = 0.0
                    if None not in (o, i2, po, pi, pt) and now > pt:
                        dt = now - pt
                        dtx = (o - po) / dt
                        ddl = (i2 - pi) / dt
                        dpf = ((pf - pp) / dt) if (pf is not None
                                                   and pp is not None) else 0
                        if dtx >= 0 and ddl >= 0 and dpf >= 0:
                            tx, dl, pfr = round(dtx), round(ddl), round(dpf)
                            e2e = round(max(0.0, (dtx - ddl - dpf) / dtx
                                            * 100), 2) if dtx > 1000 else 0.0
                    po, pi, pp, pt = o, i2, pf, now
                    # latency: per-tick histogram delta, merged across slots
                    agg = {}
                    for pg, d in (st.get('latency') or {}).items():
                        if not isinstance(d, dict) or 'latency' not in d:
                            continue
                        h = {int(k): v for k, v in
                             (d['latency'].get('histogram') or {}).items()}
                        ph = prev_h.get(pg, {})
                        dh = {k: h.get(k, 0) - ph.get(k, 0)
                              for k in set(h) | set(ph)}
                        if any(v < 0 for v in dh.values()):
                            dh = h
                        prev_h[pg] = h
                        for k, v in dh.items():
                            agg[k] = agg.get(k, 0) + v
                    an = sum(agg.values())
                    p = _hist_pcts(agg, an) if an else \
                        {'p50': '', 'p95': '', 'p99': ''}

                    black = []
                    try:
                        for pg, d in (st.get('flow_stats') or {}).items():
                            try:
                                pgi = int(pg)
                            except Exception:
                                continue
                            if pgi < 100 or not isinstance(d, dict):
                                continue
                            txc = (d.get('tx_pkts') or {}).get('total', 0) or 0
                            rxc = (d.get('rx_pkts') or {}).get('total', 0) or 0
                            ptx, prx = prev_pg.get(pgi, (None, None))
                            prev_pg[pgi] = (txc, rxc)
                            if ptx is None or txc < ptx or rxc < prx:
                                continue      # first sample / counter reset
                            if txc - ptx >= 20 and rxc - prx < (txc - ptx) * 0.5:
                                black.append(str(pgi - 100))
                    except Exception:
                        pass
                    f.write(f"{now:.1f},{getattr(self, 'sample_ue', '')},"
                            f"{tx},{dl},{pfr},{e2e},{an},"
                            f"{p['p50']},{p['p95']},{p['p99']},{';'.join(black)}\n")

                    try:
                        if isinstance(tx, (int, float)):
                            _hist.append((now, float(tx)))
                        while _hist and now - _hist[0][0] > 240:
                            _hist.popleft()
                        _b = {}
                        for _t, _v in _hist:
                            _k = int(_t // 5) * 5
                            if _v > _b.get(_k, -1.0):
                                _b[_k] = _v
                        _tmp = '/tmp/offered.json.tmp'
                        with open(_tmp, 'w') as _of:
                            json.dump({'ts': now, 'tx_pps': tx,
                                       'hist': [[k, v] for k, v in sorted(_b.items())]}, _of)
                        os.replace(_tmp, '/tmp/offered.json')
                    except Exception:
                        pass
                except Exception:
                    pass
                if stop.wait(period):
                    break
            f.close()
        threading.Thread(target=loop, daemon=True).start()

    def stop_sampler_1s(self) -> None:
        if self._lat_stop is not None:
            self._lat_stop.set()
            self._lat_stop = None

    def stop(self) -> None:
        self._stop_servo()
        self._load_sig = None
        live = getattr(self, "_live", None)
        if live:
            with self._api_lock:
                for base in list(live):
                    for op in (self._live_pid.pop(base, None) or []):
                        self._profile_drop(op)
                    del live[base]
            self._running = False
            return
        if self._running:
            with self._api_lock:
                self._port_stop_all()
            self._running = False

    def stats(self) -> dict:
        with self._api_lock:
            s = self.client.get_stats()[TREX_PORT]
        return {k: s.get(k) for k in ("opackets", "obytes", "oerrors", "tx_bps", "tx_pps", "ipackets", "ibytes")}

    def clear_latency(self) -> None:
        """(docstring removed)"""
        try:
            with self._api_lock:
                self.client.pgid_stats.clear_stats(clear_flow_stats=False,
                                                   clear_latency_stats=True)
        except Exception:
            pass

    def latency_stats(self) -> dict:
        """Round-trip latency (usec) from the native latency streams, per slot
        (key = eUPF octet) plus merged 'all'. Percentiles come from TRex's
        log-binned histogram (resolution = decade/10 — 100us bins at ms scale,
        fine for the paper's latency curves). Counters are cumulative since
        the last set_load() (reset() wipes them), i.e. per-minute in trace
        runs. Returns {} when no latency stream is running."""
        try:
            with self._api_lock:
                lat = self.client.get_stats().get("latency", {})
        except Exception:
            return {}
        out, agg_h = {}, {}
        agg_n = agg_drop = agg_max = 0
        agg_avg_num = 0.0
        for pg, d in lat.items():
            if not isinstance(d, dict) or "latency" not in d:
                continue  # skips the 'global' entry
            L = d["latency"]
            h = {int(k): v for k, v in (L.get("histogram") or {}).items()}
            n = sum(h.values())
            ent = {"avg": L.get("average"), "max": L.get("total_max"), "n": n,
                   "dropped": d.get("err_cntrs", {}).get("dropped", 0)}
            ent.update(_hist_pcts(h, n))
            out[int(pg)] = ent
            for k, v in h.items():
                agg_h[k] = agg_h.get(k, 0) + v
            agg_n += n
            agg_drop += ent["dropped"]
            agg_max = max(agg_max, L.get("total_max") or 0)
            agg_avg_num += (L.get("average") or 0) * n
        if agg_n:
            a = {"avg": agg_avg_num / agg_n, "max": agg_max, "n": agg_n,
                 "dropped": agg_drop}
            a.update(_hist_pcts(agg_h, agg_n))
            out["all"] = a
        return out

LAT_PG_PPS = 500  # per-slot native latency probe rate: 500/s gives a solid
                  # per-SECOND p95 (and a usable p99) per slot for the 1 Hz
                  # sampler; 8 slots x 500 = 4k pps = noise vs the 4.8M load

def _bucket_edge(k: int) -> int:
    """Upper edge of a TRex decade-grid latency bucket (…,900→1000, 10000→20000)."""
    d = 1
    while d * 10 <= k:
        d *= 10
    return k + d

def _hist_pcts(h: dict, n: int) -> dict:
    """Percentiles (usec) from a TRex latency histogram, LINEARLY INTERPOLATED
    inside the hit bucket. Bucket lower bounds alone flat-lined the curves:
    the decade grid's 10000 bucket spans 10-20ms, so ten straight minutes of
    real 10-18ms tails all reported exactly '10000'."""
    if not n:
        return {"p50": None, "p95": None, "p99": None}
    ks = sorted(h)
    out = {}
    for name, q in (("p50", .50), ("p95", .95), ("p99", .99)):
        tgt = q * n
        c = 0
        val = float(_bucket_edge(ks[-1]))
        for k in ks:
            if c + h[k] >= tgt:
                frac = (tgt - c) / h[k]
                val = k + (_bucket_edge(k) - k) * frac
                break
            c += h[k]
        out[name] = round(val)
    return out

# ----------- TEID capture helpers (called between stages, not in hot path) -----------

SUDO_PW = "<REDACTED>"

def _sudo_sh(cmd: str) -> subprocess.CompletedProcess:
    """Run cmd as root by piping the sudo password (same pattern as experiment.py)."""
    full = f"echo {SUDO_PW} | sudo -S -p '' bash -c {subprocess.list2cmdline([cmd])}"
    return subprocess.run(full, shell=True, capture_output=True, text=True)

def capture_teids_pulse(pcap_path: str, ue_ifaces: list[str], iface: str = "enp5s0f0np0",
                        ping_count: int = 2, ping_target: str = "10.45.0.1") -> int:
    """Run a brief tcpdump while pinging from each UE iface, then return the
    number of UL pings issued. Caller then passes pcap to extract_teids_from_pcap()."""
    if not ue_ifaces:
        return 0
    _sudo_sh(f"rm -f {pcap_path}")
    # tcpdump in bg under nohup so it survives our short-lived shell
    _sudo_sh(
        f"nohup tcpdump -Z root -i {iface} -w {pcap_path} -U 'udp port 2152' "
        f"> /tmp/m6-tcpdump.log 2>&1 &"
    )
    time.sleep(1.5)
    for tun in ue_ifaces:
        _sudo_sh(f"ping -I {tun} -c {ping_count} -W 2 {ping_target}")
    time.sleep(1.5)
    _sudo_sh("pkill -SIGTERM tcpdump")
    time.sleep(1.5)
    return ping_count * len(ue_ifaces)

# ─── v4.20 real-load-path latency (Q4) ──────────────────────────────
# Measure RTT of the ACTUAL load path (sender→VyOS→UPF→DN→back, NO gNB) by
# pushing GTP-U packets through the live UE TEIDs, each carrying a send
# timestamp in the inner UDP payload, and reading the DN-echoed DL off the
# kernel NIC (enp5s0f0np0 — where the DL returns; the DPDK VF TRex sends on
# does NOT see it). RTT = pcap_kernel_ts - embedded_send_ts (same host clock).
# Validated in isolation: 100% match, ~3ms RTT. Replaces the single ICMP probe
# UE (70-90% loss, one path, gNB+ICMP-ratelimit) — this samples the real load
# across many UEs. Latency packets are padded LARGE so a BPF size filter
# isolates them from the 792k-pps bulk DL.
LAT_MAGIC = b"HBOLAT\xAA\xBB"          # 8 bytes
LAT_PAD   = b"L" * 220                  # makes the frame distinctly large
LAT_PCAP  = "/tmp/hbo-lat.pcap"
LAT_BPF   = "udp port 2152 and greater 250"   # bulk frame ≈124B, latency ≈300B

def measure_latency_trex(trex, n_ue: int = 32, pkts_per_ue: int = 100,
                         settle_s: float = 1.2, ipg_usec: int = 50):
    """Push timestamped GTP-U packets through up to n_ue live TEIDs, capture the
    DN-echoed DL (size-filtered), return {p50,p95,p99,avg,max,n}. Caller holds
    the TRex lock (push_packets must serialize with set_load). Returns None on
    failure (latency just N/A that sample).

    v4.49: BYTE-TEMPLATE bulk push → ~100 RTT samples/tick (was ~5).
    Mechanism: at peak the UPF runs at its single-thread ceiling, so a probe is a
    MARGINAL packet over capacity → ~97% are dropped at the UPF (measured
    lat_loss≈97%, even though the firehose itself isn't dropping). So a handful of
    probes yields ~3-5 RTTs → p50≈p99, statistically meaningless. The old loop
    rebuilt each probe with scapy (slow) → capped at ~192 probes/tick. Fix: build
    ONE byte template per UE, then per round patch only the 12-byte seq+ts marker
    and push the whole UE batch in a single push_packets() call with a hardware
    IPG. pkts_per_ue=100 rounds × n_ue=32 = ~3200 probes in one capture window →
    at ~3% survival ≈ ~100 RTTs → real p50/p95/p99 separation. Each round shares
    one send-ts (the round transmits in n_ue×ipg ≈ 1.6ms, far below the 10-200ms
    RTTs, so the shared-ts approximation adds negligible error). ~0.3s push +
    1.2s settle ≪ 8s SAMPLE_INTERVAL; the ~3200 mostly-dropped probes add <0.03%
    to the offered load."""
    teids = getattr(trex, "teids", None)
    if not teids:
        return None
    # sample evenly across the pool so percentiles reflect MANY UEs, not one
    step = max(1, len(teids) // n_ue)
    sample = teids[::step][:n_ue]
    # Pre-build a byte template per sampled UE (scapy build done ONCE here, not
    # per-probe). marker_off = byte offset of LAT_MAGIC within the frame → the
    # 4-byte seq and 8-byte ts that follow it are patched in place per round.
    templates = []  # list of (bytearray frame, marker_offset)
    placeholder = LAT_MAGIC + struct.pack(">I", 0) + struct.pack(">d", 0.0) + LAT_PAD
    for t in sample:
        vmac, vtos = vyos_sel_for_upf(t["upf_ip"])
        frame = bytes(_build_gtpu_packet(
            dn_ip=trex.dn_ip, dn_port=trex.dn_port, ue_ip=t["ue_ip"],
            gnb_ip=t["gnb_ip"], upf_ip=t["upf_ip"], ul_teid=t["ul_teid"],
            vyos_mac=vmac, tos=vtos, vf_mac=trex.vf_mac, marker=placeholder))
        off = frame.find(LAT_MAGIC)
        if off >= 0:
            templates.append((bytearray(frame), off))
    if not templates:
        return None
    _sudo_sh("pkill -9 -f 'tcpdump.*hbo-lat' 2>/dev/null || true")
    time.sleep(0.3)
    _sudo_sh(f"rm -f {LAT_PCAP}; "
             f"nohup tcpdump -Z root -i enp5s0f0np0 -w {LAT_PCAP} -U '{LAT_BPF}' "
             f">/dev/null 2>&1 &")
    time.sleep(0.6)
    seq = 0
    sent = {}
    try:
        for _round in range(pkts_per_ue):
            ts = time.time()
            tsb = struct.pack(">d", ts)
            batch = []
            for buf, off in templates:
                buf[off + 8:off + 12] = struct.pack(">I", seq)
                buf[off + 12:off + 20] = tsb
                batch.append(bytes(buf))
                sent[seq] = ts
                seq += 1
            trex.client.push_packets(pkts=batch, ports=[TREX_PORT],
                                     force=True, ipg_usec=ipg_usec)
    except Exception:
        _sudo_sh(f"pkill -SIGTERM -f 'tcpdump.*{LAT_PCAP}' 2>/dev/null")
        return None
    time.sleep(settle_s)
    _sudo_sh(f"pkill -SIGTERM -f 'tcpdump.*{LAT_PCAP}' 2>/dev/null")
    time.sleep(0.4)
    rtts = {}
    try:
        for p in PcapReader(LAT_PCAP):
            if not p.haslayer(GTP_U_Header):
                continue
            raw = bytes(p[GTP_U_Header].payload)
            inner = None
            for off in (0, 4, 8):
                try:
                    ii = IP(raw[off:])
                    if ii.version == 4 and ii.haslayer(UDP):
                        inner = ii
                        break
                except Exception:
                    pass
            if inner is None or inner.src != trex.dn_ip:
                continue          # DL echoes only (inner src = DN)
            pl = bytes(inner[UDP].payload)
            i = pl.find(LAT_MAGIC)
            if i < 0 or len(pl) < i + 20:
                continue
            s = struct.unpack(">I", pl[i+8:i+12])[0]
            send_ts = struct.unpack(">d", pl[i+12:i+20])[0]
            rtt = (float(p.time) - send_ts) * 1000.0
            if s not in rtts and -2 < rtt < 5000:
                rtts[s] = rtt
    except FileNotFoundError:
        return None
    if not rtts:
        return None
    v = sorted(rtts.values())
    def pct(q):
        return v[min(len(v) - 1, int(len(v) * q / 100))]
    loss = (len(sent) - len(v)) / len(sent) * 100.0 if sent else 0.0
    return {"avg": sum(v) / len(v), "p50": pct(50), "p95": pct(95),
            "p99": pct(99), "max": v[-1], "n": len(v), "loss": loss}

class LatencySampler:
    """v4.49: CONTINUOUS, high-rate latency sampler (replaces the 8s one-shot
    measure_latency_trex inside the metrics loop).

    Why: at peak the UPF runs at its single-thread ceiling so a probe is a MARGINAL
    packet over capacity → ~97% of probes are dropped at the UPF → a one-shot push
    yields ~5 RTTs → p50≈p99 (meaningless). This sampler instead pushes timestamped
    GTP-U probes through ALL active TEIDs (every UPF/VyOS path) CONTINUOUSLY and
    captures the DN-echoed DL with a PERSISTENT size-filtered tcpdump piped to a
    reader thread. A rolling time-indexed buffer of RTTs is exposed via stats():
    >100 samples/sec with ≥99.5% temporal coverage (the buffer always has the last
    few seconds of RTTs, so every CSV tick has data — carry-last only ever needed
    across a brief set_load reload that holds the TRex lock).

    Two daemon threads:
      reader  — `tcpdump -U -w -` piped → PcapReader → (recv_ts, rtt) into a deque
      pusher  — every round_sleep, patch the 12-byte seq+ts marker into each per-UE
                byte template and push the whole batch in one push_packets() call
                (shared send-ts; a round transmits in n_ue×ipg ≈ <1ms, far below the
                10-200ms RTTs). round_sleep≈8ms × n_ue≈32 ≈ 4000 probes/s → at the
                ~3% peak survival ≈ >100 RTT/s. Off-peak survival is higher → more.
    """

    def __init__(self, trex, lock, iface: str = "enp5s0f0np0",
                 ipg_usec: int = 20, round_sleep: float = 0.004,
                 rounds_per_call: int = 8, buffer_s: float = 3.0):
        self.trex = trex
        self.lock = lock
        self.iface = iface
        self.ipg_usec = ipg_usec
        self.round_sleep = round_sleep
        # v4.49: push rounds_per_call rounds in ONE push_packets() call (each packet
        # timestamped by its ipg-scheduled offset) → ~rounds_per_call× more probes
        # per lock acquire, so the rate scales WITHOUT more lock contention. At peak
        # the UPF drops ~99.5% of probes, so >100 captured RTT/s needs ~20k probes/s:
        # 250 calls/s × 8 rounds × 32 UE ≈ 64k probes/s → comfortably >100 RTT/s.
        self.rounds_per_call = rounds_per_call
        self._rounds_eff = rounds_per_call  # v4.49: effective rate, lowered by throttle()
        self.buffer_s = buffer_s
        self._rtts = deque()           # (recv_wallclock, rtt_ms)
        # v4.70: TRex set_load/reload pauses (stop+re-arm hold the lock). A probe whose
        # round-trip STRADDLES a reload measures the pause gap, not service latency —
        # and that gap's dropped traffic is already counted as loss (mig_lost_pkts). So
        # exclude any RTT whose [send_ts, recv_ts] overlaps a reload window from the
        # latency percentiles. Sub-second windows → per-tick stats still well-populated
        # (other sessions' latency NOT interrupted).
        self._reload_windows = deque()  # (start_wallclock, end_wallclock)
        self._dlock = threading.Lock()
        self._stop = threading.Event()
        self._templates = []           # list of (bytearray frame, marker_offset, cksum_base)
        self._templ_key = None         # (len(teids), active_ues) → rebuild on change
        self._seq = 0
        self._tcpdump = None
        self._threads = []

    def _rebuild_templates(self):
        teids = getattr(self.trex, "teids", None) or []
        n = getattr(self.trex, "active_ues", 0) or len(teids)
        key = (len(teids), n)
        if key == self._templ_key and self._templates:
            return
        ph = LAT_MAGIC + struct.pack(">I", 0) + struct.pack(">d", 0.0) + LAT_PAD
        tpls = []
        for t in teids[:n]:
            try:
                vmac, vtos = vyos_sel_for_upf(t["upf_ip"])
                frame = bytes(_build_gtpu_packet(
                    dn_ip=self.trex.dn_ip, dn_port=self.trex.dn_port,
                    ue_ip=t["ue_ip"], gnb_ip=t["gnb_ip"], upf_ip=t["upf_ip"],
                    ul_teid=t["ul_teid"], vyos_mac=vmac, tos=vtos,
                    vf_mac=self.trex.vf_mac,
                    marker=ph))
                off = frame.find(LAT_MAGIC)
                if off >= 0:
                    buf = bytearray(frame)
                    # Precompute the inner-UDP checksum partial sum over the
                    # placeholder (seq=0, ts=0.0 → those words contribute 0), so each
                    # probe only folds in its 6 changed words (seq:2 + ts:4) → O(6)
                    # checksum instead of O(packet) → can build tens of k probes/s.
                    base = _udp_cksum_base(buf, off - 8)
                    tpls.append((buf, off, base))
            except Exception:
                pass
        self._templates = tpls
        self._templ_key = key

    def _reader_loop(self):
        # Persistent tcpdump → pcap stream on stdout, parsed MANUALLY at the byte
        # level (NOT scapy PcapReader — the TRex-bundled scapy 2.4.3 PcapReader
        # mangles a subprocess pipe via its gzip-magic probe → 0 packets, the
        # run17 bug). enp5s0f0np0 only sees DL echoes (UL probes leave via the DPDK
        # port), so every captured frame containing LAT_MAGIC IS an echo → just
        # byte-search the magic and read the 8-byte send-ts that follows seq.
        # pcap global header 24B; per-record header 16B (ts_sec, ts_usec, incl, orig).
        while not self._stop.is_set():
            proc = None
            try:
                cmd = (f"echo {SUDO_PW} | sudo -S -p '' tcpdump -i {self.iface} "
                       f"-U -w - '{LAT_BPF}'")
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL)
                self._tcpdump = proc
                f = proc.stdout
                gh = f.read(24)
                if not gh or len(gh) < 24:
                    raise IOError("short pcap global header")
                magic = gh[:4]
                end = "<" if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
                nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
                tdiv = 1e9 if nano else 1e6
                while not self._stop.is_set():
                    rh = f.read(16)
                    if not rh or len(rh) < 16:
                        break
                    ts_sec, ts_frac, incl, _orig = struct.unpack(end + "IIII", rh)
                    data = f.read(incl)
                    if len(data) < incl:
                        break
                    j = data.find(LAT_MAGIC)
                    if j < 0 or len(data) < j + 20:
                        continue
                    try:
                        send_ts = struct.unpack(">d", data[j + 12:j + 20])[0]
                    except Exception:
                        continue
                    recv = ts_sec + ts_frac / tdiv
                    rtt = (recv - send_ts) * 1000.0
                    if -2 < rtt < 5000:
                        with self._dlock:
                            self._rtts.append((recv, rtt))
            except Exception:
                pass
            finally:
                if proc:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            if not self._stop.is_set():
                time.sleep(0.5)

    def throttle(self, rounds: int = 1):
        """v4.49: LOWER the probe rate (not stop) during UE spawn/migration + the
        one-time fill-capture, so the ~64k-probe/s UL load doesn't slow a UE's PDU
        re-establishment on a just-scaled UPF (run22 peak 30/32: fill-capture
        snapshotted mid-migration). rounds_per_call drops to `rounds` (~8x less
        load at the default 1) but latency IS still sampled the whole time."""
        self._rounds_eff = max(1, rounds)

    def unthrottle(self):
        self._rounds_eff = self.rounds_per_call

    def _pusher_loop(self):
        while not self._stop.is_set():
            try:
                self._rebuild_templates()
                tpls = self._templates
                if not tpls:
                    self._stop.wait(0.2)
                    continue
                # v4.49: push rounds_per_call rounds in ONE call. Each packet's ts =
                # call_time + (global_index × ipg) so the embedded send-ts matches its
                # ipg-scheduled wire time (TRex has BW headroom at 1.6M pps on the
                # 25G port → honours the IPG → sub-ms ts error). The inner-UDP csum
                # is folded incrementally from the precomputed base (DN drops a stale
                # csum — proven). ~8 rounds × 32 UE × 250 calls/s ≈ 64k probes/s → at
                # the ~0.7% peak survival ≈ >400 RTT/s ≫ the 100/s target.
                ipg_s = self.ipg_usec / 1e6
                t0 = time.time()
                batch = []
                p = 0
                for _r in range(self._rounds_eff):
                    for buf, off, base in tpls:
                        pts = t0 + p * ipg_s
                        sq = self._seq & 0xFFFFFFFF
                        buf[off + 8:off + 12] = struct.pack(">I", sq)
                        tb = struct.pack(">d", pts)
                        buf[off + 12:off + 20] = tb
                        # incremental inner-UDP checksum: base + 6 changed words
                        s = base + (sq >> 16) + (sq & 0xFFFF)
                        for k in range(0, 8, 2):
                            s += (tb[k] << 8) | tb[k + 1]
                        while s >> 16:
                            s = (s & 0xFFFF) + (s >> 16)
                        ck = (~s) & 0xFFFF or 0xFFFF
                        uo = off - 8
                        buf[uo + 6] = (ck >> 8) & 0xFF
                        buf[uo + 7] = ck & 0xFF
                        batch.append(bytes(buf))
                        self._seq += 1
                        p += 1
                with self.lock:
                    self.trex.client.push_packets(pkts=batch, ports=[TREX_PORT],
                                                  force=True, ipg_usec=self.ipg_usec)
            except Exception:
                self._stop.wait(0.05)
            # trim the rolling buffer
            cutoff = time.time() - self.buffer_s
            with self._dlock:
                while self._rtts and self._rtts[0][0] < cutoff:
                    self._rtts.popleft()
            self._stop.wait(self.round_sleep)

    def start(self):
        self._stop.clear()
        self._threads = [
            threading.Thread(target=self._reader_loop, daemon=True, name="lat-reader"),
            threading.Thread(target=self._pusher_loop, daemon=True, name="lat-pusher"),
        ]
        for t in self._threads:
            t.start()

    def stop(self):
        self._stop.set()
        if self._tcpdump:
            try:
                self._tcpdump.kill()
            except Exception:
                pass

    def mark_reload(self, start: float, end: float):
        """v4.70: record a TRex reload/pause window so stats() drops RTTs that
        straddled it (those measure the pause, not latency — already counted as loss)."""
        with self._dlock:
            self._reload_windows.append((start, end))
            # keep only windows that can still overlap the buffer
            cutoff = time.time() - self.buffer_s - 2.0
            while self._reload_windows and self._reload_windows[0][1] < cutoff:
                self._reload_windows.popleft()

    def stats(self, window_s: float = 1.0):
        """Percentiles + sample count over the last window_s of RTTs. None if empty."""
        now = time.time()
        with self._dlock:
            recent = [(tt, r) for (tt, r) in self._rtts if now - tt <= window_s]
            windows = list(self._reload_windows)
        # v4.70: drop RTTs whose round-trip [send_ts, recv_ts] overlaps a reload window
        # (probe straddled a TRex stop+re-arm → measured the pause gap, not service latency).
        def _straddles(tt, r):
            send_ts = tt - r / 1000.0
            for (ws, we) in windows:
                if send_ts < we and tt > ws:
                    return True
            return False
        vals = [r for (tt, r) in recent if not _straddles(tt, r)]
        if not vals:
            return None
        vals.sort()
        def pct(q):
            return vals[min(len(vals) - 1, int(len(vals) * q / 100))]
        return {"avg": sum(vals) / len(vals), "p50": pct(50), "p95": pct(95),
                "p99": pct(99), "max": vals[-1], "n": len(vals)}
