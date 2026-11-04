// Package actuate owns the side-effecting operations against Harvester
// (worker / VyOS VMs) and the master cluster (Open5GS deployments + UPF clone
// flow). Configuration structs live here so they can be defaulted via env at
// startup and consumed by Decisioner without an import cycle through main.
package actuate

import "github.com/anon/hhro-daemon/internal/envcfg"

// WorkerCfg holds the deployment knobs for create_worker_vm.
type WorkerCfg struct {
	NamePrefix     string
	MgmtCIDR       string
	MgmtBase       int
	MgmtPrefix     string
	MgmtGateway    string
	DataCIDR       string
	DataBase       int
	DataPrefix     string
	DNS1, DNS2     string
	ImageRef       string
	StorageClass   string
	NetworkName    string
	VFResourceName string
	CPUCores       int
	MemoryGi       int
	DiskGi         int
	VFCount        int // v5.0: SR-IOV VFs per worker (eUPF era: 2, one per slot)
}

func DefaultWorkerCfg() WorkerCfg {
	return WorkerCfg{
		NamePrefix:     envcfg.Get("WORKER_NAME_PREFIX", "worker-"),
		MgmtPrefix:     envcfg.Get("WORKER_MGMT_PREFIX", "10.0.0."),
		MgmtBase:       envcfg.Int("WORKER_MGMT_BASE", 52),
		MgmtGateway:    envcfg.Get("WORKER_MGMT_GATEWAY", "10.0.0.1"),
		DataPrefix:     envcfg.Get("WORKER_DATA_PREFIX", "10.0.1."),
		DataBase:       envcfg.Int("WORKER_DATA_BASE", 14),
		DNS1:           envcfg.Get("WORKER_DNS1", "10.0.0.1"),
		DNS2:           envcfg.Get("WORKER_DNS2", "8.8.8.8"),
		ImageRef:       envcfg.Get("WORKER_IMAGE_REF", "default/image-j29n2"),
		StorageClass:   envcfg.Get("WORKER_STORAGECLASS", "longhorn-image-j29n2"),
		NetworkName:    envcfg.Get("WORKER_NETWORK", "default/anon-valn-1"),
		VFResourceName: envcfg.Get("WORKER_VF_RESOURCE", "mellanox.com/MT27800_FAMILY_CONNECTX5_VIRTUAL_FUNCTION"),
		CPUCores:       envcfg.Int("WORKER_CPU_CORES", 4),
		VFCount:        envcfg.Int("WORKER_VF_COUNT", 2),
		MemoryGi:       envcfg.Int("WORKER_MEMORY_GI", 8),
		DiskGi:         envcfg.Int("WORKER_DISK_GI", 50),
	}
}

// GroupCfg holds Open5GS pod deployment names + replica bounds for Phase C.
type GroupCfg struct {
	Namespace    string
	CPDeploy     string
	UPDeploy     string
	DBDeploy     string
	MinCP, MaxCP int
	MinUP, MaxUP int
	MinFreeCpuM  int // millicore floor; scale-out blocked below this and escalates to worker
}

func DefaultGroupCfg() GroupCfg {
	return GroupCfg{
		Namespace:   envcfg.Get("OPEN5GS_NS", "open5gs"),
		CPDeploy:    envcfg.Get("CP_DEPLOY", "open5gs-amf"),
		UPDeploy:    envcfg.Get("UP_DEPLOY", "open5gs-upf"),
		DBDeploy:    envcfg.Get("DB_DEPLOY", "open5gs-mongodb"),
		// Unified with the HBO controller's bounds (same env names) — the old
		// *_REPLICAS variants duplicated MIN/MAX_CP/UP and could silently diverge.
		MinCP:       envcfg.Int("MIN_CP", 1),
		MaxCP:       envcfg.Int("MAX_CP", 6),
		MinUP:       envcfg.Int("MIN_UP", 1),
		MaxUP:       envcfg.Int("MAX_UP", 6),
		MinFreeCpuM: envcfg.Int("MIN_FREE_CPU_M", 500),
	}
}

