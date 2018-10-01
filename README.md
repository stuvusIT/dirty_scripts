# Dirty scripts

## `config.inc.sh`

Your user configuration, set `REMOTE_USER` to your stuvus username.


## `safe_restart_vms.sh`

A script which restart all vms and iscsi devices at our hypervisor. This script is intended to be executed directly at the hypervisor or is invoked by `reboot.sh` . You can specify `stop` as first argument, to only stop all vms and logout from all iscsi devices.


## `reboot.sh`

This script is intended to safety reboot our hypervisor.

It requires following tools installed:

 * nmap
 * ping
 * xfreerdp
 * sed
 * scp,ssh
 * curl
 * grep