package actuate

import (
	"context"
	_ "embed"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log/slog"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

func (a *Actuator) nextVyosIndex(ctx context.Context) (int, error) {
	vms, err := a.H.ListVMs(ctx, "")
	if err != nil {
		return 0, err
	}
	used := map[int]bool{}
	re := regexp.MustCompile(`^` + regexp.QuoteMeta(a.VyosCfg.NamePrefix) + `(\d+)$`)
	for _, v := range vms {
		m := re.FindStringSubmatch(v.Name)
		if len(m) == 2 {
			n, _ := strconv.Atoi(m[1])
			used[n] = true
		}
	}
	maxIdx := envcfg.Int("VYOS_MAX", 3)
	for i := 0; i < maxIdx; i++ {
		if !used[i] {
			return i, nil
		}
	}
	return 0, fmt.Errorf("no free vyos index below VYOS_MAX=%d (old VM still terminating?)", maxIdx)
}

// DeployVyOS creates one VyOS VM with stateless forwarding pre-configured via
// cloud-init. API → "VM Ready + fully configured" ~ 2 minutes.
func (a *Actuator) DeployVyOS(ctx context.Context, force bool) (string, error) {
	if !force && !a.cooldownExpired("vyos") {
		return "", fmt.Errorf("vyos cooldown active")
	}
	if err := a.preflightCapacity(ctx, "vyos", a.VyosCfg.MemoryGi, 1); err != nil {
		return "", err
	}
	idx, err := a.nextVyosIndex(ctx)
	if err != nil {
		return "", err
	}
	c := a.VyosCfg
	name := fmt.Sprintf("%s%d", c.NamePrefix, idx)
	mgmtIP := fmt.Sprintf("%s%d", c.MgmtPrefix, c.MgmtBase+idx)
	dataIP := fmt.Sprintf("%s%d", c.DataPrefix, c.DataBase+idx)
	userdata := renderVyosUserData(name, mgmtIP, dataIP, c)
	secretName := name + "-cloudinit"

	secretBody, _ := json.Marshal(map[string]any{
		"apiVersion": "v1",
		"kind":       "Secret",
		"metadata": map[string]any{
			"name":      secretName,
			"namespace": a.H.Namespace,
			"labels":    map[string]string{"hhro.io/managed": "true"},
		},
		"data": map[string]string{
			"userdata":    base64.StdEncoding.EncodeToString([]byte(userdata)),
			"networkdata": "",
		},
	})

	pvcName := name + "-disk-0"
	_ = a.H.DeleteSecret(ctx, secretName)
	_ = a.H.DeletePVC(ctx, pvcName)
	if err := a.H.CreateSecret(ctx, secretBody); err != nil {
		return "", fmt.Errorf("create secret: %w", err)
	}
	vmBody := renderVyosVM(name, secretName, c)
	if err := a.H.CreateVM(ctx, vmBody); err != nil {
		return "", fmt.Errorf("create vm: %w", err)
	}
	a.resetCooldown("vyos", envcfg.Dur("VYOS_COOLDOWN", 2*time.Minute))
	// v5.0.26 — SSH post-provisioning. On VyOS, cloud-init's write_files loses
	// the boot-order race against the golden-baked replay unit (it runs first,
	// with stale content), so the kernel-MAC pin (e-switch flooding fix) and
	// the ABF protocol split never applied on fresh VMs — smoke v2/v3 needed
	// manual repair every time. Provision over SSH like workers instead.
	if a.Host != nil {
		go a.postProvisionVyos(name, mgmtIP, dataIP)
	}
	return name, nil
}

// postProvisionVyos pins the kernel eth1 MAC and installs the ABF SCTP->PF
// split on a freshly created VyOS, retrying until both verify (VPP readiness
// and SSH availability gate the early attempts).
func (a *Actuator) postProvisionVyos(name, mgmtIP, dataIP string) {
	lastOct := dataIP[strings.LastIndex(dataIP, ".")+1:]
	n, err := strconv.Atoi(lastOct)
	if err != nil {
		return
	}
	mac := fmt.Sprintf("02:00:00:0a:0a:%02x", n&0xff)
	addr := mgmtIP + ":22"
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Minute)
	defer cancel()
	// ABF v2: the policy next-hop is the phantom 10.0.1.99, statically bound
	// to the sender PF MAC and never touched by any tool. Anchoring on .100
	// poisoned the adjacency the moment measurement mode repointed the .100
	// neighbor to TRex — blackholing ALL NGAP DL and API replies riding this
	// VyOS (trace run#3's 2-minute UE deaths). The acl additionally returns
	// TCP/ICMP bound for the dev box (.100) to the PF (eupf API replies,
	// diagnostics) while UDP (GTP-U DL) stays on the measurement neighbors.
	cmd := fmt.Sprintf(`sudo /usr/sbin/ip link set dev eth1 address %s 2>/dev/null; sudo vppctl set ip neighbor eth1 10.0.1.99 50:7c:6f:14:e4:b2 static >/dev/null 2>&1; A=$(sudo vppctl show acl-plugin acl 2>/dev/null | grep ngap-api-pf-v2 | tail -1 | cut -d" " -f2); if [ -z "$A" ]; then sudo vppctl set acl-plugin acl permit proto 132 dst 10.0.1.96/27, permit proto 132 dst 10.0.1.128/28, permit proto 6 dst 10.0.1.100/32, permit proto 1 dst 10.0.1.100/32 tag ngap-api-pf-v2 >/dev/null 2>&1; A=$(sudo vppctl show acl-plugin acl 2>/dev/null | grep ngap-api-pf-v2 | tail -1 | cut -d" " -f2); fi; if ! sudo vppctl show abf policy 2>/dev/null | grep -q 10.0.1.99; then sudo vppctl abf attach ip4 del policy 10 eth1 >/dev/null 2>&1; sudo vppctl abf policy del id 10 acl 0 via 10.0.1.100 eth1 >/dev/null 2>&1; sudo vppctl abf policy add id 10 acl $A via 10.0.1.99 eth1 >/dev/null 2>&1; sudo vppctl abf attach ip4 policy 10 eth1 >/dev/null 2>&1; fi; echo MAC=$(cat /sys/class/net/eth1/address) ABF=$(sudo vppctl show abf policy 2>/dev/null | grep -c 10.0.1.99)`, mac)

	// v5.1.0 — optional SecGW provisioning (Phase-2 IPsec campaign): each VyOS
	// terminates one ESP tunnel toward the SEG box (TS 33.210 RAN-Core SecGW
	// role). Per-index SPI so the SEG can address VyOS-n by SA; DL to the
	// traffic source (.200) is routed INTO the tunnel (encrypt), while NGAP/
	// API flows keep riding the ABF split above — control plane stays clear.
	if envcfg.Bool("IPSEC_SECGW", false) {
		segIP := envcfg.Get("IPSEC_SEG_IP", "10.0.1.98")
		segMAC := envcfg.Get("IPSEC_SEG_MAC", "02:00:00:00:0c:03")
		key := envcfg.Get("IPSEC_KEY", "4a506a794f574265564551694d653768")
		spi := envcfg.Int("IPSEC_SPI_BASE", 7000) + (n - 4)
		// SA pair per direction (spi UL=7000+idx / DL=7100+idx): a shared
		// bidirectional SA poisons its own inbound anti-replay window the
		// moment its outbound traffic loops back (same SPI+key = valid ICV)
		// — the peer's real DL then all fails as ESN high-bits mismatch.
		cmd += fmt.Sprintf(`; if ! sudo vppctl show ipsec sa 2>/dev/null | grep -q "spi %d "; then sudo vppctl ipsec sa add 300 spi %d esp %s use-esn use-anti-replay >/dev/null 2>&1; sudo vppctl ipsec sa add 301 spi %d esp %s use-esn use-anti-replay >/dev/null 2>&1; T=$(sudo vppctl create ipip tunnel src %s dst %s); sudo vppctl ipsec tunnel protect $T sa-in 300 sa-out 301 >/dev/null 2>&1; sudo vppctl set int state $T up >/dev/null 2>&1; sudo vppctl set int unnumbered $T use eth1 >/dev/null 2>&1; sudo vppctl set ip neighbor eth1 %s %s static >/dev/null 2>&1; sudo vppctl ip route add 10.0.1.200/32 via $T >/dev/null 2>&1; fi; echo SECGW=$(sudo vppctl show ipsec tunnel 2>/dev/null | grep -c "spi %d")`,
			spi, spi, ipsecSuite(key), spi+100, ipsecSuite(key), dataIP, segIP, segIP, segMAC, spi)

		cmd += `; T2=$(sudo vppctl show ipsec tunnel 2>/dev/null | grep -o "^ipip[0-9]*" | head -1); if [ -n "$T2" ]; then gn=100; while [ $gn -le 144 ]; do if [ $gn -ne 108 ]; then sudo vppctl ip route add 10.0.1.$gn/32 via $T2 >/dev/null 2>&1; fi; gn=$((gn+1)); done; fi; echo GNBRT=$(sudo vppctl show ip fib 10.0.1.144/32 2>/dev/null | grep -c ipip)`

		if envcfg.Bool("SECGW_PROFILE", true) {
			cmd += `; T3=$(sudo vppctl show ipsec tunnel 2>/dev/null | grep -o "^ipip[0-9]*" | head -1); if [ -n "$T3" ]; then sudo vppctl set urpf ip4 rx loose eth1 >/dev/null 2>&1; sudo vppctl set urpf ip4 rx loose $T3 >/dev/null 2>&1; ids() { sudo vppctl show acl-plugin acl | tr -d "\r" | awk -v t="{$1}" "\$NF==t{print \$2}" | head -1; }; R=$(ids secgw-inner); [ -z "$R" ] && sudo vppctl set acl-plugin acl permit+reflect src 0.0.0.0/0 dst 0.0.0.0/0 proto 17 dport 2152-2152 tag secgw-inner >/dev/null 2>&1 && R=$(ids secgw-inner); D=$(ids secgw-deny); [ -z "$D" ] && sudo vppctl set acl-plugin acl deny src 0.0.0.0/0 dst 0.0.0.0/0 tag secgw-deny >/dev/null 2>&1 && D=$(ids secgw-deny); sudo vppctl set acl-plugin interface $T3 input acl $R >/dev/null 2>&1; sudo vppctl set acl-plugin interface $T3 input acl $D >/dev/null 2>&1; sudo vppctl set acl-plugin interface $T3 output acl $D >/dev/null 2>&1; fi; echo PROFILE=$(sudo vppctl show acl-plugin interface 2>/dev/null | grep -c "input acl")`
		}

		cmd += "; echo " + vppExporterB64 + " | base64 -d | sudo tee /usr/local/bin/vpp_vf_metrics.sh >/dev/null && sudo chmod 0755 /usr/local/bin/vpp_vf_metrics.sh; echo " + vppTelegrafB64 + " | base64 -d | sudo tee /etc/telegraf/telegraf.d/vpp.conf >/dev/null; sudo systemctl restart telegraf >/dev/null 2>&1; echo VPPEXP=$(sudo /usr/local/bin/vpp_vf_metrics.sh eth1 2>/dev/null | grep -c rx_out_of_buffer)"

		cmd += "; echo " + base64.StdEncoding.EncodeToString([]byte(vyosGuestIsolate)) + " | base64 -d | sudo tee /usr/local/bin/vyos-guest-isolate.sh >/dev/null && sudo chmod 0755 /usr/local/bin/vyos-guest-isolate.sh; echo " + base64.StdEncoding.EncodeToString([]byte(vyosGuestIsolateUnit)) + " | base64 -d | sudo tee /etc/systemd/system/vyos-guest-isolate.service >/dev/null; echo " + base64.StdEncoding.EncodeToString([]byte(vyosGuestIsolateTimer)) + " | base64 -d | sudo tee /etc/systemd/system/vyos-guest-isolate.timer >/dev/null; sudo systemctl daemon-reload; sudo systemctl enable --now vyos-guest-isolate.timer >/dev/null 2>&1; sudo /usr/local/bin/vyos-guest-isolate.sh; echo GISO=$(systemctl is-active vyos-guest-isolate.timer)"

		// v5.1.1 — SEG-side SA rebuild, BEFORE the VyOS injection loop. A
		// recreated VyOS-n restarts its ESP seq at 0 while the SEG inbound
		// window for that SPI has already advanced — every packet from the new
		// VM would be silently dropped as replay. Only a fresh SA pair on both
		// ends (windows at zero) is clean. Order matters: SEG first, so stray
		// SEG->VyOS packets in the gap find no SA on the VyOS side (harmless
		// drop) instead of advancing a window the SEG reset would then violate.
		// ESN on both ends: 32-bit seq wraps in ~35 min at ~2M pps (GCM IV
		// reuse + replay kill mid-trace); the SEG is pre-provisioned N=5 by
		// seg_up.sh, so a missing tunnel here is a config error, not ours to fix.
		segMgmt := envcfg.Get("IPSEC_SEG_MGMT", "10.0.0.146:22")
		segUser := envcfg.Get("IPSEC_SEG_USER", "user")
		segPass := envcfg.Get("IPSEC_SEG_PASS", "")
		idx := n - 4
		encSA, decSA := 111+idx, 131+idx
		segCmd := fmt.Sprintf(`sudo -S bash -c 'V="vppctl -s /run/vpp/cli-seg.sock"; if $V show ipsec tunnel 2>/dev/null | grep -q "ipip%d "; then $V ipsec tunnel protect del ipip%d >/dev/null 2>&1; $V ipsec sa del %d >/dev/null 2>&1; $V ipsec sa del %d >/dev/null 2>&1; $V ipsec sa add %d spi %d esp %s use-esn use-anti-replay; $V ipsec sa add %d spi %d esp %s use-esn use-anti-replay; $V ipsec tunnel protect ipip%d sa-in %d sa-out %d; $V ipsec sa bind %d %d; $V ipsec sa bind %d %d; echo SEGRESET=OK; else echo SEGRESET=NOTUNNEL; fi'`,
			idx, idx, encSA, decSA, encSA, spi, ipsecSuite(key), decSA, spi+100, ipsecSuite(key), idx, decSA, encSA,
			// v6.0.64 (09-09 r31): with 4 VyOS the old map put idx1-3 enc all on w5 (3.75M pps CBC on one
			// worker) and dec 131/134 both on w1 -> peak SEG rxmiss / spiky p99. New map keeps every worker
			// <=2.5M: enc 0/5/2/3, dec 1/3/2/5 (w4 has no tx queue). Same table in harness _bind_of and seg_up.sh.
			encSA, []int{0, 5, 2, 3}[idx%4],
			decSA, []int{1, 3, 2, 5}[idx%4])
		for i := 0; i < 3; i++ {
			out, err := a.Host.ExecOnAddrAs(ctx, segMgmt, segUser, segPass, segCmd)
			if err == nil && strings.Contains(out, "SEGRESET=OK") {
				slog.Info("secgw: SEG-side SA reset", "vyos", name, "spi", spi)
				break
			}
			slog.Warn("secgw: SEG-side SA reset failed", "vyos", name, "spi", spi, "attempt", i+1, "out", strings.TrimSpace(out), "err", err)
			select {
			case <-time.After(3 * time.Second):
			case <-ctx.Done():
				return
			}
		}
	}
	for {
		cmd += "; sudo touch /run/hhro-vyos-provisioned; echo PROVISIONED"
		out, err := a.Host.ExecOnAddrAs(ctx, addr, "vyos", a.VyosCfg.UserPassword, cmd)
		ok := err == nil && strings.Contains(out, "MAC="+mac) && strings.Contains(out, "ABF=1")
		if ok && envcfg.Bool("IPSEC_SECGW", false) &&
			(strings.Contains(out, "SECGW=0") || !strings.Contains(out, "SECGW=") ||
				strings.Contains(out, "GNBRT=0") || !strings.Contains(out, "GNBRT=") ||
				strings.Contains(out, "VPPEXP=0") || !strings.Contains(out, "VPPEXP=")) {
			ok = false
		}
		if ok {
			return
		}
		select {
		case <-time.After(10 * time.Second):
		case <-ctx.Done():
			return
		}
	}
}

