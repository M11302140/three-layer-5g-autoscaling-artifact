package actuate

import (
	"context"
	_ "embed"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
	"github.com/anon/hhro-daemon/internal/sshexec"
)

// v5.0 — eUPF slot actuator.
//
// The eBPF/XDP data plane replaces the open5gs clone-and-patch flow entirely:
// there is nothing to clone. Eight eUPF instances are PRE-PROVISIONED slots —
// each slot owns a fixed N3 IP (10.0.1.3x), a fixed SR-IOV VF on a fixed
// worker (MTU 3000, single queue, policy-routing table, deterministic MAC,
// static neighbors) and a pre-existing configmap (eupf-config-N). The SMF
// PFCP pool is STATIC (all 8 DNN→N3 mappings always present), so activating
// or deactivating a slot never touches the SMF configmap and never restarts
// SMF.
//
// Scale-out  = create the slot's bare pod → eUPF binds its N3 IP, loads XDP,
//
//	SMF re-associates within a heartbeat. ~10 s, no VM churn.
//
// Scale-in   = delete the pod, then wipe the slot's pinned BPF maps
//
//	(/sys/fs/bpf/eupf-N on the worker) so stale sessions and the
//	stale PFCP association don't survive into the next activation.
//
// UE placement is DNN-driven (internetN → slot N) and owned by the experiment
// harness: it reads the active slot set from the daemon and (re)spawns UEs
// with DNNs of active slots. The daemon only manages slot capacity.
type EupfSlot struct {
	Idx     int    // pod suffix: eupf-<Idx>, configmap eupf-config-<Idx>
	N3Octet int    // 10.0.1.<octet> — N3/PFCP/API address of the slot
	Node    string // k8s node hosting the slot's provisioned VF
	Iface   string // VF netdev inside the worker VM (also the eupf config's interface_name)
}

type EupfCfg struct {
	Namespace string
	Image     string
	// DN reflector VF MAC — the .16 neighbor every eUPF VF needs (XDP never
	// ARPs; a stale/missing entry blackholes ALL uplink toward the DN). NOTE:
	// this MAC changes whenever the data-network VM is recreated — update the
	// env and re-provision.
	DnVfMac string
	// Activation order. Default is round-robin across workers so N active
	// slots are always spread as evenly as the slot topology allows.
	Slots []EupfSlot // in ACTIVATION order
	// vftx4 rulechain depth (emulated per-packet SDF/PCC rule-scan cost).
	// Injected as pod env so K survives container restarts — the live
	// bpftool-map value is volatile (2026-07-24 K-drift landmine).
	RulechainK string
}

// slot spec: "idx:n3octet:node" per entry, comma-separated, in activation order.
// v5.0.29: DEPTH-FIRST activation — fill both of a worker's slots before
// opening the next worker (was breadth-first round-robin, which forced a
// fresh VM boot on the very first 1→2 eupf step while run#4's ramp bled 32%
// loss). Worker creation is now owned by the predictive pre-create logic and
// the slot-dispatch worker-first path, not by slot spreading.
const defaultEupfSlots = "0:38:worker-0:enp14s0,3:33:worker-0:enp13s0,1:31:worker-1:enp15s0,2:32:worker-1:enp14s0," +
	"4:34:worker-2:enp15s0,5:35:worker-2:enp14s0,7:37:worker-3:enp15s0,6:36:worker-3:enp14s0"

func DefaultEupfCfg() EupfCfg {
	raw := envcfg.Get("EUPF_SLOTS", defaultEupfSlots)
	var slots []EupfSlot
	for _, ent := range strings.Split(raw, ",") {
		p := strings.Split(strings.TrimSpace(ent), ":")
		if len(p) != 4 {
			continue
		}
		idx, err1 := strconv.Atoi(p[0])
		oct, err2 := strconv.Atoi(p[1])
		if err1 != nil || err2 != nil {
			continue
		}
		slots = append(slots, EupfSlot{Idx: idx, N3Octet: oct, Node: p[2], Iface: p[3]})
	}
	return EupfCfg{
		Namespace:  envcfg.Get("OPEN5GS_NS", "open5gs"),
		Image:      envcfg.Get("EUPF_IMAGE", "docker.io/library/eupf:0.6.0-vftx2"),
		Slots:      slots,
		DnVfMac:    envcfg.Get("DN_VF_MAC", "92:74:24:e0:37:87"),
		RulechainK: envcfg.Get("EUPF_RULECHAIN_K", "0"),
	}
}

// ErrWorkerNotReady marks a slot activation blocked on its host worker — the
// daemon reacts by creating the worker (nextIndex reuses the missing name).
var ErrWorkerNotReady = errors.New("slot worker not ready")

type WorkerNotReadyError struct{ Node string }

func (e *WorkerNotReadyError) Error() string { return "slot worker not ready: " + e.Node }
func (e *WorkerNotReadyError) Unwrap() error { return ErrWorkerNotReady }

type EupfActuator struct {
	A      *Actuator
	Cfg    EupfCfg
	Host   *sshexec.HostExec
	Rehome *RehomeClient

	lastAction time.Time
	cooldown   time.Duration
	draining   sync.Map // pod name -> true while a drain-then-delete is in flight
	drainCancel sync.Map
	hotOnce     sync.Once // v6.0.90 p5u12 hot-slot measured relief state
	hotSt       *hotSlotState
}

