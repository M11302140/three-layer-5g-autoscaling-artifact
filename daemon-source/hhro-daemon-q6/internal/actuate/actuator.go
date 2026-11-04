package actuate

import (
	"os"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
	"github.com/anon/hhro-daemon/internal/harvester"
	"github.com/anon/hhro-daemon/internal/master"
	"github.com/anon/hhro-daemon/internal/sshexec"
)

type Actuator struct {
	H            *harvester.Harvester
	M            *master.MasterCluster                            // for pod-level scaling
	Host         *sshexec.HostExec                                // optional: orphan-route cleanup on DeleteVyOS
	JoinProvider func(context.Context) (string, error)            // returns full kubeadm join command
	NodeReaper   func(ctx context.Context, nodeName string) error // drain + delete Node
	Cfg          WorkerCfg
	VyosCfg      VyosCfg
	Groups       GroupCfg

	mu              sync.Mutex
	firstNotRunning map[string]time.Time // ReapStuckVMs: first time each VM was seen non-Running
	cooldVM   time.Time
	cooldCP   time.Time
	cooldUP   time.Time
	cooldVyos time.Time
	cooldUpf  time.Time
}

// preflightCapacity checks Harvester host has enough free memory + VFs for
// the requested VM spec. Returns nil iff scale_out can proceed. v1.38 — gates
// CreateWorker / DeployVyOS so daemon doesn't fire unfulfillable spawns that
// leave VMs stuck Scheduling/Pending and trip the reaper.
func (a *Actuator) preflightCapacity(ctx context.Context, kind string, memGi, vfs int) error {
	node := envcfg.Get("HARVESTER_NODE", "user-master")
	cap, err := a.H.CheckCapacity(ctx, node)
	if err != nil {
		// don't block on capacity probe failure — log and proceed; reaper
		// will catch genuinely-stuck VMs as a safety net.
		return nil
	}
	// v5.0.6 — HARD host-memory reserve. The Harvester host OOMs catastrophically
	// when guest memory approaches its 60G (2026-06-15 PausedIOError storm;
	// 2026-07-03 near-miss: 52/60 used + a 2Gi VyOS would have tipped it).
	// Require the VM's memory PLUS a standing reserve to be free.
	reserveBytes := int64(envcfg.Int("HOST_MEM_RESERVE_GI", 4)) * 1024 * 1024 * 1024
	needBytes := int64(memGi)*1024*1024*1024 + reserveBytes
	if cap.FreeMemoryBytes < needBytes {
		return fmt.Errorf("preflight %s: free memory %d MiB < requested %d MiB (incl %d GiB host reserve)",
			kind, cap.FreeMemoryBytes/1024/1024, needBytes/1024/1024, reserveBytes/1024/1024/1024)
	}
	if int64(vfs) > 0 && cap.FreeVFs < int64(vfs) {
		return fmt.Errorf("preflight %s: free VFs %d < requested %d",
			kind, cap.FreeVFs, vfs)
	}
	return nil
}

// Per-action cooldown buckets per HHRO §3.
func (a *Actuator) cooldownExpired(key string) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	now := time.Now()
	switch key {
	case "vm":
		return now.After(a.cooldVM)
	case "cp":
		return now.After(a.cooldCP)
	case "up":
		return now.After(a.cooldUP)
	case "vyos":
		return now.After(a.cooldVyos)
	case "upf":
		return now.After(a.cooldUpf)
	}
	return true
}

func (a *Actuator) resetCooldown(key string, d time.Duration) {
	a.mu.Lock()
	defer a.mu.Unlock()
	t := time.Now().Add(d)
	switch key {
	case "vm":
		a.cooldVM = t
	case "cp":
		a.cooldCP = t
	case "up":
		a.cooldUP = t
	case "vyos":
		a.cooldVyos = t
	case "upf":
		a.cooldUpf = t
	}
}