// DeleteVyOS removes a VyOS VM + PVC + cloud-init secret. Also clears any
// orphan UERANSIM /32 route whose nexthop was the about-to-be-deleted VyOS.
func (a *Actuator) DeleteVyOS(ctx context.Context, name string, force bool) error {
	if !force && !a.cooldownExpired("vyos") {
		return fmt.Errorf("vyos cooldown active")
	}
	deadIP := ""
	if a.Host != nil {
		re := regexp.MustCompile(`^` + regexp.QuoteMeta(a.VyosCfg.NamePrefix) + `(\d+)$`)
		if m := re.FindStringSubmatch(name); len(m) == 2 {
			n, _ := strconv.Atoi(m[1])
			deadIP = fmt.Sprintf("%s%d", a.VyosCfg.DataPrefix, a.VyosCfg.DataBase+n)
		}
	}

	if err := a.H.DeleteVM(ctx, name); err != nil {
		return err
	}
	_ = a.H.DeletePVC(ctx, name+"-disk-0")
	_ = a.H.DeleteSecret(ctx, name+"-cloudinit")

	if a.Host != nil && deadIP != "" {
		const baseline = "10.0.1.1"
		cmd := fmt.Sprintf(
			`echo %s | sudo -S sh -c 'for pfx in $(ip route show | grep " via %s " | sed "s/ via .*//"); do ip route replace $pfx via %s dev enp5s0f0np0; done'`,
			a.Host.SudoPassword, deadIP, baseline)
		_, _ = a.Host.ExecOnUeransim(ctx, cmd)
	}
	a.resetCooldown("vyos", envcfg.Dur("VYOS_COOLDOWN", 2*time.Minute))
	return nil
}

