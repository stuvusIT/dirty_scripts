#!/bin/bash
for pid in `sudo lsof -t /dev/ttyUSB0`; do
	echo $pid
	sudo kill $pid
done
echo -n -e "\e[1;33mPlease enter the hypervisor luks password: \e[0m"
expect -f /tmp/reboot_hypervisor.expect