// CooldownExpired / ResetCooldown expose the buckets to the UPF actuator (in
// the same package) and to Rebalancer (different package) without unlocking
// internals.
func (a *Actuator) CooldownExpired(key string) bool          { return a.cooldownExpired(key) }
func (a *Actuator) ResetCooldown(key string, d time.Duration) { a.resetCooldown(key, d) }

func (a *Actuator) nextIndex(ctx context.Context) (int, error) {
	vms, err := a.H.ListVMs(ctx, "")
	if err != nil {
		return 0, err
	}
	used := map[int]bool{}
	re := regexp.MustCompile(`^` + regexp.QuoteMeta(a.Cfg.NamePrefix) + `(\d+)$`)
	for _, v := range vms {
		m := re.FindStringSubmatch(v.Name)
		if len(m) == 2 {
			n, _ := strconv.Atoi(m[1])
			used[n] = true
		}
	}
	for i := 0; i < 256; i++ {
		if !used[i] {
			return i, nil
		}
	}
	return 0, fmt.Errorf("no free worker index")
}

// workerMgmtOctet maps a worker index to its mgmt last-octet, SKIPPING .53
// which is permanently used by the data-network VM. worker-0 (the permanent
// base node) keeps MgmtBase (.52); daemon-created worker-N≥1 get MgmtBase+1+N
// → .54/.55/.56 for base 52, leaving .53 for data-network. The old MgmtBase+idx
// gave worker-1 = .53 → mgmt IP collision with data-network. Same helper drives
// CreateWorker and workerAddrForNode so create-time and address-time agree.
func workerMgmtOctet(base, idx int) int {
	if idx == 0 {
		return base
	}
	return base + 1 + idx
}

func (a *Actuator) CreateWorker(ctx context.Context, force bool) (string, error) {
	if !force && !a.cooldownExpired("vm") {
		return "", fmt.Errorf("vm cooldown active")
	}
	if err := a.preflightCapacity(ctx, "worker", a.Cfg.MemoryGi, 1); err != nil {
		return "", err
	}
	idx, err := a.nextIndex(ctx)
	if err != nil {
		return "", err
	}
	return a.createWorkerIdx(ctx, idx)
}

func (a *Actuator) CreateWorkerNamed(ctx context.Context, name string) (string, bool, error) {
	var idx int
	if _, err := fmt.Sscanf(name, a.Cfg.NamePrefix+"%d", &idx); err != nil {
		return "", false, fmt.Errorf("bad worker name %q", name)
	}
	vms, err := a.H.ListVMs(ctx, "")
	if err != nil {
		return "", false, err
	}
	for _, v := range vms {
		if v.Name == name {
			return name, false, nil
		}
	}
	if err := a.preflightCapacity(ctx, "worker", a.Cfg.MemoryGi, 1); err != nil {
		return "", false, err
	}
	created, err := a.createWorkerIdx(ctx, idx)
	return created, err == nil, err
}