// IMPORTANT: vyos_config_commands values MUST use single quotes; double quotes
// trip VyOS 1.5-rolling's cloud-init module and the whole batch rolls back.
//
// NIC-flip note (2026-05-27): operator reports that KubeVirt's auto-assigned
// PCI slot for the SR-IOV hostDevice can flip across reboots, putting the
// mlx5 VF on eth0 (where the VyOS template expects the virtio bridge) → the
// mgmt IP lands on the data NIC and the VM becomes unreachable. A v23
// cloud-init `bootcmd` rename attempt failed (either VyOS' cloud-init plugin
// skipped bootcmd, or the rename ran after networking had already bound IP
// to the wrong iface). The correct fix is to bake a udev rule into the VyOS
// template image (`/etc/udev/rules.d/70-vyos-net-by-driver.rules`):
//
//	SUBSYSTEM=="net", DRIVERS=="virtio_net", NAME="eth0"
//	SUBSYSTEM=="net", DRIVERS=="mlx5_core", NAME="eth1"
//
// Then PCI enumeration order stops mattering — the kernel names by driver.
// vyosUserDataTmpl — cloud-init user-data for each daemon-spawned VyOS VM.
//
// v1.39 (2026-06-03) — embed firewall rules so scale-out VyOS instances are
// born with the same firewall posture as test-vyos. Sender (sender data IPs
// 10.0.1.100..108) ↔ UPF/AMF externalIPs (10.0.1.11..15) is the only
// allowed forward traffic; everything else dropped + logged. mgmt SSH on
// eth0 (input chain) is unaffected.
//
// VyOS rule ranges: 10.0.1.100-10.0.1.140 (sender gNB, 30 UE) ↔ 10.0.1.11-10.0.1.40 (UPF/AMF)
// (UPF/AMF externalIPs). If these change, update the rule 10/20 source/dest.
const vyosUserDataTmpl = `#cloud-config
vyos_config_commands:
  - set system host-name '{{NAME}}'
  - set system login user vyos authentication plaintext-password '{{PASSWORD}}'
  - set system name-server '{{DNS}}'
  - set service ssh port '22'
  - set interfaces ethernet eth0 address '{{MGMT_IP}}/24'
  - set interfaces ethernet eth1 mac '{{DATA_MAC}}'
  - set interfaces ethernet eth1 address '{{DATA_IP}}/24'
  - set interfaces ethernet eth1 mtu '9000'
  - set protocols static route 0.0.0.0/0 next-hop '{{GATEWAY}}'
  - set system sysctl parameter net.ipv4.conf.all.forwarding value '1'
  - set system sysctl parameter net.ipv4.conf.all.rp_filter value '0'
  - set system sysctl parameter net.ipv4.conf.default.rp_filter value '0'
  - set system sysctl parameter net.ipv4.conf.eth1.rp_filter value '0'
  - set system sysctl parameter net.ipv4.conf.all.arp_ignore value '1'
  - set system sysctl parameter net.ipv4.conf.all.arp_announce value '2'
  - set system sysctl parameter net.ipv4.conf.all.send_redirects value '0'
  - set system sysctl parameter net.ipv4.conf.eth1.send_redirects value '0'
  - set firewall ipv4 forward filter default-action 'drop'
  - set firewall ipv4 forward filter rule 5 action 'accept'
  - set firewall ipv4 forward filter rule 5 state 'established'
  - set firewall ipv4 forward filter rule 5 state 'related'
  - set firewall ipv4 forward filter rule 5 description 'allow established/related (reverse path)'
  - set firewall ipv4 forward filter rule 10 action 'accept'
  - set firewall ipv4 forward filter rule 10 source address '10.0.1.100-10.0.1.140'
  - set firewall ipv4 forward filter rule 10 destination address '10.0.1.11-10.0.1.40'
  - set firewall ipv4 forward filter rule 10 description 'sender data plane -> UPF/AMF'
  - set firewall ipv4 forward filter rule 20 action 'accept'
  - set firewall ipv4 forward filter rule 20 source address '10.0.1.11-10.0.1.40'
  - set firewall ipv4 forward filter rule 20 destination address '10.0.1.100-10.0.1.140'
  - set firewall ipv4 forward filter rule 20 description 'UPF DL -> sender'
  - set firewall ipv4 forward filter rule 1000 action 'drop'
  - set firewall ipv4 forward filter rule 1000 description 'default drop (no log)'
  - set service monitoring telegraf prometheus-client
`