func NewEupfActuator(a *Actuator, host *sshexec.HostExec) *EupfActuator {
	return &EupfActuator{
		A:        a,
		Cfg:      DefaultEupfCfg(),
		Host:     host,
		Rehome:   NewRehomeClient(),
		cooldown: envcfg.Dur("UPF_COOLDOWN", 3*time.Minute),
	}
}

// activeSlotIdxs returns the pod indices of eupf-N pods that currently exist
// (any phase — an existing pod occupies its slot even while ContainerCreating).
func (e *EupfActuator) ActiveSlotIdxs(ctx context.Context) (map[int]bool, error) {
	raw, err := e.A.M.K8sGet(ctx,
		fmt.Sprintf("/api/v1/namespaces/%s/pods?labelSelector=app%%3Deupf", e.Cfg.Namespace))
	if err != nil {
		return nil, err
	}
	var list struct {
		Items []struct {
			Metadata struct {
				Name string `json:"name"`
			} `json:"metadata"`
		} `json:"items"`
	}
	if err := json.Unmarshal(raw, &list); err != nil {
		return nil, err
	}
	out := map[int]bool{}
	for _, it := range list.Items {
		var n int
		if _, err := fmt.Sscanf(it.Metadata.Name, "eupf-%d", &n); err == nil {
			out[n] = true
		}
	}
	return out, nil
}

func (e *EupfActuator) slotByIdx(idx int) *EupfSlot {
	for i := range e.Cfg.Slots {
		if e.Cfg.Slots[i].Idx == idx {
			return &e.Cfg.Slots[i]
		}
	}
	return nil
}

// podJSON renders the bare-pod manifest for a slot — the exact known-good
// shape the testbed runs (hostNetwork, privileged, bpf hostPath pin dir,
// per-slot configmap).
func (e *EupfActuator) podJSON(s EupfSlot) []byte {
	pod := map[string]any{
		"apiVersion": "v1",
		"kind":       "Pod",
		"metadata": map[string]any{
			"name":      fmt.Sprintf("eupf-%d", s.Idx),
			"namespace": e.Cfg.Namespace,
			"labels": map[string]string{
				"app":                   "eupf",
				"hhro.io/eupf-release":  fmt.Sprintf("eupf-%d", s.Idx),
				"hhro.io/eupf-n3-octet": strconv.Itoa(s.N3Octet),
			},
		},
		"spec": map[string]any{
			"hostNetwork":  true,
			"nodeSelector": map[string]string{"kubernetes.io/hostname": s.Node},
			"tolerations":  []any{map[string]any{"operator": "Exists"}},
			"containers": []any{map[string]any{
				"name":            "eupf",
				"image":           e.Cfg.Image,
				"imagePullPolicy": "IfNotPresent",
				"args":            []string{"--config", "/app/conf/config.yml"},
				"env": []any{map[string]any{
					"name": "EUPF_RULECHAIN_K", "value": e.Cfg.RulechainK,
				}},
				"securityContext": map[string]any{
					"privileged": true,
					"capabilities": map[string]any{
						"add": []string{"NET_ADMIN", "SYS_ADMIN", "SYS_RESOURCE"},
					},
				},
				"volumeMounts": []any{
					map[string]any{"mountPath": "/app/conf", "name": "cfg"},
					map[string]any{"mountPath": "/sys/fs/bpf", "name": "bpf", "mountPropagation": "Bidirectional"},
					map[string]any{"mountPath": "/sys", "name": "sys", "readOnly": true},
				},
			}},
			"volumes": []any{
				map[string]any{"name": "cfg", "configMap": map[string]any{"name": fmt.Sprintf("eupf-config-%d", s.Idx)}},
				map[string]any{"name": "bpf", "hostPath": map[string]any{"path": fmt.Sprintf("/sys/fs/bpf/eupf-%d", s.Idx), "type": "DirectoryOrCreate"}},
				map[string]any{"name": "sys", "hostPath": map[string]any{"path": "/sys"}},
			},
		},
	}
	b, _ := json.Marshal(pod)
	return b
}

// DeployUPF activates the first inactive slot in activation order and returns
// its pod name. Mirrors UpfActuator.DeployUPF's signature so the daemon
// dispatch is a drop-in.
func (e *EupfActuator) DeployUPF(ctx context.Context, force bool) (string, error) {
	if !force && time.Since(e.lastAction) < e.cooldown {
		return "", fmt.Errorf("eupf cooldown active (%s left)", (e.cooldown - time.Since(e.lastAction)).Round(time.Second))
	}
	active, err := e.ActiveSlotIdxs(ctx)
	if err != nil {
		return "", fmt.Errorf("list eupf pods: %w", err)
	}
	for _, s := range e.Cfg.Slots {
		if active[s.Idx] {
			continue
		}
		// Slot's worker must exist & be Ready. eUPF pods carry no CPU requests,
		// so the legacy free-CPU BN_INFRA signal never fires — this typed error
		// IS the worker-scale-out trigger.
		if !e.nodeReady(ctx, s.Node) {
			return "", fmt.Errorf("eupf-%d needs %s: %w", s.Idx, s.Node, &WorkerNotReadyError{Node: s.Node})
		}
		if err := e.A.M.K8sCreate(ctx,
			fmt.Sprintf("/api/v1/namespaces/%s/pods", e.Cfg.Namespace), e.podJSON(s)); err != nil {
			return "", fmt.Errorf("create eupf-%d on %s: %w", s.Idx, s.Node, err)
		}
		e.lastAction = time.Now()
		return fmt.Sprintf("eupf-%d", s.Idx), nil
	}
	return "", fmt.Errorf("all %d eupf slots already active", len(e.Cfg.Slots))
}

