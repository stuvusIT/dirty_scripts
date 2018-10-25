#!/usr/bin/env bash
BASE_DIR="$( dirname "$( realpath -s "${BASH_SOURCE[0]}" )" )/"
cd $BASE_DIR

TERM=ansi
export TERM=ansi

function LOGIT {
	echo -e "\n\e[1;32m$*\e[0m\n"
}

function ERROR {
	echo -e "\e[1;31m$*\e[0m"
	echo "Press return to continue"
	read
}

function show_vms {
	LOGIT "show all running vms"
	sudo xl list
}

function show_failed {
	LOGIT "show all failed units"
	sudo systemctl --failed || ERROR "there are some failed units"
}

function shutdown_vms {
	cd /etc/xen/vms/
	LOGIT "shutdown all running xen_vman managed vms"
	for vm in *; do
		vm="${vm//.cfg}"
		sudo xl shutdown -F $vm 2>&1 | grep -E -v "(invalid domain identifier|Shutting down domain|sending ACPI power button event)" &
	done

	if [ $((`sudo xl list | wc -l`-2)) -gt 0 ]; then
	echo -e "\e[1;31mWait 3minutes for all vms to shutdown gracefully before destroy them via \`xl destroy\`\e[0m\n"
	for sec in {0..180}; do
		rem_vms=$((`sudo xl list | wc -l`-2))
		echo -n -e "\r\tWait $sec/180 seconds ($rem_vms vms are still running, press 'x' to destroy them immediately)   \r"
		read -n 1 -N 1 -t 1 key
		if [ $rem_vms -le 0 -o "$key" = "x" ]; then
			break
		fi
	done
	fi

	if [ $((`sudo xl list | wc -l`-2)) -gt 0 ]; then
	sudo xl list
	LOGIT "destroy all all remaining $((`sudo xl list | wc -l`-2)) vms"
	for vm in *; do
		vm="${vm//.cfg}"
		sudo xl destroy $vm 2>&1 | grep -E -v "(invalid domain identifier|Shutting down domain)" &
	done
	wait
	fi

	LOGIT "reset failed state of all vms"
	for vm in *; do
		vm="${vm//.cfg}"
		sudo systemctl reset-failed vm@$vm 2>&1 | grep -v "Failed to reset failed state" &
	done
	wait
}

function logout_iscsi {
	cd /dev/disk/by-path/
	if [ $(ls ip* 2>/dev/null | wc -l) -gt 0 ]; then
		LOGIT "logout all iscsi devices via systemctl"
		for vm in *; do
			vm="${vm//.cfg}"
			sudo systemctl stop "vm_iscsi@$vm" &
		done
		wait; sleep 5
	fi

	if [ $(ls ip* 2>/dev/null | wc -l) -gt 0 ]; then
		LOGIT "logout from all remaining iscsi devices"
		for disk in `ls ip* 2>/dev/null | grep -v "part[0-9]$" | sed 's/.*\(iqn\..*\)-lun.*/\1/'`; do
			sudo iscsiadm -m node -T $disk --logout -p 129.69.139.18:3260
		done
	fi

	if [ $(ls ip* 2>/dev/null | wc -l) -gt 0 ]; then
		echo -e "\e[1;31mFailed to logout from following iscsi devices:\e[0m"
		ls ip*
		echo "Press return to continue"
		read
	fi
}

function login_iscsi {
	cd /etc/xen/vms/.iscsi/
	LOGIT "login into all iscsi devices"
	for vm in *; do
		sudo systemctl start "vm_iscsi@$vm"
	done
}

function start_vms {
	cd /etc/xen/vms/
	LOGIT "start all enabled vms"
	for vm in *; do
		vm="${vm//.cfg}"
		if grep -q "$vm" /etc/xen/disabled_vms.txt; then
			echo -e "\t\e[33mskip vm  ›\e[0m$vm\e[33m‹\e[0m"
		else
			echo -e "\t\e[32mstart vm ›\e[0m$vm\e[32m‹\e[0m"
			rvm=$((`sudo xl list | wc -l`-2))
			rvm=$((rvm +9))
			echo -ne "\tWait $((rvm /10)).$((rvm %10))sec   \r"
			sudo systemctl start vm@$vm
			for i in $(seq $rvm -1 1); do
				echo -ne "\tWait $((i /10)).$((i %10))sec   \r"
				sleep 0.1
			done
		fi
	done
}

[[ "$HOSTNAME" = *hypervisor* ]] || {
	echo -n execute on remote hypervisor;
	source config.inc.sh
	echo " $HYPERVISOR_IP"
	scp $0 $REMOTE_USER@$HYPERVISOR_IP:/tmp/safe_restart_vms.sh
	ssh -t $REMOTE_USER@$HYPERVISOR_IP /tmp/safe_restart_vms.sh $1
	exit $?
}

show_failed
show_vms

case $1 in
	stop)
		shutdown_vms
		show_failed
		logout_iscsi
		show_vms
		show_failed
		;;
	restart)
		shutdown_vms
		show_failed
		logout_iscsi
		login_iscsi
		show_failed
		start_vms
		show_vms
		show_failed
		;;
	start|*)
		login_iscsi
		show_failed
		start_vms
		show_vms
		show_failed
		;;
esac