// vyosEupfUserDataTmpl — v5.0 eUPF-era VyOS (VPP datapath, 3 vCPU / 1 worker).
//
// The data plane is VPP/DPDK: eth1 is owned by DPDK, so kernel-level firewall
// and eth1 addressing via vyos_config_commands are irrelevant — the VPP config
// files are BAKED at first boot instead:
//   - /etc/vpp/startup.conf  — 1 worker (core 2) + 1 rx queue: the per-instance
//     capacity knob that makes 3 VyOS NECESSARY at the 4.8M bidirectional peak
//     buffers 65536, startup-config points at bootstrap.vpp.
//   - /etc/vpp/bootstrap.vpp — deterministic eth1 MAC pin (clone images share a
//     machine-id → identical guest-generated MACs → VEB funnels all traffic to
//     one VF; VPP ignores the kernel-level `set interfaces ethernet eth1 mac`,
//     only this early-boot VPP command works) + static neighbors for every
//     XDP/no-ARP peer: CP VIPs → worker-0 CP VF, eUPF N3 IPs → their
//     deterministic VF MACs, gNB IPs → sender PF (functional mode; the
//     experiment flips gNBs to the TRex DPDK MAC for measurement runs).
//   - vpp-neigh-replay.service also installs the ABF protocol split: SCTP
//     (proto 132) destined to the gNB ranges is forwarded via 10.0.1.100
//     (-> sender PF MAC) so NGAP replies survive measurement mode, while
//     GTP-U keeps following the per-gNB neighbors (-> TRex VF). This kills
//     the DL-vs-NGAP conflict on the same gNB IP (2026-07-04).
//   - vpp-neigh-replay.service — `set ip neighbor` lines do NOT stick when
//     bootstrap.vpp runs at early boot (eth1 has no IP yet); replay them 45 s
//     after every boot.
const vyosEupfUserDataTmpl = `#cloud-config
vyos_config_commands:
  - set system host-name '{{NAME}}'
  - set system login user vyos authentication plaintext-password '{{PASSWORD}}'
  - set system name-server '{{DNS}}'
  - set service ssh port '22'
  - set interfaces ethernet eth0 address '{{MGMT_IP}}/24'
  - set protocols static route 0.0.0.0/0 next-hop '{{GATEWAY}}'
  - set service monitoring telegraf prometheus-client
write_files:
  - path: /etc/vpp/startup.conf
    permissions: '0644'
    content: |
      unix { nodaemon log /var/log/vpp/vpp.log cli-listen /run/vpp/cli.sock gid vpp startup-config /etc/vpp/bootstrap.vpp }
      api-segment { gid vpp }
      socksvr { default }
      cpu { main-core 0 corelist-workers 1 }
      buffers { buffers-per-numa {{BUFFERS}} }
      memory { main-heap-size 512M }
      dpdk { dev {{VF_PCI}} { name eth1 num-rx-queues 1 num-rx-desc {{RX_DESC}} num-tx-desc 4096 } }
      plugins { plugin default { enable } plugin dpdk_plugin.so { enable } }
  - path: /etc/vpp/bootstrap.vpp
    permissions: '0644'
    content: |
{{BOOTSTRAP_VPP}}
  - path: /etc/systemd/system/vpp-neigh-replay.service
    permissions: '0644'
    content: |
      [Unit]
      Description=Replay VPP static neighbors (bootstrap.vpp neighbors do not stick at early boot)
      After=vpp.service
      [Service]
      # Type=simple + hard timeouts: a v1 oneshot variant of this unit (no
      # timeout, vppctl can block forever on a wedged CLI socket) hung the
      # systemd job queue at boot and took sshd down with it (2026-07-03).
      Type=simple
      TimeoutStartSec=180
      ExecStart=/bin/bash -c 'for i in $(seq 1 60); do timeout 3 /usr/bin/vppctl show version >/dev/null 2>&1 && break; sleep 2; done; for i in $(seq 1 60); do /usr/sbin/ip link set dev eth1 address {{DATA_MAC}} >>/var/log/hhro-replay.log 2>&1; [ "$(cat /sys/class/net/eth1/address)" = "{{DATA_MAC}}" ] && break; sleep 3; done; echo "mac=$(cat /sys/class/net/eth1/address)" >>/var/log/hhro-replay.log; grep "set ip neighbor" /etc/vpp/bootstrap.vpp | while read l; do timeout 3 /usr/bin/vppctl $l || true; done; timeout 3 /usr/bin/vppctl set ip neighbor eth1 10.0.1.99 50:7c:6f:14:e4:b2 static >>/var/log/hhro-replay.log 2>&1; for i in $(seq 1 36); do timeout 3 /usr/bin/vppctl show abf policy 2>/dev/null | grep -q 10.0.1.99 && break; timeout 3 /usr/bin/vppctl set acl-plugin acl permit proto 132 dst 10.0.1.96/27, permit proto 132 dst 10.0.1.128/28, permit proto 6 dst 10.0.1.100/32, permit proto 1 dst 10.0.1.100/32 tag ngap-api-pf-v2 >>/var/log/hhro-replay.log 2>&1; A=$(timeout 3 /usr/bin/vppctl show acl-plugin acl 2>/dev/null | grep ngap-api-pf-v2 | tail -1 | cut -d" " -f2); timeout 3 /usr/bin/vppctl abf attach ip4 del policy 10 eth1 >>/var/log/hhro-replay.log 2>&1; timeout 3 /usr/bin/vppctl abf policy del id 10 acl 0 via 10.0.1.100 eth1 >>/var/log/hhro-replay.log 2>&1; timeout 3 /usr/bin/vppctl abf policy add id 10 acl $$A via 10.0.1.99 eth1 >>/var/log/hhro-replay.log 2>&1; timeout 3 /usr/bin/vppctl abf attach ip4 policy 10 eth1 >>/var/log/hhro-replay.log 2>&1; sleep 5; done; timeout 3 /usr/bin/vppctl show abf policy >>/var/log/hhro-replay.log 2>&1'
      [Install]
      WantedBy=multi-user.target
  - path: /config/scripts/vyos-postconfig-bootup.script
    permissions: '0755'
    content: |
      #!/bin/bash
      # VyOS-native late-boot hook. cloud-init's write_files lands AFTER the
      # golden-baked unit already ran at early boot, so the rendered
      # ExecStart (kernel MAC pin + ABF split) never took effect on fresh
      # VMs (smoke v2/v3). Re-running the unit here — guaranteed after both
      # cloud-init and the VyOS config load — closes that ordering hole.
      systemctl daemon-reload
      systemctl restart vpp-neigh-replay.service
runcmd:
  - [ systemctl, daemon-reload ]
  - [ systemctl, enable, vpp-neigh-replay.service ]
  - [ systemctl, restart, vpp ]
  - [ systemctl, start, vpp-neigh-replay.service ]
`

