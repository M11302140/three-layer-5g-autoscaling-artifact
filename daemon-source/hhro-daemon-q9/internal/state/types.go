// Package state holds the canonical State_t / Scores_t structs from goal.md
// §1-§2 plus the cost-function `Compute` and the two cross-cutting gates
// (Freeze / SteadyGate) shared between Decisioner and Rebalancer. Defined here
// (and not in decide/) because everyone — collect, decide, rebalance, the HTTP
// /state handler — produces or reads them.
package state

import "time"

type WorkerState struct {
	N        int     `json:"n_w"`
	Ready    int     `json:"ready_w"`
	Cpu      float64 `json:"cpu_w"`
	Mem      float64 `json:"mem_w"`
	AllocCpu   float64 `json:"alloc_cpu_m"`
	AllocMem   float64 `json:"alloc_mem_b"`
	MaxFreeCpu float64 `json:"max_free_cpu_m"` // free CPU on the emptiest worker (millicores)
	VMCount    int     `json:"vm_count"`       // Harvester worker VMs incl. booting/not-yet-joined
	IdleWorker string  `json:"idle_worker"`    // Ready >10min scaled worker with zero UPF pods ("" = none)
}

type VyosState struct {
	Exist bool    `json:"exist_v"`
	Count int     `json:"count_v"`
	Cpu   float64 `json:"cpu_v"`
	Mem   float64 `json:"mem_v"`
	Bw    float64 `json:"bw_v"`
}

type GroupState struct {
	Rep   int     `json:"rep"`
	Ready int     `json:"ready"`
	Cpu   float64 `json:"cpu"`
	Mem   float64 `json:"mem"`
}

type UpGroupState struct {
	GroupState
	Bw   float64 `json:"bw_up"`
	Drop float64 `json:"drop_up"`
	// UPF pods stuck Pending (unschedulable). Drives BN_INFRA + blocks
	// further UPF scale-out + makes CREATE_WORKER feasible at RepUP==MaxUP.
	PendingPods int `json:"pending_pods"`
}

type DbGroupState struct {
	GroupState
	Lat float64 `json:"lat_db_us"`
}

type QoSState struct {
	Thr          float64 `json:"thr_t"`
	Drop         float64 `json:"drop_t"`
	ReadyRatioCp float64 `json:"ready_ratio_cp"`
	ReadyRatioUp float64 `json:"ready_ratio_up"`
	// UeCount: attached UEs on the UERANSIM host (0 when probe is unavailable;
	// Decisioner treats ue-driven triggers as inactive in that case).
	UeCount int `json:"ue_count"`
}

type State struct {
	Time time.Time    `json:"t"`
	W    WorkerState  `json:"W"`
	V    VyosState    `json:"V"`
	Cp   GroupState   `json:"G_cp"`
	Up   UpGroupState `json:"G_up"`
	Db   DbGroupState `json:"G_db"`
	Q    QoSState     `json:"Q"`
}

type Scores struct {
	Cp    float64 `json:"C_cp"`
	Up    float64 `json:"C_up"`
	Infra float64 `json:"C_infra"`
	J     float64 `json:"J"`
}
