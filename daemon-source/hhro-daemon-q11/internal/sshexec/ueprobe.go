package sshexec

import (
	"context"
	"fmt"
	"regexp"
)

// UeProbe counts attached UEs on the UERANSIM host via `nr-cli --dump`. One
// SSH round-trip per call; errors are swallowed by callers so a flaky
// UERANSIM falls back to cpu-only signal.
type UeProbe struct {
	Host  *HostExec
	NrCli string
	re    *regexp.Regexp
}

func NewUeProbe(host *HostExec, nrcli string) *UeProbe {
	if nrcli == "" {
		nrcli = "/home/user/UERANSIM/build/nr-cli"
	}
	return &UeProbe{Host: host, NrCli: nrcli, re: regexp.MustCompile(`(?m)^\s*imsi-\d+\s*$`)}
}

func (u *UeProbe) Count(ctx context.Context) (int, error) {
	if u == nil || u.Host == nil {
		return 0, nil
	}
	cmd := fmt.Sprintf("echo %s | sudo -S %s --dump", u.Host.SudoPassword, u.NrCli)
	out, err := u.Host.ExecOnUeransim(ctx, cmd)
	if err != nil {
		return 0, err
	}
	return len(u.re.FindAllString(out, -1)), nil
}