// renderVyosBootstrapVpp builds the bootstrap.vpp body (data IP + MAC pin +
// static neighbors), indented 6 spaces for the cloud-init write_files block.
func renderVyosBootstrapVpp(dataIP, dataMAC string, c VyosCfg) string {
	var b strings.Builder
	line := func(s string) { b.WriteString("      " + s + "\n") }
	line(fmt.Sprintf("set interface mac address eth1 %s", dataMAC))
	line(fmt.Sprintf("set interface ip address eth1 %s/24", dataIP))
	line("set interface state eth1 up")
	// CP VIPs → worker-0 CP VF (NGAP/PFCP anchor)
	for _, oct := range []int{10, 11, 14} {
		line(fmt.Sprintf("set ip neighbor static eth1 10.0.1.%d %s", oct, c.CpVfMac))
	}
	// eUPF N3 IPs → their deterministic VF MACs (02:00:00:00:0b:<octet-as-hex-digits>)
	for oct := 31; oct <= 38; oct++ {
		line(fmt.Sprintf("set ip neighbor static eth1 10.0.1.%d %s%d", oct, c.EupfMacPrefix, oct))
	}
	// gNB range → sender PF (functional default; measurement mode is flipped by
	// the experiment: gNB → TRex DPDK VF MAC, minus .100 which is ALSO the dev
	// box PF primary IP and must always stay on the PF)
	for oct := 100; oct <= 132; oct++ {
		line(fmt.Sprintf("set ip neighbor static eth1 10.0.1.%d %s", oct, c.SenderPfMac))
	}
	return strings.TrimRight(b.String(), "\n")
}