func (a *Actuator) createWorkerIdx(ctx context.Context, idx int) (string, error) {
	name := fmt.Sprintf("%s%d", a.Cfg.NamePrefix, idx)
	mgmtIP := fmt.Sprintf("%s%d", a.Cfg.MgmtPrefix, workerMgmtOctet(a.Cfg.MgmtBase, idx))
	dataIP := fmt.Sprintf("%s%d", a.Cfg.DataPrefix, a.Cfg.DataBase+idx)
	// v5.0.8 — the legacy data-IP scheme COLLIDES at idx 2: 14+2 = 10.0.1.16
	// = the DN reflector IP. A worker carrying .16 makes every eUPF's
	// bpf_fib_lookup(.16) resolve LOCAL -> XDP_PASS -> its slots blackhole ALL
	// uplink (and poisons the DN path fleet-wide). In eUPF mode the legacy
	// data IP serves nothing (slot N3 IPs come from VF provisioning) — park
	// the netplan address high above every live range instead.
	if os.Getenv("EUPF_ENABLED") != "false" {
		dataIP = fmt.Sprintf("%s%d", a.Cfg.DataPrefix, 200+idx)
	}

	join := ""
	if a.JoinProvider != nil {
		j, err := a.JoinProvider(ctx)
		if err != nil {
			return "", fmt.Errorf("join command: %w", err)
		}
		join = j
	}

	userdata := renderUserData(name, join)
	netdata := renderNetworkData(mgmtIP, dataIP, a.Cfg)
	// v5.0.11 — eUPF mode: netplan must NOT manage the data VFs at all. Any
	// systemd-networkd reload re-applies the netplan config and WIPES the
	// runtime VF state (N3 IP, rules, MTU) — worker-2 lost 10.0.1.34 three
	// times this way. VF config is owned exclusively by the provisioning unit.
	if os.Getenv("EUPF_ENABLED") != "false" {
		netdata = renderNetworkDataMgmtOnly(mgmtIP, a.Cfg)
	}
	secretName := name + "-cloudinit"

	secretBody, _ := json.Marshal(map[string]any{
		"apiVersion": "v1",
		"kind":       "Secret",
		"type":       "secret",
		"metadata": map[string]any{
			"name":      secretName,
			"namespace": a.H.Namespace,
			"labels":    map[string]string{"harvesterhci.io/cloud-init-template": "harvester"},
		},
		"data": map[string]string{
			"userdata":    base64.StdEncoding.EncodeToString([]byte(userdata)),
			"networkdata": base64.StdEncoding.EncodeToString([]byte(netdata)),
		},
	})
	pvcName := name + "-disk-0"
	_ = a.H.DeleteSecret(ctx, secretName)
	_ = a.H.DeletePVC(ctx, pvcName)
	if err := a.H.CreateSecret(ctx, secretBody); err != nil {
		return "", fmt.Errorf("create secret: %w", err)
	}

	vmBody := renderVM(name, secretName, a.Cfg)
	if err := a.H.CreateVM(ctx, vmBody); err != nil {
		return "", fmt.Errorf("create vm: %w", err)
	}

	a.resetCooldown("vm", envcfg.Dur("VM_COOLDOWN", 5*time.Minute))
	return name, nil
}

func (a *Actuator) DeleteWorker(ctx context.Context, name string, force bool) error {
	if !force && !a.cooldownExpired("vm") {
		return fmt.Errorf("vm cooldown active")
	}
	var nodeErr error
	if a.NodeReaper != nil {
		nodeErr = a.NodeReaper(ctx, name)
	}
	if err := a.H.DeleteVM(ctx, name); err != nil {
		if nodeErr != nil {
			return fmt.Errorf("delete vm: %w (also: drain/delete node: %v)", err, nodeErr)
		}
		return err
	}
	_ = a.H.DeletePVC(ctx, name+"-disk-0")
	_ = a.H.DeleteSecret(ctx, name+"-cloudinit")
	a.resetCooldown("vm", envcfg.Dur("VM_COOLDOWN", 5*time.Minute))
	return nodeErr
}

// ReapStuckVMs removes daemon-managed VMs stuck non-Running for too long
// (typical cause: Harvester host out of disk for Longhorn → VM CR succeeds
// but virt-launcher never starts).
func (a *Actuator) ReapStuckVMs(ctx context.Context, stuckFor time.Duration) ([]string, error) {
	vms, err := a.H.ListVMs(ctx, "")
	if err != nil {
		return nil, err
	}
	now := time.Now()
	if a.firstNotRunning == nil {
		a.firstNotRunning = map[string]time.Time{}
	}
	reaped := []string{}
	for _, v := range vms {
		if !isDaemonManaged(v.Name, a.Cfg.NamePrefix, a.VyosCfg.NamePrefix) {
			continue
		}
		// NEVER reap the permanent min worker. 2026-06-12 incident: a routine
		// VMI restart (CPU resize) put worker-0 briefly in a non-Running phase
		// and the reaper deleted the VM+PVC because "stuck" was measured from
		// VM CREATION (34 days > any window), destroying the long-lived root
		// disk. worker-0's lifecycle is owned by the operator, not the daemon.
		if v.Name == a.Cfg.NamePrefix+"0" {
			continue
		}
		if v.Phase == "Running" {
			delete(a.firstNotRunning, v.Name)
			continue
		}
		// Measure stuck-time from when we FIRST observed the VM non-Running,
		// not from VM creation — a momentarily-stopped old VM is not "stuck".
		first, seen := a.firstNotRunning[v.Name]
		if !seen {
			a.firstNotRunning[v.Name] = now
			continue
		}
		if now.Sub(first) < stuckFor {
			continue
		}
		_ = a.H.DeleteVM(ctx, v.Name)
		_ = a.H.DeletePVC(ctx, v.Name+"-disk-0")
		_ = a.H.DeleteSecret(ctx, v.Name+"-cloudinit")
		a.resetCooldown("vm", 0)
		reaped = append(reaped, v.Name)
	}
	return reaped, nil
}

