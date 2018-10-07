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


#### `fix_and_check.sh`

Fix commonly failed hosts and check for failed units and some other stuff.


#### `safe_restart_vms.sh`

A script which restart all vms and iscsi devices at our hypervisor. This script is intended to be executed directly at the hypervisor or is invoked by `reboot.sh` . You can specify `stop` as first argument, to only stop all vms and logout from all iscsi devices. The script doesn't start/boot VMs listed in `/etc/xen/disabled_vms.txt` (one VM per line).


#### `disable_vms.sh`

A script which list and modifies disabled VMs. VMs listed in `/etc/xen/disabled_vms.txt`. You can simply run it on our hypervisor, it's already in you `$PATH`.