// vyosDataMAC returns a deterministic, locally-administered, UNIQUE MAC for a
// scaled VyOS's data interface (eth1), derived from its index. The eth1 VF is
// attached via hostDevices and the PF leaves the VF admin MAC at 00:00:00:00:00:00,
// so the guest generates the MAC itself — and because every scaled VyOS is cloned
// from the same disk image (same machine-id), udev's persistent policy derives the
// SAME MAC on every clone. Two VyOS sharing one MAC makes the sender's ARP resolve
// every VyOS data IP to a single VF, funnelling all traffic to one box (the other
// starves) — the real cause of the VyOS CPU imbalance the rebalancer could never
// fix. Pinning a unique MAC in the VyOS config overrides the guest-generated one.
func vyosDataMAC(idx int) string {
	return fmt.Sprintf("02:00:00:00:0a:%02x", idx&0xff)
}

func renderVyosUserData(name, mgmtIP, dataIP string, c VyosCfg) string {
	idx := 0
	if strings.HasPrefix(name, c.NamePrefix) {
		if n, err := strconv.Atoi(strings.TrimPrefix(name, c.NamePrefix)); err == nil {
			idx = n
		}
	}
	dataMAC := vyosDataMAC(idx)
	if c.EupfMode {
		// v5.0: VPP MAC pin uses the LIVE convention 02:00:00:0a:0a:<data-octet>
		// (matches the hand-provisioned vyos-0/1/2 so ARP caches stay stable).
		lastOct := dataIP[strings.LastIndex(dataIP, ".")+1:]
		if n, err := strconv.Atoi(lastOct); err == nil {
			dataMAC = fmt.Sprintf("02:00:00:0a:0a:%02x", n&0xff)
		}
		r := strings.NewReplacer(
			"{{NAME}}", name,
			"{{PASSWORD}}", c.UserPassword,
			"{{DNS}}", c.DNS,
			"{{MGMT_IP}}", mgmtIP,
			"{{GATEWAY}}", c.MgmtGateway,
			"{{BOOTSTRAP_VPP}}", renderVyosBootstrapVpp(dataIP, dataMAC, c),
			"{{VF_PCI}}", c.VfPci,
			"{{RX_DESC}}", envcfg.Get("VYOS_RX_DESC", "4096"),
			"{{BUFFERS}}", envcfg.Get("VYOS_BUFFERS", "32768"),
			"{{DATA_MAC}}", dataMAC,
		)
		return r.Replace(vyosEupfUserDataTmpl)
	}
	r := strings.NewReplacer(
		"{{NAME}}", name,
		"{{PASSWORD}}", c.UserPassword,
		"{{DNS}}", c.DNS,
		"{{MGMT_IP}}", mgmtIP,
		"{{DATA_IP}}", dataIP,
		"{{GATEWAY}}", c.MgmtGateway,
		"{{DATA_MAC}}", dataMAC,
	)
	return r.Replace(vyosUserDataTmpl)
}

