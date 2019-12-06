#! /bin/bash
# list scanned tags on door01 with human readable date
lines=$1
pattern=$2
if [ -z $lines ] || [ -z $pattern ]
then echo "usage: $0 <lines for tail e.g. 1000> <all or new>"
  exit 1
fi

if [ $pattern == "new" ]
then 
tail -n $lines /var/local/entman01.history | grep 'Unknown' | jq '.time,.token' | awk '{ if (NR%2==0) printf "echo ID: "$1"\n"; else print "\n echo Date: && date +%Y-%m-%e_%k:%M:%S -d @" $1"&& echo "$1;}' | sh
exit 0
fi

if [ $pattern == "all" ]
then 
tail -n $lines /var/local/entman01.history | jq '.time,.token' | awk '{ if (NR%2==0) printf "echo ID: "$1"\n"; else print "\n echo Date: && date +%Y-%m-%e_%k:%M:%S -d @" $1"&& echo "$1;}' | sh
exit 0
fi
exit 1