// VyosCfg holds deployment knobs for deploy_vyos_vm. VyOS VMs are stateless
// L3 forwarders — no k8s join, no networkdata secret, smaller image.
type VyosCfg struct {
	NamePrefix     string
	MgmtPrefix     string
	MgmtBase       int
	MgmtGateway    string
	DataPrefix     string
	DataBase       int
	DNS            string
	UserPassword   string
	ImageRef       string
	StorageClass   string
	NetworkName    string
	VFResourceName string
	CPUCores       int
	MemoryGi       int
	DiskGi         int

	InternalSubnet string // e.g. "10.20.0.0/24" (firewall dest match)
	SenderRange    string // e.g. "10.0.1.100-10.0.1.130" (allowed external source)

	// v5.0 eUPF era: VPP-datapath template (1 worker / 1 rx queue baked via
	// cloud-init write_files + deterministic MAC pin + static neighbors).
	EupfMode      bool
	// SR-IOV VF PCI address inside the daemon-created VyOS VM (deterministic
	// for the current renderVyosVM device layout; measured 0000:09:00.0 —
	// the hand-built VMs' 0000:0e:00.0 came from an older device layout).
	VfPci         string
	CpVfMac       string // worker-0 CP VF (NGAP/PFCP anchor) MAC
	EupfMacPrefix string // eUPF VF MAC prefix; full MAC = prefix + N3 last octet as hex digits
	SenderPfMac   string // dev box PF MAC (functional-mode gNB neighbor target)
}

func DefaultVyosCfg() VyosCfg {
	return VyosCfg{
		NamePrefix:     envcfg.Get("VYOS_NAME_PREFIX", "vyos-"),
		MgmtPrefix:     envcfg.Get("VYOS_MGMT_PREFIX", "10.0.0."),
		MgmtBase:       envcfg.Int("VYOS_MGMT_BASE", 57),  // v4.18: 55→57 — avoid worker mgmt range (.54-.56); scaled vyos → .57/.58
		MgmtGateway:    envcfg.Get("VYOS_MGMT_GATEWAY", "10.0.0.1"),
		DataPrefix:     envcfg.Get("VYOS_DATA_PREFIX", "10.0.1."),
		DataBase:       envcfg.Int("VYOS_DATA_BASE", 4),
		DNS:            envcfg.Get("VYOS_DNS", "8.8.8.8"),
		UserPassword:   envcfg.Get("VYOS_USER_PASSWORD", ""),
		ImageRef:       envcfg.Get("VYOS_IMAGE_REF", "default/image-5r5rv"),
		StorageClass:   envcfg.Get("VYOS_STORAGECLASS", "longhorn-image-5r5rv"),
		NetworkName:    envcfg.Get("VYOS_NETWORK", "default/anon-valn-1"),
		VFResourceName: envcfg.Get("VYOS_VF_RESOURCE", "mellanox.com/MT27800_FAMILY_CONNECTX5_VIRTUAL_FUNCTION"),
		CPUCores:       envcfg.Int("VYOS_CPU_CORES", vyosDefaultCores()),
		MemoryGi:       envcfg.Int("VYOS_MEMORY_GI", 3), // v5.0.14: 2Gi starves the guest with VPP (heap+buffers) — sshd/systemd thrash. NEVER live-patch memory; set at creation only.
		DiskGi:         envcfg.Int("VYOS_DISK_GI", 20),
		EupfMode:       envcfg.Get("EUPF_ENABLED", "true") == "true",
		VfPci:          envcfg.Get("VYOS_VF_PCI", "0000:0e:00.0"),
		CpVfMac:        envcfg.Get("CP_VF_MAC", "02:00:00:00:0b:0a"),
		EupfMacPrefix:  envcfg.Get("EUPF_MAC_PREFIX", "02:00:00:00:0b:"),
		SenderPfMac:    envcfg.Get("SENDER_PF_MAC", "50:7c:6f:14:e4:b2"),
		InternalSubnet: envcfg.Get("INTERNAL_SUBNET", "10.20.0.0/24"),
		SenderRange:    envcfg.Get("VYOS_SENDER_RANGE", "10.0.1.100-10.0.1.130"),
	}
}

