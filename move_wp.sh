#!/usr/bin/env bash
# Script I used to move our WordPress instances to one machine. Some things are hardcoded but it may be useful nonetheless
# usage: ./move_wp.sh <IP of old instance> <folder/db name of new instance>
set -o xtrace
ssh "$1" 'sudo grep wp-admin /var/log/nginx/access.log |grep -v upgrade_db |tail'
read -p "Continue (y/n)? " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
	ssh "$1" "sudo systemctl stop nginx"
	ssh -A 129.69.139.89 "sudo mysql -e \"create database \\\`$2\\\`;\"; sudo mysql $2 < <(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null mweitbrecht@$1 \"sudo mysqldump wordpress\")"
	ssh -A "$1" "sudo -E -s rsync -ahixEAXP -e \"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null\" --rsync-path=\"sudo rsync\" --stats /var/www/wordpress/ mweitbrecht@129.69.139.89:/var/www/wordpress-$2"
	ssh -A "$1" "sudo -E -s scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /etc/ssl/privkey.pem mweitbrecht@129.69.139.89:/home/mweitbrecht/privkey-$2.pem"
	ssh -A "$1" "sudo -E -s scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /etc/ssl/fullchain.pem mweitbrecht@129.69.139.89:/home/mweitbrecht/fullchain-$2.pem"
	ssh 129.69.139.89 "sudo mv privkey* fullchain* /etc/ssl"
fi