// PickScaleInTarget returns the LAST active slot in activation order — the
// reverse of deploy, so the pool stays spread across workers.
func (e *EupfActuator) PickScaleInTarget(ctx context.Context) (string, error) {
	active, err := e.ActiveSlotIdxs(ctx)
	if err != nil {
		return "", err
	}
	for i := len(e.Cfg.Slots) - 1; i >= 0; i-- {
		name := fmt.Sprintf("eupf-%d", e.Cfg.Slots[i].Idx)
		if _, busy := e.draining.Load(name); busy {
			continue
		}
		if active[e.Cfg.Slots[i].Idx] {
			return name, nil
		}
	}
	return "", fmt.Errorf("no active eupf slot")
}

// DeleteUPF deactivates a slot: delete the pod, then wipe its pinned BPF maps
// on the worker so stale sessions / the stale PFCP association can't leak into
// the next activation (pins are the session-survival mechanism — on an
// EXPLICIT scale-in we want a clean slate).
func (e *EupfActuator) DeleteUPF(ctx context.Context, name string, force bool) error {
	if !force && time.Since(e.lastAction) < e.cooldown {
		return fmt.Errorf("eupf cooldown active")
	}
	var idx int
	if _, err := fmt.Sscanf(name, "eupf-%d", &idx); err != nil {
		return fmt.Errorf("bad eupf pod name %q", name)
	}
	s := e.slotByIdx(idx)
	if s == nil {
		return fmt.Errorf("eupf-%d is not a configured slot", idx)
	}
	if err := e.A.M.K8sDelete(ctx,
		fmt.Sprintf("/api/v1/namespaces/%s/pods/eupf-%d", e.Cfg.Namespace, idx)); err != nil {
		return fmt.Errorf("delete eupf-%d: %w", idx, err)
	}
	// pin wipe (best-effort): worker-N mgmt addr via the same octet mapping
	// CreateWorker uses (worker-0 = MgmtBase, N≥1 = MgmtBase+1+N skipping .53).
	if e.Host != nil {
		var widx int
		if _, err := fmt.Sscanf(s.Node, "worker-%d", &widx); err == nil {
			addr := fmt.Sprintf("%s%d:22", e.A.Cfg.MgmtPrefix, workerMgmtOctet(e.A.Cfg.MgmtBase, widx))
			cmd := fmt.Sprintf("echo %s | sudo -S -p '' rm -rf /sys/fs/bpf/eupf-%d", e.Host.SudoPassword, idx)
			_, _ = e.Host.ExecOnWorkerAddr(ctx, addr, cmd)
		}
	}
	e.lastAction = time.Now()
	return nil
}

// ActiveSummary returns "n/total [idx,idx,...]" for logs and /state.
func (e *EupfActuator) ActiveSummary(ctx context.Context) string {
	active, err := e.ActiveSlotIdxs(ctx)
	if err != nil {
		return "unknown"
	}
	var idxs []int
	for i := range active {
		idxs = append(idxs, i)
	}
	sort.Ints(idxs)
	return fmt.Sprintf("%d/%d %v", len(idxs), len(e.Cfg.Slots), idxs)
}

// ProvisionWorkerVFs runs the per-slot VF provisioning on a (re)booted worker.
// Everything here is RUNTIME state (netplan only carries legacy config) and is
// lost on every reboot: deterministic MAC (kills the clone machine-id MAC
// collision), N3 IP, MTU 3000, single queue, big rings, arp_ignore, the
// from-N3IP policy-routing table (XDP fib + API replies stay on the slot's own
// VF instead of detouring via VyOS where measurement-mode neighbors blackhole
// them), the DN .16 static neighbor, and the NAPI core pin.
// Blocks until SSH answers or the deadline passes; call from a goroutine.
//
//go:embed assets/upf-cpu-exporter.py
var upfExporterPy string