func isDaemonManaged(name, workerPrefix, vyosPrefix string) bool {
	re := regexp.MustCompile(`^` + regexp.QuoteMeta(workerPrefix) + `\d+$`)
	if re.MatchString(name) {
		return true
	}
	re = regexp.MustCompile(`^` + regexp.QuoteMeta(vyosPrefix) + `\d+$`)
	return re.MatchString(name)
}

// ScaleGroup adjusts a Deployment's replica count by `delta`, bounded by
// [min, max]. Returns the new replica count (or current if no-op).
func (a *Actuator) ScaleGroup(ctx context.Context, key string, delta int, force bool) (int, error) {
	if a.M == nil {
		return 0, fmt.Errorf("master-cluster client unavailable; cannot scale pod groups")
	}
	if !force && !a.cooldownExpired(key) {
		return 0, fmt.Errorf("%s cooldown active", key)
	}
	var deploy string
	var minR, maxR int
	switch key {
	case "cp":
		deploy, minR, maxR = a.Groups.CPDeploy, a.Groups.MinCP, a.Groups.MaxCP
	case "up":
		deploy, minR, maxR = a.Groups.UPDeploy, a.Groups.MinUP, a.Groups.MaxUP
	default:
		return 0, fmt.Errorf("unknown group %q", key)
	}
	cur, err := a.M.GetDeploymentReplicas(ctx, a.Groups.Namespace, deploy)
	if err != nil {
		return 0, err
	}
	target := cur + delta
	if target < minR {
		return cur, fmt.Errorf("at min: rep=%d min=%d", cur, minR)
	}
	if target > maxR {
		return cur, fmt.Errorf("at max: rep=%d max=%d", cur, maxR)
	}
	if target == cur {
		return cur, nil
	}
	if err := a.M.PatchDeploymentReplicas(ctx, a.Groups.Namespace, deploy, target); err != nil {
		return cur, err
	}
	cd := envcfg.Dur(map[string]string{"cp": "CP_COOLDOWN", "up": "UP_COOLDOWN"}[key], 60*time.Second)
	a.resetCooldown(key, cd)
	return target, nil
}

// ---- worker cloud-init templates ----

const userDataTmpl = `#cloud-config
hostname: {{NAME}}
package_update: false
#   cloud-init analyze blame → config-package_update_upgrade_install 228.3s
users:
  - name: user
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: users, admin
    shell: /bin/bash
    lock_passwd: false

chpasswd:
  list: |
    user:user
  expire: false
ssh_pwauth: true

write_files:
  - path: /usr/local/bin/hhro-bootstrap.sh
    permissions: '0755'
    content: |
      #!/bin/bash
      set -e
      # v5.0.17: goldens built via a scratch VM may carry a masked kubelet
      # (the scratch boot masks it to keep the image from joining the
      # cluster) — unmask unconditionally or kubeadm join hangs at
      # kubelet-wait and the worker never becomes a node.
      systemctl unmask kubelet 2>/dev/null || true
      if [ -f /etc/kubernetes/kubelet.conf ]; then
        systemctl enable --now kubelet
        exit 0
      fi
      kubeadm reset -f --cri-socket unix:///run/containerd/containerd.sock || true
{{JOIN}}

runcmd:
  - systemctl enable --now qemu-guest-agent.service
  - /usr/local/bin/hhro-bootstrap.sh
`

