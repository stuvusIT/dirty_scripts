#!/bin/bash
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

HR
LOGIT "Stop all vms on hypervisor01 - execute »safe_restart_vms.sh« on hypervisor01\nPress return to continue"; read
scp safe_restart_vms.sh $REMOTE_USER@$HYPERVISOR_IP:/tmp/safe_restart_vms.sh
ssh -t $REMOTE_USER@$HYPERVISOR_IP bash /tmp/safe_restart_vms.sh stop
HR

LOGIT "Reboot and wait for server to come back online (Press Ctrl+a followed by 'k' after you see the login screen)\nPress return to continue"; read
ssh $REMOTE_USER@$HYPERVISOR_IP "sudo shutdown -r &"
ssh -t $REMOTE_USER@129.69.139.1 sudo screen /dev/ttyUSB0 115200

HR
LOGIT "Re(start) all vms on hypervisor01 - execute »safe_restart_vms.sh« on hypervisor01\nPress return to continue"; read
scp safe_restart_vms.sh $REMOTE_USER@$HYPERVISOR_IP:/tmp/safe_restart_vms.sh
ssh -t $REMOTE_USER@$HYPERVISOR_IP bash /tmp/safe_restart_vms.sh
HR

for sec in {0..60}; do
	echo -n -e "\e[1;33m\rWait $(($sec*5))/300 seconds for stuvus.de\e[0m\n"
	curl -m 5 -i https://stuvus.uni-stuttgart.de 2>/dev/null | head -n 1 | grep -q '200' && break
done

./fix_and_check.sh