func (e *EupfActuator) ProvisionWorkerVFs(ctx context.Context, node string, wait time.Duration) error {
	if e.Host == nil {
		return fmt.Errorf("host ssh disabled")
	}
	var widx int
	if _, err := fmt.Sscanf(node, "worker-%d", &widx); err != nil {
		return fmt.Errorf("bad worker name %q", node)
	}
	addr := fmt.Sprintf("%s%d:22", e.A.Cfg.MgmtPrefix, workerMgmtOctet(e.A.Cfg.MgmtBase, widx))
	deadline := time.Now().Add(wait)
	for {
		// v5.0.7 — wait for cloud-init to FINISH, not just SSH: provisioning
		// that lands mid-boot gets wiped by cloud-init's final netplan apply
		// (worker-3's enp15s0 lost its N3 IP/rule exactly this way).
		if _, err := e.Host.ExecOnWorkerAddr(ctx, addr, "cloud-init status --wait >/dev/null 2>&1 || true"); err == nil {
			break
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("worker %s (%s) not reachable within %s", node, addr, wait)
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(10 * time.Second):
		}
	}
	// worker-0 hosts the CP — its NAPI pins avoid the CP cores (use 4,5);
	// plain workers pin the two slots to cores 1,2.
	cpus := []int{1, 2}
	if widx == 0 {
		cpus = []int{4, 5}
	}
	// Build ONE idempotent provisioning script covering every slot on this
	// worker, install it as a boot-time systemd unit, then run it now.
	// Rationale (v5.0.9): all of this is runtime state; netplan re-applies at
	// every boot (and cloud-init's late final stage re-applies it after early
	// provisioning) wiping VF IPs/rules — worker-1/-3 each lost their N3 IPs
	// this way. A unit ordered after network-online reasserts the config on
	// every boot, closing the whole class (reboot, halt/start, late netplan).
	var sb strings.Builder
	sb.WriteString("#!/bin/bash\n# generated by hhro-daemon v5.1.4 — eUPF VF provisioning (idempotent)\n")
	sb.WriteString("systemctl stop irqbalance 2>/dev/null\nsystemctl start kubelet 2>/dev/null\n")
	sb.WriteString("rm -f /etc/netplan/99-mtu.yaml && netplan generate 2>/dev/null\n")
	sb.WriteString("sysctl -qw net.ipv4.conf.all.arp_ignore=1 net.ipv4.conf.all.arp_announce=2\n")
	if envcfg.Bool("EUPF_HK_CONFINE", true) {
		var ex []string
		for _, c := range cpus {
			ex = append(ex, fmt.Sprintf("%d", c))
		}
		sb.WriteString(fmt.Sprintf("HK=$(seq 0 $(($(nproc)-1)) | grep -vxE '(%s)' | paste -sd,); [ -n \"$HK\" ] && for u in system.slice user.slice init.scope kubepods.slice; do systemctl set-property $u AllowedCPUs=$HK 2>/dev/null; done\n", strings.Join(ex, "|")))
	}
	for _, sl := range e.Cfg.Slots {
		if sl.Node != node {
			continue
		}
		sb.WriteString(fmt.Sprintf("ethtool --set-priv-flags %s rx_cqe_compress on 2>/dev/null\nsysctl -qw net.ipv4.conf.%s.arp_announce=2 2>/dev/null\n", sl.Iface, sl.Iface))
	}
	if url := envcfg.Get("EUPF_IMAGE_TAR_URL", ""); url != "" {
		tag := e.Cfg.Image
		if i := strings.LastIndex(tag, ":"); i >= 0 {
			tag = tag[i+1:]
		}
		sb.WriteString(fmt.Sprintf("ctr -n k8s.io images ls -q 2>/dev/null | grep -q '%s' || { curl -fso /tmp/eupf-img.tar.gz --connect-timeout 5 -m 120 '%s' && gunzip -f /tmp/eupf-img.tar.gz && ctr -n k8s.io images import /tmp/eupf-img.tar; rm -f /tmp/eupf-img.tar /tmp/eupf-img.tar.gz; }\n", tag, url))
	}
	// Idempotence guard: if every slot's MAC+IP+MTU are already in place, do
	// NOTHING. The provisioning block bounces links (down/up), which flushes
	// neighbor tables and briefly kills eUPF heartbeats — re-running it on an
	// already-correct worker cost sessions (v5.0.9 rollout killed eupf-4's).
	sb.WriteString("ok=1\n")
	n := 0
	for _, sl := range e.Cfg.Slots {
		if sl.Node != node {
			continue
		}
		cpu := cpus[n%len(cpus)]
		n++
		sb.WriteString(fmt.Sprintf(`
ip link set %[1]s down
ip link set %[1]s address 02:00:00:00:0b:%[2]d
ip link set %[1]s mtu 3000
ip link set %[1]s up
ip addr replace 10.0.1.%[2]d/24 dev %[1]s
ethtool -L %[1]s combined 1 2>/dev/null
ethtool -G %[1]s rx %[6]s tx 1024 2>/dev/null
sysctl -qw net.ipv4.conf.%[1]s.arp_ignore=1
ip route replace 10.0.1.0/24 dev %[1]s scope link src 10.0.1.%[2]d table %[2]d
ip rule del from 10.0.1.%[2]d lookup %[2]d 2>/dev/null; ip rule add from 10.0.1.%[2]d lookup %[2]d
ip neigh replace 10.0.1.16 lladdr %[3]s dev %[1]s
for gn in $(seq 100 144); do [ "$gn" = 108 ] || ip neigh replace 10.0.1.$gn lladdr %[5]s dev %[1]s nud permanent; done
comp0=$(ls /sys/class/net/%[1]s/device/msi_irqs | sort -n | sed -n 2p)
echo %[4]d > /proc/irq/$comp0/smp_affinity_list
ip link set %[1]s up
`, sl.Iface, sl.N3Octet, e.Cfg.DnVfMac, cpu, envcfg.Get("EUPF_GNB_DEFAULT_MAC", "50:7c:6f:14:e4:b2"),
			envcfg.Get("EUPF_VF_RX_RING", "1024")))
	}
	if n == 0 {
		return fmt.Errorf("no eupf slots configured on %s", node)
	}
	// assemble guard prologue now that slots are known
	var guard strings.Builder
	for _, sl := range e.Cfg.Slots {
		if sl.Node != node {
			continue
		}
		guard.WriteString(fmt.Sprintf(
			"{ ip addr show dev %[1]s 2>/dev/null | grep -q ' 10.0.1.%[2]d/24 ' && [ \"$(cat /sys/class/net/%[1]s/address)\" = \"02:00:00:00:0b:%[2]d\" ] && [ \"$(cat /sys/class/net/%[1]s/mtu)\" = \"3000\" ] && ip rule list | grep -q 'from 10.0.1.%[2]d ' ; } || ok=0\n",
			sl.Iface, sl.N3Octet))
	}
	script := strings.Replace(sb.String(), "ok=1\n", "ok=1\n"+guard.String()+"[ \"$ok\" = 1 ] && { echo already-provisioned; exit 0; }\n", 1)
	unit := `[Unit]
Description=eUPF VF provisioning (reassert runtime VF config after netplan)
After=network-online.target cloud-final.service
Wants=network-online.target
[Service]
Type=oneshot
ExecStartPre=/bin/sleep 10
ExecStart=/usr/local/sbin/eupf-vf-provision.sh
RemainAfterExit=yes
[Install]
WantedBy=cloud-init.target
`
	// v5.0.15 — ship script+unit base64-encoded: the old single-quoted
	// bash -c heredoc broke on the idempotence guard's embedded single
	// quotes (remote got a 214-byte truncated script yet exited 0, so the
	// daemon reported "provisioned" with nothing applied).
	b64s := base64.StdEncoding.EncodeToString([]byte(script))
	b64u := base64.StdEncoding.EncodeToString([]byte(unit))
	expUnit := `[Unit]
Description=per-slot XDP CPU + VF loss counters exporter (hhro-daemon provisioned)
After=network-online.target
[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/upf-cpu-exporter.py
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
`
	b64e := base64.StdEncoding.EncodeToString([]byte(upfExporterPy))
	b64eu := base64.StdEncoding.EncodeToString([]byte(expUnit))
	install := fmt.Sprintf(`echo %s | sudo -S -p '' bash -c "echo %s | base64 -d > /usr/local/sbin/eupf-vf-provision.sh; chmod 755 /usr/local/sbin/eupf-vf-provision.sh; echo %s | base64 -d > /etc/systemd/system/eupf-vf-provision.service; echo %s | base64 -d > /tmp/upf-cpu-exporter.py.new; echo %s | base64 -d > /etc/systemd/system/upf-cpu-exporter.service; if ! cmp -s /tmp/upf-cpu-exporter.py.new /usr/local/bin/upf-cpu-exporter.py; then install -m 755 /tmp/upf-cpu-exporter.py.new /usr/local/bin/upf-cpu-exporter.py; systemctl daemon-reload; systemctl enable upf-cpu-exporter.service 2>/dev/null; systemctl restart upf-cpu-exporter.service; fi; rm -f /tmp/upf-cpu-exporter.py.new; systemctl daemon-reload; systemctl reenable eupf-vf-provision.service 2>/dev/null; systemctl is-active --quiet upf-cpu-exporter.service || systemctl start upf-cpu-exporter.service; /usr/local/sbin/eupf-vf-provision.sh"`, e.Host.SudoPassword, b64s, b64u, b64e, b64eu)
	if _, err := e.Host.ExecOnWorkerAddr(ctx, addr, install); err != nil {
		return fmt.Errorf("provision %s: %w", node, err)
	}
	return nil
}