// vyosDefaultCores: 3 in the eUPF era (main + 1 VPP worker + OS — the 1-worker
// capacity knob that makes 3 VyOS necessary at the 4.8M peak), 4 legacy.
func vyosDefaultCores() int {
	if envcfg.Get("EUPF_ENABLED", "true") == "true" {
		return 3
	}
	return 4
}

// UpfCfg holds the deployment knobs for deploy_upf (Phase 2e same-DNN pool).
type UpfCfg struct {
	Namespace      string
	SeedRelease    string
	SMFCM          string
	SMFDeploy      string
	DataPrefix     string
	ExternalIPBase int
	WorkerDataIP   string
	SharedDNN      string
	// Cross-worker multi-DNN: each cloned UPF gets DNN "<DnnPrefix><idx>" and
	// UE subnet "<UeSubnetPrefix>.<idx>.0/24" so SMF distributes sessions by DNN
	// and each UPF can run on a different worker. Per-worker externalIP alias is
	// set on the node the pod is scheduled to (WorkerMgmtPrefix + WorkerMgmtBase
	// + N for "worker-N").
	DnnPrefix        string
	UeSubnetPrefix   string // e.g. "10.45" → 10.45.<idx>.0/24
	WorkerMgmtPrefix string
	WorkerMgmtBase   int
	// SMFStaticPool: the SMF cm is pre-populated with all UPF↔DNN mappings, so
	// the actuator must NOT mutate/restart SMF on scale-out/in (avoids repeated
	// SBI-mesh degradation from SMF rollouts during a run).
	SMFStaticPool bool

	// dual-leg NAT (Option 3). When DualLeg, a UPF's GTP-U endpoint (svc
	// externalIP + node L2 anchor alias) moves to the internal VLAN
	// (InternalPrefix+ExternalIPBase+idx on enp15s0.<InternalVLAN>), while the
	// sender-facing VIP (gtpu.advertise + rebalancer route) stays on DataPrefix.
	// VyOS DNATs VIP->internal (ReconcileVyosRuleset). When false, vip==internal
	// and the alias is on plain enp15s0 (v4.22 behaviour).
	DualLeg        bool
	InternalPrefix string
	InternalVLAN   int
	DnIP           string // data-network echo IP (internal VLAN when dual-leg)
}

func DefaultUpfCfg() UpfCfg {
	return UpfCfg{
		Namespace:        envcfg.Get("OPEN5GS_NS", "open5gs"),
		SeedRelease:      envcfg.Get("UPF_SEED_RELEASE", "open5gs-upf-2"),
		SMFCM:            envcfg.Get("SMF_CONFIGMAP", "open5gs-smf"),
		SMFDeploy:        envcfg.Get("SMF_DEPLOYMENT", "open5gs-smf"),
		DataPrefix:       envcfg.Get("VYOS_DATA_PREFIX", "10.0.1."),
		ExternalIPBase:   envcfg.Int("UPF_EXTERNALIP_BASE", 10),
		WorkerDataIP:     envcfg.Get("WORKER_DATA_IP", "10.0.1.11"),
		SharedDNN:        envcfg.Get("UPF_SHARED_DNN", "internet"),
		DnnPrefix:        envcfg.Get("UPF_DNN_PREFIX", "internet"),
		UeSubnetPrefix:   envcfg.Get("UPF_UE_SUBNET_PREFIX", "10.45"),
		WorkerMgmtPrefix: envcfg.Get("WORKER_MGMT_PREFIX", "10.0.0."),
		WorkerMgmtBase:   envcfg.Int("WORKER_MGMT_BASE", 52),
		SMFStaticPool:    envcfg.Bool("SMF_STATIC_POOL", false),
		DualLeg:          envcfg.Get("DUAL_LEG_ENABLED", "false") == "true",
		InternalPrefix:   envcfg.Get("INTERNAL_PREFIX", "10.20.0."),
		InternalVLAN:     envcfg.Int("INTERNAL_VLAN", 20),
		DnIP:             envcfg.Get("DN_IP", ""),
	}
}
