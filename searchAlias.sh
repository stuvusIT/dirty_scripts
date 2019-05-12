#!/bin/bash
[[ $# -ne 1 ]] && echo "Usage: $0 <alias>" && exit 2
dnA=$(ldapsearch -LLL -x -b "ou=mail,ou=faveve,dc=faveve,dc=uni-stuttgart,dc=de" | perl -p00e 's/\r?\n //g' | grep dn: | grep "$1")
listOfDn=$(echo $dnA | sed 's/dn: /\ndn:/g')
for dn in $listOfDn; do
	dn=$(echo $dn | sed 's/^dn:/dn: /')
	printf '\e[1;33m%*s\e[0m\n' "${COLUMNS:-$(tput cols)}" '' | tr ' ' =
	echo $dn
	printf '\e[1;33m%*s\e[0m\n' "${COLUMNS:-$(tput cols)}" '' | tr ' ' -
	ldapsearch -LLL -x -b "${dn:4}"
done