// nodeReady reports whether the k8s node exists and has condition Ready=True.
func (e *EupfActuator) nodeReady(ctx context.Context, node string) bool {
	raw, err := e.A.M.K8sGet(ctx, "/api/v1/nodes/"+node)
	if err != nil {
		return false
	}
	var n struct {
		Status struct {
			Conditions []struct {
				Type   string `json:"type"`
				Status string `json:"status"`
			} `json:"conditions"`
		} `json:"status"`
	}
	if json.Unmarshal(raw, &n) != nil {
		return false
	}
	for _, c := range n.Status.Conditions {
		if c.Type == "Ready" {
			return c.Status == "True"
		}
	}
	return false
}

// activeDnns lists the DNNs of active slots, excluding one slot index.
func (e *EupfActuator) activeDnns(ctx context.Context, exclude int) ([]string, error) {
	active, err := e.ActiveSlotIdxs(ctx)
	if err != nil {
		return nil, err
	}
	var dnns []string
	for _, s := range e.Cfg.Slots {
		if active[s.Idx] && s.Idx != exclude {
			if _, busy := e.draining.Load(fmt.Sprintf("eupf-%d", s.Idx)); busy {
				continue
			}
			dnns = append(dnns, dnnByOctet(s.N3Octet))
		}
	}
	return dnns, nil
}

