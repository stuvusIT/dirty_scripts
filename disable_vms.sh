#!/usr/bin/env bash
BASE_DIR="$( dirname "$( realpath -s "${BASH_SOURCE[0]}" )" )/"
cd $BASE_DIR

[[ "$HOSTNAME" = *hypervisor* ]] || {
	echo -n execute on remote hypervisor;
	source config.inc.sh
	echo " $HYPERVISOR_IP"
	scp $0 $REMOTE_USER@$HYPERVISOR_IP:/tmp/disable_vms.sh
	tput smcup
	ssh -t $REMOTE_USER@$HYPERVISOR_IP bash /tmp/disable_vms.sh
	tput rmcup
	exit $?
}

cd /etc/xen/vms/

function vm_list() {
	for vm in *; do
		vm_name="${vm//.cfg}"
		vm_desc="$(head -n 5 $vm | tail -n 1 | sed 's/^# //g')"
		grep -q "$vm_name" /etc/xen/disabled_vms.txt && vm_stat="on" || vm_stat="off"
		echo "\"$vm_name\" \"$vm_desc\" \"$vm_stat\""
	done
}
LINES=$(tput lines)
COLUMNS=$(tput cols)
a=$(echo -n dialog --title '"Disabled VMs"' --checklist '"Please select all VMs, that should be disabled"' $((LINES-10)) $((COLUMNS-10)) $((LINES-15)) " " ; vm_list | tr '\n' ' ')
eval $a 2>/tmp/disabled_vms.txt && {
	cat /tmp/disabled_vms.txt | tr ' ' '\n' | sudo tee /etc/xen/disabled_vms.txt
}
