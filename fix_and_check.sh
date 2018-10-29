#!/usr/bin/env bash
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

LOGIT "Fix mtu on legacy hosts"
for host in mail01 sympa ldap01 imap01; do
	echo -e "\tFix mtu on $host"
	ssh root-mmroch@$host sudo ip l set mtu 1400 eth0
done

LOGIT "Restart openvpn services"
for host in openvpn01 openvpn02; do
	ssh $REMOTE_USER@$host sudo mount -a
	if ssh $REMOTE_USER@$host sudo brctl show | grep -q tap; then
		echo -e "\topenvpn service on $host seems to be okay"
	else
		echo -e "\tFix and restart openvpn on $host"
		ssh $REMOTE_USER@$host sudo systemctl restart openvpn@openvpn_udp_1194.service
		ssh $REMOTE_USER@$host sudo brctl show | grep -q tap || ERROR "Failed on $host"
	fi
done

LOGIT "Fix imap01 (restart dovecot and exim4)"
echo -e "\tRestart dovecot"
ssh root-mmroch@imap01 sudo systemctl restart dovecot 
echo -e "\tRestart exim4"
ssh root-mmroch@imap01 sudo systemctl restart exim4

LOGIT "Fix mail01 (restart exim4)"
echo -e "\tRestart exim4"
ssh root-mmroch@mail01 sudo systemctl restart exim4

LOGIT "Fix gitlab (restart gitlab-sidekiq)"
echo -e "\tRestart gitlab-sidekiq"
ssh $REMOTE_USER@mail01 sudo systemctl restart gitlab-sidekiq

LOGIT "Reset malicious failed state on legacy vms"
for host in mail01 sympa ldap01 imap01; do
	echo -e "\tReset failed state on $host"
	ssh root-mmroch@$host sudo systemctl reset-failed systemd-modules-load.service
done

LOGIT "Check and restart confluence if required"
for sec in {0..120}; do
	echo -n -e "\e[1;33m\rWait $sec/120 seconds for confluence to startup.\e[0m"
	curl -m 1 https://wiki.stuvus.uni-stuttgart.de/ 2>/dev/null | grep 'Übersicht - stuvus Wiki' >/dev/null && # -q is not used here since curl and grep seem to have problems with buffer
		break
	sleep 1
done
if curl -m 1 https://wiki.stuvus.uni-stuttgart.de/ 2>/dev/null | grep 'Übersicht - stuvus Wiki' >/dev/null; then
	echo -e "\r        Confluence has started successfully               "
else
	echo -e "\r        Restart confluence                                ";
	ssh $REMOTE_USER@wiki01 sudo systemctl restart confluence.service;
	for sec in {0..120}; do
		echo -n -e "\e[1;33m\rWait $sec/120 seconds for confluence to startup.\e[0m"
		if curl -m 1 https://wiki.stuvus.uni-stuttgart.de/ 2>/dev/null | grep 'Übersicht - stuvus Wiki' >/dev/null; then
			echo -e "\r        Confluence has started successfully                   "
			break
		fi
		sleep 1
	done
	if curl -m 1 https://wiki.stuvus.uni-stuttgart.de/ 2>/dev/null | grep 'Übersicht - stuvus Wiki' >/dev/null; then
		echo -e "\r        Confluence has started successfully              "
		break
	fi
	ERROR "\rConfluence has failed to startup, manual fix required"
fi

LOGIT "Check for failed services"
for ip in `ssh $REMOTE_USER@hypervisor01 grep 'ip=' /etc/xen/vms/\*.cfg | sed 's/.*ip\=\([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*\).*/\1/g' | sort | uniq`; do
	echo -ne "\tcheck ›$ip‹                                               \r"
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
		echo -e -n "\r\e[32m\tno failed units on ›\e[0m$ip\e[32m‹\e[0m ($host_name)\r"
		continue
	fi
	host_name=`ssh $use_user@$ip hostname`
	echo -e "\r\e[1;31m\tfailed units on ›\e[0m$ip\e[1;31m‹\e[0m ($host_name)"
	ssh $use_user@$ip sudo systemctl --failed
	#ssh -t $use_user@$ip
	echo ""
done

LOGIT "Check finanz vm"
for sec in {0..120}; do
	echo -n -e "\e[1;33m\rWait $sec/120 seconds for open RDP port.\e[0m"
	if nmap -p 3389 129.69.139.57 | grep -q filtered; then
		sleep 1
	else
		echo -e "\r        RDP port on finanzen vm seems to be up."
		break
	fi
done
xfreerdp /u:$REMOTE_USER /d:samba.faveve.uni-stuttgart.de /v:129.69.139.57 || ERROR "Failed to connect to finanzen via RDP!"

echo -e "\e[1;31m\n\n\tPlease keep in mind to check Jira manually\n\n"