// RebalanceInto evenly spreads UEs into a freshly activated slot via the
// rehome agent (SMF-initiated re-registration story). Call it asynchronously
// after DeployUPF — it waits for the slot's PFCP association to settle first.
func (e *EupfActuator) RebalanceInto(ctx context.Context, podName string, full bool) error {
	if e.Rehome == nil || !e.Rehome.Enabled {
		return nil
	}
	var idx int
	if _, err := fmt.Sscanf(podName, "eupf-%d", &idx); err != nil {
		return fmt.Errorf("bad eupf pod name %q", podName)
	}
	s := e.slotByIdx(idx)
	if s == nil {
		return fmt.Errorf("eupf-%d is not a configured slot", idx)
	}
	// wait until the slot's API answers (pod truly up — creation can take
	// minutes on a cold node), then one PFCP heartbeat cycle to associate.
	if err := e.waitSlotAPI(ctx, s.N3Octet, 8*time.Minute); err != nil {
		return err
	}
	select {
	case <-time.After(20 * time.Second):
	case <-ctx.Done():
		return ctx.Err()
	}
	dnns, err := e.activeDnns(ctx, idx)
	if err != nil {
		return err
	}
	ues, err := e.Rehome.UEsLive(ctx) // rebalance planning on ground truth (v5.1.5)
	if err != nil {
		return err
	}
	newDnn := dnnByOctet(s.N3Octet)
	// v5.0.30: "relief" (default) moves ONLY the UEs sitting on donors that
	// exceed the per-slot design capacity (UP_REBALANCE_DONOR_MIN, 4 UE at
	// the 150k/UE design point) — every move costs the UE its in-flight data
	// plane (cli_move release→establish), and the full even-spread dominated
	// the remaining ramp loss (run#7 P1 3.4% ≈ all in-move). New arrivals
	// steer to the least-loaded slot, so balance converges without touching
	// standing sessions; only genuine over-cap donors get relieved.
	var moves []RehomeMove
	if full {
		moves = planScaleOut(ues, dnns, newDnn)
	} else {
		moves = planRelief(ues, newDnn, envcfg.Int("UP_REBALANCE_DONOR_MIN", 4),
			envcfg.Int("UP_REBALANCE_RECV_MAX", 5))
	}
	if len(moves) == 0 {
		return nil
	}
	have := 0
	for _, v := range ues {
		if v.Dnn == newDnn {
			have++
		}
	}
	want := have + len(moves)
	if full {
		want = len(ues) / (len(dnns) + 1)
	}
	if err := e.Rehome.Rehome(ctx, moves); err != nil {
		return err
	}
	return e.Rehome.WaitCond(ctx, func(u map[int]ueInfo) bool {
		n := 0
		for _, v := range u {
			if v.Dnn == newDnn {
				n++
			}
		}
		return n >= want
	})
}

func (e *EupfActuator) PoolRelief(ctx context.Context, donorMin, maxMoves int) (int, map[string]int, error) {
	if e.Rehome == nil || !e.Rehome.Enabled {
		return 0, nil, nil
	}
	idxs, err := e.ActiveSlotIdxs(ctx)
	if err != nil || len(idxs) < 2 {
		return 0, nil, err
	}
	dnnSet := map[string]bool{}
	for i := range idxs {
		if s := e.slotByIdx(i); s != nil {
			if _, busy := e.draining.Load(fmt.Sprintf("eupf-%d", i)); busy {
				continue
			}
			dnnSet[dnnByOctet(s.N3Octet)] = true
		}
	}
	ues, err := e.Rehome.UEsLive(ctx)
	if err != nil {
		return 0, nil, err
	}
	cnt := map[string]int{}
	byDnn := map[string][]int{}
	for d := range dnnSet {
		cnt[d] = 0
	}
	for i, u := range ues {
		if dnnSet[u.Dnn] {
			cnt[u.Dnn]++
			if eligibleForMove(u) { // fresh arrivals count as load but are never moved
				byDnn[u.Dnn] = append(byDnn[u.Dnn], i)
			}
		}
	}
	var dnns []string
	for d := range cnt {
		dnns = append(dnns, d)
	}
	sort.Strings(dnns)
	var moves []RehomeMove
	for len(moves) < maxMoves {
		hot, cold := "", ""
		for _, d := range dnns {
			if hot == "" || cnt[d] > cnt[hot] {
				hot = d
			}
			if cold == "" || cnt[d] < cnt[cold] {
				cold = d
			}
		}
		if cnt[hot] <= donorMin || cnt[cold] >= donorMin || cnt[hot]-cnt[cold] < 2 {
			break
		}
		us := byDnn[hot]
		if len(us) == 0 { // hot slot holds only fresh UEs: nothing movable this round
			break
		}
		sort.Ints(us)
		ue := us[len(us)-1]
		byDnn[hot] = us[:len(us)-1]
		moves = append(moves, RehomeMove{UE: ue, Dnn: cold})
		cnt[hot]--
		cnt[cold]++
	}
	if len(moves) == 0 {
		for d := range cnt {
			cnt[d] = cnt[d]*100 + len(byDnn[d])
		}
		return 0, cnt, nil
	}
	return len(moves), cnt, e.Rehome.Rehome(ctx, moves)
}

// waitSlotAPI polls the slot's eUPF HTTP API until it answers.
func (e *EupfActuator) waitSlotAPI(ctx context.Context, octet int, max time.Duration) error {
	hc := &http.Client{Timeout: 3 * time.Second}
	end := time.Now().Add(max)
	url := fmt.Sprintf("http://10.0.1.%d:8080/api/v1/xdp_stats", octet)
	for {
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if resp, err := hc.Do(req); err == nil {
			resp.Body.Close()
			if resp.StatusCode == 200 {
				return nil
			}
		}
		if time.Now().After(end) {
			return fmt.Errorf("eupf slot .%d API not up within %s", octet, max)
		}
		select {
		case <-time.After(10 * time.Second):
		case <-ctx.Done():
			return ctx.Err()
		}
	}
}