func renderVyosVM(name, secretName string, c VyosCfg) []byte {
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
				"hhro.io/role":            "vyos",
			},
		},
		"spec": map[string]any{
			"runStrategy": "Always", // v5.0: delete-vmi must mean RESTART (RerunOnFailure treats a graceful stop as final → VM stays off)
			"template": map[string]any{
				"metadata": map[string]any{
					"labels": map[string]string{
						"harvesterhci.io/vmName": name,
						"hhro.io/managed":        "true",
						"hhro.io/role":           "vyos",
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
								// Pin bridge to PCI 0000:00:02.0 so guest names it eth0;
								// otherwise KubeVirt may give the SR-IOV VF eth0 and mgmt
								// IP lands on the data VLAN → VM unreachable.
								map[string]any{
									"name":       "default",
									"model":      "virtio",
									"bridge":     map[string]any{},
									"pciAddress": "0000:00:02.0",
								},
							},
							"hostDevices": []any{
								map[string]any{"deviceName": c.VFResourceName, "name": vfDisplayName(name)},
							},
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
							"secretRef": map[string]string{"name": secretName},
						}},
					},
				},
			},
		},
	}
	b, _ := json.Marshal(vm)
	return b
}

//
//go:embed assets/vyos-guest-isolate.sh
var vyosGuestIsolate string

const vyosGuestIsolateUnit = `[Unit]
Description=VyOS guest: keep vCPU1 exclusive to the VPP worker
[Service]
Type=oneshot
ExecStart=/usr/local/bin/vyos-guest-isolate.sh
`
const vyosGuestIsolateTimer = `[Unit]
Description=Re-assert VPP worker vCPU exclusivity every 60s
[Timer]
OnBootSec=30
OnUnitActiveSec=60
AccuracySec=5
[Install]
WantedBy=timers.target
`

