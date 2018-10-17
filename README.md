# Dirty scripts

#### `config.inc.sh`

Your user configuration, set `REMOTE_USER` to your stuvus username.


#### `reboot.sh`

This script is intended to safety reboot our hypervisor.

It requires following tools installed:
 * nmap
 * ping
 * xfreerdp
 * sed
 * scp,ssh
 * curl
 * grep
 * mplayer - to indicate user attention


#### `fix_and_check.sh`

Fix commonly failed hosts and check for failed units and some other stuff.


#### `safe_restart_vms.sh`

The propose of this script is it to *start*, *stop* or *restart* all VMs and iSCSI devices. VMs listed in `/etc/xen/disabled_vms.txt`(one per line) are only stopped and excluded from the start/boot process. You can use `disable_vms.sh` to disable them interactively. This script is also invoked by `reboot.sh`.

##### Arguments

This script can take exactly zero or one argument
 * start - only login into all iSCSI devices and start all enabled VMs
 * stop - stop all running VMs and logout from all iSCSI devices
 * restart - do both `start` and `stop`

If no argument is given `start` is assumed.


#### `disable_vms.sh`

A script which list and modifies disabled VMs. VMs listed in `/etc/xen/disabled_vms.txt`. You can execute this script right inside this repository.


#### `reboot_hypervisor.sh`

Helper script to close all services using the serial port our hypervisor is attached to and to execute `reboot_hypervisor.expect`. This invoked by `reboot.sh`, don't execute it directly.


#### `reboot_hypervisor.expect`

Helper script to enter the luks password. This script is invoked by `reboot_hypervisor.sh` which is used by `reboot.sh` and should never be executed directly by the user.


#### `test_io.sh`

Simple bash script to test IO performance.