// DrainAndDelete rehomes the victim slot's UEs onto the remaining slots, then
// deletes the pod — zero-loss scale-in (UEs leave BEFORE capacity does). If
// the drain fails the delete is aborted; the autoscaler retries next tick.
func (e *EupfActuator) DrainAndDelete(parent context.Context, podName string) error {
	if _, busy := e.draining.LoadOrStore(podName, true); busy {
		return fmt.Errorf("%s: drain already in flight", podName)
	}
	defer e.draining.Delete(podName)
	ctx, dcancel := context.WithCancel(parent)
	defer dcancel()
	e.drainCancel.Store(podName, dcancel)
	defer e.drainCancel.Delete(podName)
	cancelled := func(err error) error {
		if ctx.Err() != nil && parent.Err() == nil {
			return ErrDrainCancelled
		}
		return err
	}
	var idx int
	if _, err := fmt.Sscanf(podName, "eupf-%d", &idx); err != nil {
		return fmt.Errorf("bad eupf pod name %q", podName)
	}
	s := e.slotByIdx(idx)
	if s == nil {
		return fmt.Errorf("eupf-%d is not a configured slot", idx)
	}
	moved := map[int]bool{}
	if e.Rehome != nil && e.Rehome.Enabled {
		victimDnn := dnnByOctet(s.N3Octet)
		// two-phase: tell the harness (via the agent) not to place arrivals here
		// for the whole drain; retracted when this function returns (deleted or
		// aborted). Best effort — an old agent without the field just ignores it.
		if err := e.Rehome.SetSlotDrain(ctx, victimDnn, true); err != nil {
			slog.Warn("drain: slot-drain publish failed", "slot", podName, "err", err)
		}
		defer func() {
			bg, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer cancel()
			if err := e.Rehome.SetSlotDrain(bg, victimDnn, false); err != nil {
				slog.Warn("drain: slot-drain retract failed", "slot", podName, "err", err)
			}
		}()
		if err := e.drainMoves(ctx, podName, idx, victimDnn, moved); err != nil {
			return cancelled(err)
		}
	}
	// two-phase: tell the harness (via the agent) not to place arrivals here
	// for the whole drain; retracted when this function returns (deleted or
	// aborted). Best effort — an old agent without the field just ignores it.
	// block until the slot is empty — deleting early would cut live UEs
	// v5.0.33: the agent view (uemap) is written at harness minute boundaries
	// and can be up to ~60s stale — an arrival can land on the victim after
	// the view said "empty" (run#10: silent session kill on scale-in).
	// Verify the DATA PLANE is empty before deleting: poll the slot's own
	// pfcp_sessions until null. Make-before-break old anchors linger ~30s
	// after a move, so allow 90s.
	// v5.0.34: a hard abort here DEADLOCKED all scale-in for the entire
	// run#11 ramp-down (20 consecutive aborts): zombie sessions (mbb
	// old anchors whose ps-release timed out, departures whose UE died
	// before SMF finished the release) never clear on their own. Arbitrate
	// with the agent view: if no live UE maps to the victim's DNN, the
	// leftovers are zombies -> delete anyway (SMF orphans are parked-state
	// cleanup, not live traffic). Only a live-UE sighting aborts.
	// zombies only — proceed
	for round := 0; ; round++ {
		if err := e.waitPendingReleases(ctx, podName); err != nil {
			return cancelled(err)
		}
		max := 210 * time.Second
		if round > 0 {
			max = 150 * time.Second
		}
		victimDnn := dnnByOctet(s.N3Octet)
		err := e.waitSlotSessionsEmptyOrLive(ctx, s.N3Octet, max, victimDnn)
		if err == nil {
			break
		}
		if ctx.Err() != nil {
			return cancelled(err)
		}
		if e.Rehome == nil || !e.Rehome.Enabled {
			return fmt.Errorf("drain %s: %w (delete aborted)", podName, err)
		}
		ues, uerr := e.Rehome.UEsLive(ctx) // zombie arbitration MUST use ground truth (v5.1.5)
		if uerr != nil {
			return cancelled(fmt.Errorf("drain %s: %w (agent unreachable, delete aborted)", podName, err))
		}
		live := 0
		for _, v := range ues {
			if v.Dnn == victimDnn {
				live++
			}
		}
		if live == 0 {
			slog.Warn("drain: deleting slot with leftover sessions (zombie arbitration)",
				"slot", podName, "octet", s.N3Octet, "err", err.Error())
			break
		}
		if round >= 4 {
			return fmt.Errorf("drain %s: %w and live UE present after %d re-plans (delete aborted)", podName, err, round)
		}
		slog.Warn("drain: live UE on victim after plan — re-planning", "slot", podName, "live", live, "round", round+1)
		if err := e.drainMoves(ctx, podName, idx, victimDnn, moved); err != nil {
			return cancelled(err)
		}
	}
	if ctx.Err() != nil {
		return cancelled(ctx.Err())
	}
	return e.DeleteUPF(parent, podName, true)
}

var ErrDrainCancelled = errors.New("drain cancelled: slot retained (reversible scale-in)")

// CancelDrain aborts an in-flight drain-then-delete of podName. Returns false if none.
func (e *EupfActuator) CancelDrain(podName string) bool {
	v, ok := e.drainCancel.Load(podName)
	if !ok {
		return false
	}
	v.(context.CancelFunc)()
	return true
}

