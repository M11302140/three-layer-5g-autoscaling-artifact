# Redactions applied to this copy

Every text file in this record was copied from the lab tree and then passed through one redaction script. The originals were not modified. The six frozen simulator files were excluded from every rewrite (their md5 must match `FROZEN_MD5`).

| original | placeholder | where it appears |
|---|---|---|
| management network 192.168.0.N | 10.0.0.N | scripts, manifests, logs, reports |
| data network 10.10.10.N | 10.0.1.N | scripts, manifests, logs, reports, per-run CSV columns that carry node or slot addresses |
| testbed user name and home directory | `user`, `/home/user` | scripts, logs |
| sudo and ssh passwords piped on the command line | `$SUDO_PASS`, `$SSH_PASS`, `$VYOS_PASS` (environment variables the operator must set) | shell and Python harness scripts |
| password defaults compiled into the controller | empty string (the environment variables `HOST_SSH_PASSWORD`, `HOST_PASS`, `IPSEC_SEG_PASS`, `VYOS_USER_PASSWORD` must be set) | `daemon-source/*/` |
| password values in manifests and logged manifests | `<REDACTED>` | `deploy/*.yaml`, `raw-runs/chain_*.log` |
| Go module path `github.com/<user>/hhro-daemon` | `github.com/anon/hhro-daemon` | `go.mod` and imports |
| Multus network and VM names carrying the user name | `anon-valn-1`, `anon-master-…` | manifests, logs |
| author e-mail | `author@example.org` | — |

Cluster-internal addresses that are Kubernetes defaults (10.42/16, 10.43/16 service range, 10.45/16 UE pool, ClusterIP values) were left unchanged; they identify nothing outside the testbed.

Comments written in Chinese were removed from `.py`, `.sh`, `.go` and `.yaml` files (whole comment lines, trailing comments and Chinese docstrings, the latter replaced by `"""(docstring removed)"""`). All Python files compile (`py_compile`), all shell scripts pass `bash -n`, and every change to a Go file was verified line by line to be either a comment removal or one of the substitutions above. Comments in English were kept.

Scan used before upload: `grep -rniE "password|token|secret|BEGIN (RSA|OPENSSH)|kubeconfig|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}"`; the remaining hits are identifier names (`HOST_SSH_PASSWORD`), Kubernetes secret mount paths, prose, and the placeholder addresses.
