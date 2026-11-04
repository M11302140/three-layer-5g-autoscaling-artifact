#!/bin/bash
set -e
cat > /etc/systemd/system/pedpoll.slice <<'EOF'
[Unit]
Description=pedestrian-data poller slice (core 15 only; review round 33 explicit exception)
[Slice]
AllowedCPUs=15
EOF
cat > /etc/systemd/system/ped-poll.service <<'EOF'
[Unit]
Description=Fetch City of Melbourne per-minute pedestrian counts (rolling ~18 h snapshot)
[Service]
Type=oneshot
Slice=pedpoll.slice
Nice=19
User=user
ExecStart=/home/user/experiment/qsim/ped_poll.sh /home/user/experiment/qsim/ped2026
EOF
cat > /etc/systemd/system/ped-poll.timer <<'EOF'
[Unit]
Description=Run ped-poll every 6 hours
[Timer]
OnCalendar=*-*-* 00,06,12,18:05:00
Persistent=true
Unit=ped-poll.service
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now ped-poll.timer
# remove the crontab fallback (installed 10-11 16:4x on core 13)
su - user -c 'crontab -l 2>/dev/null | grep -v ped_poll | crontab -' || true
systemctl start ped-poll.service && sleep 2 && tail -n 2 /home/user/experiment/qsim/ped2026/poll.log
echo "cpuset of slice: $(cat /sys/fs/cgroup/pedpoll.slice/cpuset.cpus.effective 2>/dev/null)"
systemctl list-timers --no-pager | grep -i ped