// vppExporterB64 / vppTelegrafB64 — base64 of experiment/p2/vpp_vf_metrics.sh
// and experiment/p2/telegraf_vpp.conf. Embedded (not read from disk) because
// the daemon ships as a distroless image with no repo alongside it. Keep the
// readable copies in the repo in sync when editing either.
const vppExporterB64 = `IyEvYmluL2Jhc2gKIyB2cHBfdmZfbWV0cmljcy5zaCB2MiDigJQg5oqKIFZQUCDlsI0gVkYg55qE6KiI5pW45Zmo6aS157WmIHRlbGVncmFmKGluZmx1eCBsaW5lIHByb3RvY29sKeOAggojCiMg54K65LuA6bq86ZyA6KaBOlZ5T1Mg55qE6LOH5paZ6Z2i5pivIFZQUCArIG1seDUgUE1EKERldlgpLGd1ZXN0IOeahCBrZXJuZWwgbmV0ZGV2IGV0aDEg5piv56m65q68CiMgKDA4LTI5IOWvpua4rCBrZXJuZWwgZXRodG9vbCDmgYYgMCxWUFAg6Ieq5bexIHJ4X291dF9vZl9idWZmZXI9My4zNmU5KeOAguWUr+S4gOecn+a6kD1WUFDjgIIKIwojIOKYhXYyKDA5LTAzKTrmlLnotbAgc3RhdHMgc2VnbWVudCh2cHBfZ2V0X3N0YXRzLOWFseS6q+iomOaGtumrlCwqKueEoSB3b3JrZXIgYmFycmllcioqKeOAggojIHYxIOeUqCBgdnBwY3RsIHNob3cgaGFyZHdhcmUtaW50ZXJmYWNlc2Ag6K6AIHhzdGF0cyzmr4/lkbzlj6vkuIDmrKEgUE1EIOWBnOi9iSDihpIg5a+m5ris5q+P5qyh5LifCiMgfjQuNmsg5YyFKDFIeiDovKroqaIgNjBzOnZ5b3MtMiBtaXNzIDI3IOiQrCB2cyA0IOiQrCk7dGVsZWdyYWYg5q+PIDE1cyDkuIDmrKE95q+P5YiG6ZCY55m95LifCiMgfjE4ay/lj7A96YeP5ris5Zmo6Ieq5bex6KO96YCgIGxvc3PjgIJgc2hvdyBpbnRlcmZhY2VgIOeEoeatpOaViOaHiShBL0Ig5a+m6K2JKeOAggojIC9pZi9yeC1taXNzID0gbWx4NSBpbWlzc2VkID0gcnhfb3V0X29mX2J1ZmZlciDlkIznvqk75qyE5L2N5ZCN5L+d55WZ55u45a6544CCCnNldCAtdQpJRj0kezE6LWV0aDF9ClNPQ0s9L3J1bi92cHAvc3RhdHMuc29jawojIOS7i+mdoue0ouW8lTpzaG93IGludGVyZmFjZSDnhKEgYmFycmllcihBL0Ig5a+m6K2JKSzlj6rlnKjmraTlj5YgaWR4CklEWD0kKHZwcGN0bCBzaG93IGludGVyZmFjZSAiJElGIiAyPi9kZXYvbnVsbCB8IGF3ayAtdiBuPSIkSUYiICckMT09bntwcmludCAkMjsgZXhpdH0nKQpbIC16ICIke0lEWDotfSIgXSAmJiBleGl0IDAgICAgICAgICMgVlBQIOaykui1t+S+hi/ku4vpnaLkuI3lnKg96Z2c6buY6Lez6YGOLOS4jeimgemktemrkuWAvApEPSQodnBwX2dldF9zdGF0cyAtcyAkU09DSyBkdW1wICJeL2lmL3J4JCIgIl4vaWYvdHgkIiAiXi9pZi9yeC1taXNzJCIgIl4vaWYvZHJvcHMkIiAyPi9kZXYvbnVsbCB8IGdyZXAgIl5cWyRJRFggQCIpCnN1bWMoKXsgZWNobyAiJEQiIHwgZ3JlcCAiICQxXCQiIHwgZ3JlcCAtb0UgJ1xdOiBbMC05XSsnIHwgYXdrICd7cys9JDJ9IEVORHtwcmludCBzKzB9JzsgfQpyeD0kKHN1bWMgL2lmL3J4KTsgdHg9JChzdW1jIC9pZi90eCk7IG1zPSQoc3VtYyAvaWYvcngtbWlzcyk7IGRyPSQoc3VtYyAvaWYvZHJvcHMpClsgLXogIiR7cng6LX0iIF0gJiYgZXhpdCAwCmVjaG8gInZwcF9pZmFjZSxpbnRlcmZhY2U9JElGIHJ4X3BhY2tldHM9JHtyeDotMH1pLHR4X3BhY2tldHM9JHt0eDotMH1pLGRyb3BzPSR7ZHI6LTB9aSxyeF9vdXRfb2ZfYnVmZmVyPSR7bXM6LTB9aSxyeF9taXNzZWRfZXJyb3JzPTBpIgo=`

const vppTelegrafB64 = `IyAwOC0yOTpWUFAg6KiI5pW45ZmoIOKGkiB0ZWxlZ3JhZiDihpIgOjkyNzMg4oaSIFByb21ldGhldXMoam9iPXZ5b3Mp44CCCiMgL2V0Yy90ZWxlZ3JhZi90ZWxlZ3JhZi5kIOaYryBzeXN0ZW1kIG92ZXJyaWRlIOeahCAtLWNvbmZpZy1kaXJlY3RvcnksCiMgVnlPUyDph43mlrDnlKLnlJ8gL3J1bi90ZWxlZ3JhZi90ZWxlZ3JhZi5jb25mIOaZguS4jeacg+WLlemAmeijoT1jb21taXQg5a6J5YWo44CCCltbaW5wdXRzLmV4ZWNdXQogIGNvbW1hbmRzID0gWyIvdXNyL2xvY2FsL2Jpbi92cHBfdmZfbWV0cmljcy5zaCBldGgxIl0KICB0aW1lb3V0ID0gIjVzIgogIGludGVydmFsID0gIjE1cyIKICBkYXRhX2Zvcm1hdCA9ICJpbmZsdXgiCg==`

func ipsecSuite(key string) string {
	switch envcfg.Get("IPSEC_SUITE", "cbc-sha256") {
	case "gcm128":
		return "crypto-alg aes-gcm-128 crypto-key " + key
	case "cbc256-sha384":
		ikey := envcfg.Get("IPSEC_INTEG_KEY", "0011223344556677889900aabbccddeeff00112233445566778899aabbccddeeff")
		return "crypto-alg aes-cbc-256 crypto-key " + key + key + " integ-alg sha-384-192 integ-key " + ikey + ikey[:32]
	default:
		ikey := envcfg.Get("IPSEC_INTEG_KEY", "0011223344556677889900aabbccddeeff00112233445566778899aabbccddeeff")
		return "crypto-alg aes-cbc-128 crypto-key " + key + " integ-alg sha-256-128 integ-key " + ikey
	}
}