func renderUserData(name, joinCmd string) string {
	join := ""
	if joinCmd != "" {
		join = "      " + joinCmd
	}
	r := strings.NewReplacer("{{NAME}}", name, "{{JOIN}}", join)
	return r.Replace(userDataTmpl)
}

const networkDataTmpl = `version: 2
ethernets:
  enp1s0:
    dhcp4: false
    addresses:
      - {{MGMT_IP}}/24
    routes:
      - to: default
        via: {{GATEWAY}}
    nameservers:
      addresses:
        - {{DNS1}}
        - {{DNS2}}
  enp15s0:
    mtu: 9000
    dhcp4: false
    addresses:
      - {{DATA_IP}}/24
    optional: true
    ignore-carrier: true
`

// renderNetworkDataMgmtOnly: netplan v2 with ONLY the virtio mgmt NIC —
// the SR-IOV VFs stay unmanaged (provisioning unit owns them).
func renderNetworkDataMgmtOnly(mgmtIP string, c WorkerCfg) string {
	return fmt.Sprintf(`version: 2
ethernets:
  enp1s0:
    addresses: [%s/24]
    gateway4: %s
    nameservers:
      addresses: [%s, %s]
`, mgmtIP, c.MgmtGateway, c.DNS1, c.DNS2)
}

func renderNetworkData(mgmtIP, dataIP string, c WorkerCfg) string {
	r := strings.NewReplacer(
		"{{MGMT_IP}}", mgmtIP,
		"{{DATA_IP}}", dataIP,
		"{{GATEWAY}}", c.MgmtGateway,
		"{{DNS1}}", c.DNS1,
		"{{DNS2}}", c.DNS2,
	)
	out := r.Replace(networkDataTmpl)
	// dual-leg: add the internal VLAN sub-interface so UPF-clone GTP-U anchors
	// (10.20.0.x/32, added by ReconcileAliases on enp15s0.<vlan>) are reachable.
	return out
}

