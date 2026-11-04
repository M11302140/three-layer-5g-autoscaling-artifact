// Package sshexec runs single commands on bare-metal hosts (UERANSIM,
// worker-0) that aren't k8s nodes. Password auth via env to match the
// testbed's shared user/user account.
package sshexec

import (
	"bytes"
	"context"
	"fmt"
	"net"
	"os"
	"strings"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
	"golang.org/x/crypto/ssh"
)

type HostExec struct {
	UeransimHost     string
	UeransimUser     string
	UeransimPassword string

	WorkerHost     string
	WorkerUser     string
	WorkerPassword string

	// HarvesterHost is the bare-metal hypervisor (not a k8s node). Used by the
	// dual-leg VF-VLAN manager to run `ip link set <pf> vf N ...` on the eSwitch.
	// Login user differs from the shared worker account (rancher@ on Harvester).
	HarvesterHost     string
	HarvesterUser     string
	HarvesterPassword string

	SudoPassword string // root for `sudo -S` on either host

	// sem bounds concurrent SSH sessions. Previously a single global mutex
	// serialized ALL SSH across every host — at scale the per-tick
	// ReconcileAliases (SSH to each worker) + vfvlan + rebalancer monopolized it
	// and starved DeleteUPF/DeleteWorker (cascading dial timeouts → scale-in
	// stuck). A bounded semaphore allows cross-host concurrency (different hosts
	// are independent) while capping total fan-out to avoid a thundering herd.
	sem chan struct{}
}

func NewFromEnv() *HostExec {
	user := envcfg.Get("HOST_SSH_USER", "user")
	pass := envcfg.Get("HOST_SSH_PASSWORD", "")
	return &HostExec{
		UeransimHost:     envcfg.Get("UERANSIM_HOST", "10.0.0.146:22"),
		UeransimUser:     envcfg.Get("UERANSIM_SSH_USER", user),
		UeransimPassword: envcfg.Get("UERANSIM_SSH_PASSWORD", pass),
		WorkerHost:       envcfg.Get("WORKER_HOST", "10.0.0.52:22"),
		WorkerUser:       envcfg.Get("WORKER_SSH_USER", user),
		WorkerPassword:   envcfg.Get("WORKER_SSH_PASSWORD", pass),
		HarvesterHost:     envcfg.Get("HARVESTER_HOST_SSH", "10.0.0.193:22"),
		HarvesterUser:     envcfg.Get("HARVESTER_SSH_USER", "rancher"),
		HarvesterPassword: envcfg.Get("HARVESTER_SSH_PASSWORD", pass),
		SudoPassword:     envcfg.Get("HOST_SUDO_PASSWORD", pass),
		sem:              make(chan struct{}, envcfg.Int("SSH_MAX_CONCURRENT", 8)),
	}
}

func (h *HostExec) runOnHost(ctx context.Context, addr, user, password, cmd string) (string, error) {
	return h.runOnHostSudo(ctx, addr, user, password, h.SudoPassword, cmd)
}

func (h *HostExec) runOnHostSudo(ctx context.Context, addr, user, password, sudoPass, cmd string) (string, error) {
	select {
	case h.sem <- struct{}{}:
		defer func() { <-h.sem }()
	case <-ctx.Done():
		return "", ctx.Err()
	}
	cfg := &ssh.ClientConfig{
		User:            user,
		Auth:            []ssh.AuthMethod{ssh.Password(password)},
		HostKeyCallback: ssh.InsecureIgnoreHostKey(),
		Timeout:         8 * time.Second,
	}
	d := net.Dialer{Timeout: 8 * time.Second}
	conn, err := d.DialContext(ctx, "tcp", addr)
	if err != nil {
		return "", fmt.Errorf("dial %s: %w", addr, err)
	}
	defer conn.Close()
	sshConn, chans, reqs, err := ssh.NewClientConn(conn, addr, cfg)
	if err != nil {
		return "", fmt.Errorf("ssh handshake %s: %w", addr, err)
	}
	client := ssh.NewClient(sshConn, chans, reqs)
	defer client.Close()
	sess, err := client.NewSession()
	if err != nil {
		return "", fmt.Errorf("new session: %w", err)
	}
	defer sess.Close()
	var stdout, stderr bytes.Buffer
	sess.Stdout = &stdout
	sess.Stderr = &stderr
	sess.Stdin = bytes.NewReader([]byte(sudoPass + "\n"))
	if err := sess.Run(cmd); err != nil {
		return stdout.String() + stderr.String(),
			fmt.Errorf("exec %q on %s: %w (stderr=%s)", cmd, addr, err, stderr.String())
	}
	return stdout.String(), nil
}

