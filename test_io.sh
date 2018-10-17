#!/usr/bin/env bash
[ $USER != "root" ] && { sudo $0 $@; exit $?; }
BASE_DIR="$( dirname "$( realpath -s "${BASH_SOURCE[0]}" )" )/"
cd $BASE_DIR

set -e
set -u
set -o pipefail

function LOGIT {
	echo -e -n "\e[1;33m$*\e[0m"
}

function TEST {
	local t_start=$(date +%s)
	$*
	wait
	local t_end=$(date +%s)
	local t_dur=$((t_end - t_start))
	LOGIT "\e[32m$t_dur seconds!\n"
}



function TEST_100M {
	dd if=/tmp/test.bin.img of=/io_test/test.bin.img bs=1M count=100 conv=fsync iflag=fullblock,sync oflag=sync &>/dev/null
	dd if=/io_test/test.bin.img of=/dev/null bs=1M count=100 iflag=fullblock,sync oflag=sync &>/dev/null
}
function TEST_M {
	local tasks=$1
	local task_size=$2
	local mod=$(( 100 / task_size ))

	echo -n -e "\r\t\t\tTest processes are starting"

	for i in `seq 1 $tasks`; do
		(
			skip=$(( i % mod ))
#			echo -e "\ntasks=$tasks, task_size=$task_size, skip=$skip, i=$i"
			dd if=/tmp/test.bin.img of=/io_test/test_${tasks}_${task_size}_${i}.bin.img bs=${task_size}M count=1 conv=fsync iflag=fullblock,sync oflag=sync skip=$skip &>/dev/null
			dd if=/io_test/test_${tasks}_${task_size}_${i}.bin.img of=/dev/null bs=${task_size}M iflag=fullblock,sync oflag=sync &>/dev/null

			rm /io_test/test_${tasks}_${task_size}_${i}.bin.img
		) &
		echo -n -e "\r\t\t\t$i of $tasks processes are started.            \r"
	done
	local num_children=`ps --no-headers -o pid --ppid=$$ | wc -w`
	while [ $num_children -gt 1 ]; do
		echo -n -e "\r\t\t\tWait for $num_children processes.           \r"
		sleep 0.5
		num_children=`ps --no-headers -o pid --ppid=$$ | wc -w`
	done
	echo -n -e "\r\t\t\t                                               \r\t\t\t"
	wait
	sync
}


ulimit -n 65536
ulimit -u 65536
ulimit -a
LOGIT "\nPress return to start IO-Test\n"
read


mkdir -pv /io_test/

LOGIT "Generate binary test image\n"

dd if=/dev/urandom of=/tmp/test.bin.img bs=1M status=progress conv=fsync iflag=fullblock,sync oflag=sync count=100 &>/dev/null

t_start=$(date +%s)

LOGIT "Test 1 task @100M...\t"
TEST TEST_100M

for tasks in 10 100 1000 2000; do
	LOGIT "Test $tasks tasks @1M..."
	TEST TEST_M $tasks 1
done

for tasks in 10 100 200 500; do
	LOGIT "Test $tasks tasks @10M."
	TEST TEST_M $tasks 10
done

rm -rfv /io_test/
sync

t_end=$(date +%s)
t_dur=$((t_end - t_start))

LOGIT "\n\n\tOverall it takes about \e[32m$t_dur\e[33m seconds.\n\n\n"
