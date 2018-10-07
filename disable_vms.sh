#!/bin/bash
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
a=$(echo -n dialog --title '"Disabled VMs"' --checklist '" "' $((LINES-10)) $((COLUMNS-10)) $((LINES-15)) " " ; vm_list | tr '\n' ' ')
eval $a 2>/tmp/disabled_vms.txt
cat /tmp/disabled_vms.txt | tr ' ' '\n' | sudo tee /etc/xen/disabled_vms.txt