// ExecOnAddrAs runs cmd on an arbitrary host with explicit credentials
// (used for VyOS post-provisioning — its user/password differ from workers).
func (h *HostExec) ExecOnAddrAs(ctx context.Context, addr, user, password, cmd string) (string, error) {
	return h.runOnHost(ctx, addr, user, password, cmd)
}

func (h *HostExec) ExecOnUeransim(ctx context.Context, cmd string) (string, error) {
	return h.runOnHost(ctx, h.UeransimHost, h.UeransimUser, h.UeransimPassword, cmd)
}

func (h *HostExec) ExecOnWorker(ctx context.Context, cmd string) (string, error) {
	return h.runOnHost(ctx, h.WorkerHost, h.WorkerUser, h.WorkerPassword, cmd)
}

// ExecOnWorkerAddr runs cmd on an arbitrary worker by mgmt address (host:port),
// reusing the worker credentials. Used for per-worker data-plane setup when a
// UPF clone is scheduled on a worker other than worker-0 (cross-worker UPF).
func (h *HostExec) ExecOnWorkerAddr(ctx context.Context, addr, cmd string) (string, error) {
	return h.runOnHost(ctx, addr, h.WorkerUser, h.WorkerPassword, cmd)
}

// RunVyosConfig applies a batch of VyOS `set`/`delete` config commands on a
// VyOS VM (user vyos) over SSH, wrapped in a single configure→commit session via
// the script-template. Used by ReconcileVyosRuleset to push the replicated
// DNAT/firewall table. The whole batch commits atomically — a bad command rolls
// the batch back without touching the running config. Returns combined output.
func (h *HostExec) RunVyosConfig(ctx context.Context, addr, password string, cmds []string) (string, error) {
	var sb strings.Builder
	sb.WriteString("source /opt/vyatta/etc/functions/script-template\n")
	sb.WriteString("configure\n")
	for _, c := range cmds {
		sb.WriteString(c)
		sb.WriteString("\n")
	}
	sb.WriteString("commit\n")
	sb.WriteString("exit\n")
	return h.runVyos(ctx, addr, "vyos", password, sb.String())
}

// runVyos pipes a script to `vbash` on a VyOS VM (no sudo; vyos user already has
// config rights via the operator shell). stdin carries the script, not a sudo pw.
func (h *HostExec) runVyos(ctx context.Context, addr, user, password, script string) (string, error) {
	select {
	case h.sem <- struct{}{}:
		defer func() { <-h.sem }()
	case <-ctx.Done():
		return "", ctx.Err()
	}
	cfg := &ssh.ClientConfig{
		User:            user,
		Auth:            []ssh.AuthMethod{ssh.Password(password)},
		HostKeyCallback: ssh.InsecureIgnoreHostKey(),
		Timeout:         10 * time.Second,
	}
	d := net.Dialer{Timeout: 10 * time.Second}
	conn, err := d.DialContext(ctx, "tcp", addr)
	if err != nil {
		return "", fmt.Errorf("dial %s: %w", addr, err)
	}
	defer conn.Close()
	sshConn, chans, reqs, err := ssh.NewClientConn(conn, addr, cfg)
	if err != nil {
		return "", fmt.Errorf("ssh handshake %s: %w", addr, err)
	}
	client := ssh.NewClient(sshConn, chans, reqs)
	defer client.Close()
	sess, err := client.NewSession()
	if err != nil {
		return "", fmt.Errorf("new session: %w", err)
	}
	defer sess.Close()
	var stdout, stderr bytes.Buffer
	sess.Stdout = &stdout
	sess.Stderr = &stderr
	sess.Stdin = bytes.NewReader([]byte(script))
	if err := sess.Run("vbash"); err != nil {
		return stdout.String() + stderr.String(),
			fmt.Errorf("vyos config on %s: %w (stderr=%s)", addr, err, stderr.String())
	}
	return stdout.String(), nil
}

// ExecOnHarvesterHost runs cmd on the bare-metal hypervisor (rancher@ account).
// `sudo -S` consumes the piped HarvesterPassword as both login is rancher and
// the sudo password is the same shared testbed secret.
func (h *HostExec) ExecOnHarvesterHost(ctx context.Context, cmd string) (string, error) {
	return h.runOnHostSudo(ctx, h.HarvesterHost, h.HarvesterUser, h.HarvesterPassword, h.HarvesterPassword, cmd)
}

func (h *HostExec) SanityCheck() error {
	if h.UeransimPassword == "" || h.WorkerPassword == "" {
		return fmt.Errorf("HOST_SSH_PASSWORD missing")
	}
	return nil
}

func Enabled() bool {
	return os.Getenv("HOST_SSH_PASSWORD") != "" || os.Getenv("UERANSIM_SSH_PASSWORD") != ""
}
