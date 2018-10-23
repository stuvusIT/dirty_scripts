#!/usr/bin/env bash
BASE_DIR="$( dirname "$( realpath -s "${BASH_SOURCE[0]}" )" )/"
source ./config.inc.sh

[ "$1" = "-u" ] && only_neg="true"

[ -d "$SUBMODULE_TEST_DIR" ] || git clone --depth 1 git@github.com:Mr-Pi/stuvus_config "$SUBMODULE_TEST_DIR"
cd "$SUBMODULE_TEST_DIR"
git pull >/dev/null || { echo -e "\e[1;31mFailed to update repository.\e[0m;"; exit 1; }
git submodule update --recursive --init

IFS=$'\n'
for module_str in $(git submodule status); do
	IFS=' ' read -ra module <<< "$module_str"
	if echo "${module[2]}"|grep -q "master"; then
		[ -z "$only_neg" ] && echo -e "\e[3;33m${module[1]}\r\t\t\t\t\t\e[0;1;32m is up to date\e[0m"
	else
		echo -e "\e[3;33m${module[1]}\r\t\t\t\t\t\e[0;1;31m is not up to date\e[0m"
	fi
done
