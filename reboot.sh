#!/usr/bin/env bash
set -e
set -u
set -o pipefail

BASE_DIR="$( dirname "$( realpath -s "${BASH_SOURCE[0]}" )" )/"
cd $BASE_DIR
source config.inc.sh

function LOGIT {
	echo -e "\n\e[1;32m$*\e[0m\n"
}
function ERROR {
	echo -e "\e[1;31m$*\e[0m"
	echo "Press return to continue"
	read
}
function HR {
	echo ""
	printf "\e[1;31m%*s\e[0m\n" "${COLUMNS:-$(tput cols)}" "" | tr " " -
	printf "\e[1;31m%*s\e[0m\n" "${COLUMNS:-$(tput cols)}" "" | tr " " -
	echo ""
}
function READ {
	mplayer finn.wav &>/dev/null &
	read
}

HR
if ping -c 1 -W 1 &>/dev/null; then
LOGIT "Stop all vms on hypervisor01 - execute »safe_restart_vms.sh« on hypervisor01"
scp safe_restart_vms.sh $REMOTE_USER@$HYPERVISOR_IP:/tmp/safe_restart_vms.sh
ssh -t $REMOTE_USER@$HYPERVISOR_IP bash /tmp/safe_restart_vms.sh stop
HR
fi

LOGIT "Reboot and wait for server to come back online"
ssh $REMOTE_USER@$HYPERVISOR_IP "sudo shutdown -r &"
scp reboot_hypervisor.sh $REMOTE_USER@129.69.139.1:/tmp/reboot_hypervisor.sh
scp reboot_hypervisor.expect $REMOTE_USER@129.69.139.1:/tmp/reboot_hypervisor.expect
ssh -t $REMOTE_USER@129.69.139.1 bash /tmp/reboot_hypervisor.sh

HR
LOGIT "Re(start) all vms on hypervisor01 - execute »safe_restart_vms.sh« on hypervisor01\nPress return to continue"; READ
scp safe_restart_vms.sh $REMOTE_USER@$HYPERVISOR_IP:/tmp/safe_restart_vms.sh
ssh -t $REMOTE_USER@$HYPERVISOR_IP bash /tmp/safe_restart_vms.sh
HR

for sec in {0..60}; do
	echo -n -e "\e[1;33m\rWait $(($sec*5))/300 seconds for stuvus.de\e[0m\n"
	curl -m 1 -i https://stuvus.uni-stuttgart.de 2>/dev/null | head -n 1 | grep -q '200' && break
	sleep 4
done

./fix_and_check.sh
