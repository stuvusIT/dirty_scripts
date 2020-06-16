#!/bin/bash
#/etc/cron.hourly
rsync -av /lib/modules/ /vms/kernel-modules >/dev/null