// DrainInFlight returns one pod currently being drained, if any.
func (e *EupfActuator) DrainInFlight() (string, bool) {
	name, found := "", false
	e.draining.Range(func(k, _ any) bool { name, found = k.(string), true; return false })
	return name, found
}

// drainMoves plans and executes the victim's UE moves and waits for the agent view
// to show the victim DNN empty. Called once by DrainAndDelete and again per re-plan.
func (e *EupfActuator) drainMoves(ctx context.Context, podName string, idx int, victimDnn string, already map[int]bool) error {
	dnns, err := e.activeDnns(ctx, idx)
	if err != nil {
		return err
	}
	ues, err := e.Rehome.UEsLive(ctx) // ground truth — cached view can be stale (v5.1.5)
	if err != nil {
		return fmt.Errorf("drain %s: %w", podName, err)
	}
	for i := range already {
		delete(ues, i)
	}
	moves := planScaleIn(ues, dnns, victimDnn)
	for _, m := range moves {
		already[m.UE] = true
	}
	dist := map[string]int{}
	for _, u := range ues {
		dist[u.Dnn]++
	}
	slog.Info("drain: plan", "slot", podName, "victim", victimDnn, "targets", fmt.Sprint(dnns),
		"dist", fmt.Sprint(dist), "cap", scaleInPackCap(), "moves", fmt.Sprint(moves))
	if err := e.Rehome.Rehome(ctx, moves); err != nil {
		return fmt.Errorf("drain %s: %w (delete aborted)", podName, err)
	}
	// block until the slot is empty — deleting early would cut live UEs
	if err := e.Rehome.WaitCond(ctx, func(u map[int]ueInfo) bool {
		for _, v := range u {
			if v.Dnn == victimDnn {
				return false
			}
		}
		return true
	}); err != nil {
		return fmt.Errorf("drain %s: %w (delete aborted)", podName, err)
	}
	return nil
}

func (e *EupfActuator) waitPendingReleases(ctx context.Context, podName string) error {
	if e.Rehome == nil || !e.Rehome.Enabled {
		return nil
	}
	deadline := time.Now().Add(300 * time.Second)
	for {
		n, err := e.Rehome.PendingReleases(ctx)
		if err != nil || n == 0 {
			return nil
		}
		if time.Now().After(deadline) {
			slog.Warn("drain: agent still owes old-anchor releases, proceeding anyway",
				"slot", podName, "pending", n)
			return nil
		}
		select {
		case <-time.After(5 * time.Second):
		case <-ctx.Done():
			return ctx.Err()
		}
	}
}

// errLiveOnVictim: the agent view shows a live UE on the victim DNN while we wait for
// the slot's sessions to clear — re-plan now instead of burning the whole wait budget.
var errLiveOnVictim = fmt.Errorf("live UE seen on victim during session wait")

func (e *EupfActuator) waitSlotSessionsEmptyOrLive(ctx context.Context, octet int, max time.Duration, victimDnn string) error {
	hc := &http.Client{Timeout: 3 * time.Second}
	end := time.Now().Add(max)
	url := fmt.Sprintf("http://10.0.1.%d:8080/api/v1/pfcp_sessions", octet)
	liveStreak := 0
	lastView := time.Time{}
	for {
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if resp, err := hc.Do(req); err == nil {
			b, rerr := io.ReadAll(io.LimitReader(resp.Body, 64))
			resp.Body.Close()
			if rerr == nil && resp.StatusCode == 200 {
				body := strings.TrimSpace(string(b))
				if body == "null" || body == "[]" || body == "" {
					return nil
				}
			}
		}
		if time.Now().After(end) {
			return fmt.Errorf("eupf slot .%d still has sessions after %s", octet, max)
		}
		if e.Rehome != nil && e.Rehome.Enabled && time.Since(lastView) >= 10*time.Second {
			lastView = time.Now()
			if ues, uerr := e.Rehome.UEs(ctx); uerr == nil {
				live := 0
				for _, v := range ues {
					if v.Dnn == victimDnn {
						live++
					}
				}
				if live > 0 {
					liveStreak++
					if liveStreak >= 2 {
						return errLiveOnVictim
					}
				} else {
					liveStreak = 0
				}
			}
		}
		select {
		case <-time.After(5 * time.Second):
		case <-ctx.Done():
			return ctx.Err()
		}
	}
}

func (e *EupfActuator) waitSlotSessionsEmpty(ctx context.Context, octet int, max time.Duration) error {
	hc := &http.Client{Timeout: 3 * time.Second}
	end := time.Now().Add(max)
	url := fmt.Sprintf("http://10.0.1.%d:8080/api/v1/pfcp_sessions", octet)
	for {
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if resp, err := hc.Do(req); err == nil {
			b, rerr := io.ReadAll(io.LimitReader(resp.Body, 64))
			resp.Body.Close()
			if rerr == nil && resp.StatusCode == 200 {
				body := strings.TrimSpace(string(b))
				if body == "null" || body == "[]" || body == "" {
					return nil
				}
			}
		}
		if time.Now().After(end) {
			return fmt.Errorf("eupf slot .%d still has sessions after %s", octet, max)
		}
		select {
		case <-time.After(5 * time.Second):
		case <-ctx.Done():
			return ctx.Err()
		}
	}
}
