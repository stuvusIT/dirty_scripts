#!/bin/bash
BASE_DIR="$( dirname "$( realpath -s "${BASH_SOURCE[0]}" )" )/"
cd $BASE_DIR

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

source config.inc.sh

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
	echo -n -e "\e[1;33m\rWait $sec/60 seconds for stuvus.de\e[0m\n"
	curl -m 10 -i https://stuvus.uni-stuttgart.de 2>/dev/null | head -n 1 | grep -q '200' && break
done

LOGIT "Fix mtu on legacy hosts"
for host in mail01 sympa ldap01 imap01; do
	echo -e "\tFix mtu on $host"
	ssh root-mmroch@$host sudo ip l set mtu 1400 eth0
done

LOGIT "Restart openvpn services"
for host in openvpn01 openvpn02; do
	echo -e "\tRestart and fix openvpn on $host"
	ssh $REMOTE_USER@$host sudo systemctl restart openvpn@openvpn_udp_1194.service
	ssh $REMOTE_USER@$host sudo brctl show | grep -q tap || ERROR "Failed on $host"
done

LOGIT "Fix imap01 (restart dovecot and exim4)"
echo -e "\trestart dovecot"
ssh root-mmroch@imap01 sudo systemctl restart dovecot 
echo -e "\trestart exim4"
ssh root-mmroch@imap01 sudo systemctl restart exim4

LOGIT "Fix mail01 (restart exim4)"
echo -e "\trestart exim4"
ssh root-mmroch@mail01 sudo systemctl restart exim4

LOGIT "Reset malicious failed state on legacy vms"
for host in mail01 sympa ldap01 imap01; do
	echo -e "\tReset failed state on $host"
	ssh root-mmroch@$host sudo systemctl reset-failed systemd-modules-load.service
done

LOGIT "Check finanz vm"
for sec in {0..60}; do
	echo -n -e "\e[1;33m\rWait $sec/60 seconds for open RDP port.\e[0m\n"
	if nmap -p 3389 129.69.139.57 | grep -q filtered; then
		sleep 1
	else
		break
	fi
done
xfreerdp /u:$REMOTE_USER /d:samba.faveve.uni-stuttgart.de /v:129.69.139.57 || ERROR "Failed to connect to finanzen via RDP!"

LOGIT "Check for failed services"
for ip in `ssh $REMOTE_USER@hypervisor01 grep 'ip=' /etc/xen/vms/\*.cfg | sed 's/.*ip\=\([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*\).*/\1/g' | sort | uniq`; do
	echo -ne "\tcheck ›$ip‹ "
	if ! ping -c 1 -W 1 $ip >/dev/null; then
		echo -e "\r\e[33m\tskip ip ›\e[0m$ip\e[33m‹ (can't ping)\e[0m"
		continue
	fi
	use_user="$REMOTE_USER"
	[[ " 129.69.139.50 129.69.139.70 129.69.139.72 129.69.139.71 " =~ .*\ $ip\ .* ]] && use_user="root-mmroch"
	if nmap -p 22 $ip | grep -q filtered; then
		echo -e "\r\e[33m\tskip ip ›\e[0m$ip\e[33m‹ (ssh is closed)\e[0m"
		continue
	fi
	if ssh $use_user@$ip sudo systemctl --failed | grep -q "0 loaded units listed."; then
		host_name=`ssh $use_user@$ip hostname`
		echo -e "\r\e[32m\tno failed units on ›\e[0m$ip\e[32m‹\e[0m ($host_name)"
		continue
	fi
	echo -e "\r\e[1;31m\tfailed units on ›\e[0m$ip\e[1;31m‹\e[0m"
	ssh $use_user@$ip sudo systemctl --failed
	ssh $use_user@$ip
done

echo -e "\e[1;31m\n\n\tPlease keep in mind to check Jira manually\n\n"
