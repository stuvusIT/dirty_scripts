#!/usr/bin/env bash
BASE_DIR="$( dirname "$( realpath -s "${BASH_SOURCE[0]}" )" )/"
source ./config.inc.sh

[ "$1" = "-u" ] && only_neg="true"

[ -d "$SUBMODULE_TEST_DIR" ] || git clone --depth 1 --recurse-submodules git@github.com:Mr-Pi/stuvus_config "$SUBMODULE_TEST_DIR"
cd "$SUBMODULE_TEST_DIR/roles/"
git submodule update --recursive --init
for role in *; do
	cd $role
	if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/master)" ]; then
		[ -z "$only_neg" ] && echo -e "\e[3;33m$role\r\t\t\t\e[0;1;32m is up to date\e[0m"
	else
		echo -e "\e[3;33m$role\r\t\t\t\e[0;1;31m is not up to date\e[0m"
	fi
	cd ..
done
