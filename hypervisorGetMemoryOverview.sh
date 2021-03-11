#!/usr/bin/env bash

format="%32s :%5s GiB\n"

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

echo "Memory overview: "

total_mib="$(sudo xl info | grep total_memory | sed -e 's/^.*: //')"
free_mib="$(sudo xl info | grep free_memory | sed -e 's/^.*: //')"

total=`expr $total_mib / 1024`
free=`expr $free_mib / 1024`
used=`expr $total - $free`

printf "$format" "Total" "$total"
printf "$format" "Free" "$free"
printf "$format" "Used" "$used"

echo ""
echo "Doms:"

doms="$(sudo xl list | grep -v 'Name')"

OOIFS="$IFS"
total="0"
while IFS= read -r line ;do
  dom_name=""
  dom_mem_mib=""
  col_id=0
  OIFS="$IFS"
  IFS=' '
  for column in $line ;do
    if [ $col_id -eq 0 ] ;then
      dom_name="$column"
    fi
    if [ $col_id -eq 2 ] ;then
      dom_mem_mib="$column"
    fi
    col_id=`expr $col_id + 1`
  done
  IFS="$OIFS"
  dom_mem=`expr $dom_mem_mib / 1024`
  total=`expr $total + $dom_mem`
  printf "$format" "$dom_name" "$dom_mem"
done <<< "$doms"
IFS="$OOIFS"

echo ""
printf "$format" "Sum" "$total"