func renderVM(name, secretName string, c WorkerCfg) []byte {
	pvcName := name + "-disk-0"
	vm := map[string]any{
		"apiVersion": "kubevirt.io/v1",
		"kind":       "VirtualMachine",
		"metadata": map[string]any{
			"name":      name,
			"namespace": "default",
			"annotations": map[string]string{
				"harvesterhci.io/vmRunStrategy": "RerunOnFailure",
				"harvesterhci.io/volumeClaimTemplates": fmt.Sprintf(
					`[{"metadata":{"name":"%s","annotations":{"harvesterhci.io/imageId":"%s"}},"spec":{"accessModes":["ReadWriteMany"],"resources":{"requests":{"storage":"%dGi"}},"volumeMode":"Block","storageClassName":"%s"}}]`,
					pvcName, c.ImageRef, c.DiskGi, c.StorageClass),
			},
			"labels": map[string]string{
				"harvesterhci.io/creator": "harvester",
				"harvesterhci.io/os":      "linux",
				"hhro.io/managed":         "true",
			},
		},
		"spec": map[string]any{
			"runStrategy": "Always", // v5.0: delete-vmi must mean RESTART (RerunOnFailure treats a graceful stop as final → VM stays off)
			"template": map[string]any{
				"metadata": map[string]any{
					"labels": map[string]string{
						"harvesterhci.io/vmName": name,
						"hhro.io/managed":        "true",
					},
				},
				"spec": map[string]any{
					"affinity": map[string]any{
						"nodeAffinity": map[string]any{
							"requiredDuringSchedulingIgnoredDuringExecution": map[string]any{
								"nodeSelectorTerms": []any{
									map[string]any{"matchExpressions": []any{
										map[string]any{"key": "network.harvesterhci.io/mgmt", "operator": "In", "values": []string{"true"}},
									}},
								},
							},
						},
					},
					"architecture": "amd64",
					"domain": map[string]any{
						"cpu":     map[string]any{"cores": c.CPUCores, "sockets": 1, "threads": 1, "maxSockets": 1},
						"machine": map[string]any{"type": "q35"},
						"memory":  map[string]any{"guest": fmt.Sprintf("%dGi", c.MemoryGi)},
						"resources": map[string]any{
							"limits":   map[string]string{"cpu": fmt.Sprintf("%d", c.CPUCores), "memory": fmt.Sprintf("%dGi", c.MemoryGi)},
							"requests": map[string]string{"cpu": "250m", "memory": fmt.Sprintf("%dGi", c.MemoryGi)},
						},
						"features": map[string]any{"acpi": map[string]any{"enabled": true}},
						"devices": map[string]any{
							"disks": []any{
								map[string]any{"name": "disk-0", "bootOrder": 1, "disk": map[string]any{"bus": "virtio"}},
								map[string]any{"name": "cloudinitdisk", "disk": map[string]any{"bus": "virtio"}},
							},
							"interfaces": []any{
								map[string]any{"name": "default", "model": "virtio", "bridge": map[string]any{}},
							},
							"hostDevices": workerHostDevices(name, c),
							"inputs": []any{map[string]any{"bus": "usb", "name": "tablet", "type": "tablet"}},
						},
					},
					"hostname":                      name,
					"evictionStrategy":              "LiveMigrateIfPossible",
					"terminationGracePeriodSeconds": 120,
					"networks": []any{
						map[string]any{"name": "default", "multus": map[string]any{"networkName": c.NetworkName}},
					},
					"volumes": []any{
						map[string]any{"name": "disk-0", "persistentVolumeClaim": map[string]any{"claimName": pvcName}},
						map[string]any{"name": "cloudinitdisk", "cloudInitNoCloud": map[string]any{
							"secretRef":            map[string]string{"name": secretName},
							"networkDataSecretRef": map[string]string{"name": secretName},
						}},
					},
				},
			},
		},
	}
	b, _ := json.Marshal(vm)
	return b
}

// workerHostDevices renders VFCount SR-IOV VF entries. eUPF era: 2 VFs per
// worker (one per eUPF slot); the pool is flat, names are cosmetic labels.
func workerHostDevices(name string, c WorkerCfg) []any {
	n := c.VFCount
	if n < 1 {
		n = 1
	}
	out := []any{map[string]any{"deviceName": c.VFResourceName, "name": vfDisplayName(name)}}
	for i := 1; i < n; i++ {
		out = append(out, map[string]any{"deviceName": c.VFResourceName, "name": fmt.Sprintf("eupf%d-vf", i)})
	}
	return out
}

// vfDisplayName returns a Harvester-PCIDevice-style hostDevices entry name
// (e.g. "anon-master-000001005") so the dashboard SHOWS the VF attachment —
// it only renders hostDevices whose name matches a PCIDevice object; the
// daemon's old literal "vf0" made daemon-created VMs look VF-less. Display
// only: the actual VF is allocated by the device plugin at schedule time
// (Harvester's own attach flow has the same nominal mapping). Distinct per
// VM index to avoid two VMs displaying the same device.
func vfDisplayName(vmName string) string {
	pool := strings.Split(envcfg.Get("VF_DISPLAY_NAMES",
		"anon-master-000001005,anon-master-000001006,anon-master-000001007,anon-master-000001010,anon-master-000001011"), ",")
	idx := 0
	if n := strings.LastIndexByte(vmName, '-'); n >= 0 {
		if v, err := strconv.Atoi(vmName[n+1:]); err == nil {
			idx = v
		}
	}
	if strings.HasPrefix(vmName, "vyos-") {
		idx = len(pool) - 1 - idx // vyos indexes from the tail, workers from the head
		if idx < 0 {
			idx = 0
		}
	}
	return strings.TrimSpace(pool[idx%len(pool)])
}
