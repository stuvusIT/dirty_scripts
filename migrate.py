#!/usr/bin/env python3
from typing import List, Optional, Tuple, Dict, Any

import os
import argparse
import subprocess
import datetime
import json

ZFS_SNAPSHOTDIR = '.zfs/snapshot'

SNAPSHOT_TAG = "snapshot="
LOGICAL_REFERENCE_TAG = "logicalreferenced="

DEBUG = False


def _run(command: str, input: Optional[str] = None, void_stderr: bool = False) -> None:
    other_args = dict()
    if void_stderr and not DEBUG:
        other_args["stderr"] = subprocess.DEVNULL
    subprocess.run(command, shell=True, text=True, input=input, **other_args)


def _eval(command: str, input: Optional[str] = None, void_stderr: bool = False) -> str:
    other_args = dict()
    if void_stderr and not DEBUG:
        other_args["stderr"] = subprocess.DEVNULL
    return subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, input=input, **other_args).stdout


def _get_year(date: str) -> int:
    return int(date[:4])


def _get_month(date: str) -> int:
    return int(date[4:6])


def _get_day(date: str) -> int:
    return int(date[6:8])


def _get_week(date: str) -> int:
    return datetime.date(_get_year(date), _get_month(date), _get_day(date)).isocalendar()[1]


class Backuper:

    def __init__(self,
                 restic_repo_prefix: str,
                 zfs_dataset_common_prefix: str,
                 restic_password_file: str,
                 dry_run: bool):
        self.restic_repo_prefix: str = restic_repo_prefix.rstrip("/")
        self.zfs_dataset_common_prefix: str = zfs_dataset_common_prefix
        self.restic_password_file: str = restic_password_file
        self.dry_run: bool = dry_run
        self._dry_run_finished_backups: Dict[str, str] = dict()

    def _restic_cmd(self, restic_repo: str, restic_command: str, flags: List[str] = []) -> str:
        initial_args = ["-r", restic_repo, "--password-file", self.restic_password_file, restic_command]
        args = initial_args + flags
        arg_string = " ".join([f"'{arg}'" for arg in args])
        return f"restic {arg_string}"

    def _get_dataset_snapshots(self, dataset_name: str) -> List[str]:
        lines = _eval(f"sudo zfs list -Hp -o name -t snapshot '{dataset_name}'")
        snapshots = [line.split("@")[-1] for line in lines.split("\n") if len(line) > 0]
        return snapshots

    def _get_snapshot_tag(self, datum: Dict[str, Any]) -> str:
        tags = datum["tags"]
        tag: str
        for tag in tags:
            if tag.startswith(SNAPSHOT_TAG):
                return tag[len(SNAPSHOT_TAG):]
        raise Exception("Snapshot does not have a valid snapshot tag.")

    def _get_snapshots_in_restic(self, restic_repo: str) -> Dict[str, str]:
        json_data = _eval(self._restic_cmd(restic_repo, "snapshots", ["--json"]))
        data = json.loads(json_data)
        return {self._get_snapshot_tag(datum): datum["short_id"] for datum in data}

    def _get_zfs_snapshot_size(self, dataset_name: str, snapshot_name: str) -> int:
        result = _eval(f"sudo zfs list -Hp -o used -t snapshot '{dataset_name}@{snapshot_name}'")
        return int(result)

    def _get_zfs_snapshot_logical_refrence_size(self, dataset_name: str, snapshot_name: str) -> int:
        result = _eval(f"sudo zfs get logicalreferenced '{dataset_name}@{snapshot_name}' -Hpo value")
        return int(result)

    def _get_repo_name_and_path(self, dataset_name) -> Tuple[str, str]:
        ds_name_without_prefix = dataset_name.removeprefix(self.zfs_dataset_common_prefix).strip("/")
        repo_name = "/".join([self.restic_repo_prefix, ds_name_without_prefix])
        path_in_restic_repo = "/" + ds_name_without_prefix

        return repo_name, path_in_restic_repo

    def _init_restic_repo(self, restic_repo):
        result = _eval(self._restic_cmd(restic_repo, "cat", ["config"]), void_stderr=True)
        if "chunker_polynomial" not in result:
            print(f"Initializing restic repo {restic_repo}.")
            _run(self._restic_cmd(restic_repo, "init"))
        else:
            print(f"Restic repo {restic_repo} already initialized.")

    def _check_restic_repo(self, restic_repo):
        print(f"Checking restic repo {restic_repo}.")
        _run(self._restic_cmd(restic_repo, "check"))

    def _pre(self, dataset_name):
        _run(f"zfs mount {dataset_name}")
        restic_repo, _ = self._get_repo_name_and_path(dataset_name)
        self._init_restic_repo(restic_repo)

    def _post(self, dataset_name):
        restic_repo, _ = self._get_repo_name_and_path(dataset_name)
        self._check_restic_repo(restic_repo)

    def _backup_single_snapshot(self, dataset_name: str, snapshot_name: str, parent_restic_snapshot: Optional[str]):
        full_snapshot_name = f"{dataset_name}@{snapshot_name}"
        restic_repo, path_in_restic_repo = self._get_repo_name_and_path(dataset_name)

        ds_mountpoint = _eval(f"zfs get -Hp -o value mountpoint '{dataset_name}'").strip()
        snapshot_path = "/".join([ds_mountpoint, ZFS_SNAPSHOTDIR, snapshot_name])

        snapshot_time = _eval(f"zfs get -Hp -o value creation '{full_snapshot_name}'")
        snapshot_time_readble = str(datetime.datetime.fromtimestamp(int(snapshot_time)))

        # Use proot to "mount" coorect path. See https://github.com/restic/restic/issues/2092
        proot_command = f"proot -b '{snapshot_path}':'{path_in_restic_repo}'"
        tags = [f"{SNAPSHOT_TAG}{snapshot_name}",
                f"{LOGICAL_REFERENCE_TAG}{self._get_zfs_snapshot_logical_refrence_size(dataset_name, snapshot_name)}"]
        tags_with_flag = []
        for tag in tags:
            tags_with_flag.append("--tag")
            tags_with_flag.append(tag)
        restic_backup_args = ["--ignore-ctime", "--time", snapshot_time_readble, "--compression", "max"] + tags_with_flag
        if parent_restic_snapshot is not None:
            restic_backup_args += ["--parent", parent_restic_snapshot]
        restic_backup_args.append(path_in_restic_repo)
        restic_command = self._restic_cmd(restic_repo, "backup", restic_backup_args)
        print(f"Starting backup of {dataset_name}@{snapshot_name} into {restic_repo} under {path_in_restic_repo}")
        if self.dry_run:
            print(f"Would run: {proot_command} {restic_command}")
            self._dry_run_finished_backups[snapshot_name] = "__dry_run__"
        else:
            _run(f"{proot_command} {restic_command}")

    def backup_single_snapshot(self, dataset_name: str, snapshot_name: str, parent_restic_snapshot: Optional[str]):
        self._pre(dataset_name)
        self._backup_single_snapshot(dataset_name, snapshot_name, parent_restic_snapshot)
        self._post(dataset_name)

    def _find_newest_snapshot_in_restic(self, snapshots_in_restic: Dict[str, str]):
        snapshots = list(snapshots_in_restic.keys())
        snapshots.sort()
        return snapshots[-1]

    def _is_snapshot_in_tail_of_list(self, snapshots_to_consider: List[str], snapshot: str, tail_size: int):
        snapshots_to_consider.sort()
        last_index = snapshots_to_consider.index(snapshot)
        if last_index >= len(snapshots_to_consider) - tail_size:
            return True

    def _is_weekly(self, snapshots: List[str], snapshot: str) -> bool:
        year = _get_year(snapshot)
        week = _get_week(snapshot)
        snapshots_in_that_week = [snapshot for snapshot in snapshots if _get_week(snapshot) == week and _get_year(snapshot) == year]
        snapshots_in_that_week.sort()
        return snapshot == snapshots_in_that_week[-1]

    def _is_monthly(self, snapshots: List[str], snapshot: str) -> bool:
        year = _get_year(snapshot)
        month = _get_month(snapshot)
        snapshots_in_that_month = [snapshot for snapshot in snapshots if _get_month(snapshot) == month and _get_year(snapshot) == year]
        snapshots_in_that_month.sort()
        return snapshot == snapshots_in_that_month[-1]

    def _must_keep(self, snapshots: List[str], snapshot: str, keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]) -> bool:
        # Last n
        if keep_last_n is None:
            return True
        if self._is_snapshot_in_tail_of_list(snapshots, snapshot, keep_last_n):
            return True

        # Weekly n
        if self._is_weekly(snapshots, snapshot):
            # This is a weekly snapshot
            if keep_weekly_n is None:
                return True
            weekly_snapshots = [snapshot for snapshot in snapshots if self._is_weekly(snapshots, snapshot)]
            if self._is_snapshot_in_tail_of_list(weekly_snapshots, snapshot, keep_weekly_n):
                return True

        # Monthly n
        if self._is_monthly(snapshots, snapshot):
            # This is a monthly snapshot
            if keep_monthly_n is None:
                return True
            monthly_snapshots = [snapshot for snapshot in snapshots if self._is_monthly(snapshots, snapshot)]
            if self._is_snapshot_in_tail_of_list(monthly_snapshots, snapshot, keep_monthly_n):
                return True

        return False

    def _find_next_snapshot(self, dataset_name: str, snapshots: List[str], newest_snapshot_in_restic: str,
                            keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]) -> Optional[str]:
        snapshots.sort()
        snapshots_with_size = [snapshot for snapshot in snapshots if self._get_zfs_snapshot_size(dataset_name, snapshot) != 0]
        for snapshot in snapshots:
            if snapshot <= newest_snapshot_in_restic:
                # We have that already (or skipped it)
                continue
            if self._get_zfs_snapshot_size(dataset_name, snapshot) == 0:
                print(F"Skipping snapshot {dataset_name}@{snapshot} because of zero size.")
                continue
            if not self._must_keep(snapshots_with_size, snapshot, keep_last_n, keep_weekly_n, keep_monthly_n):
                print(F"Skipping snapshot {dataset_name}@{snapshot} because it does not need to be kept according to the keep pattern.")
                continue
            return snapshot
        return None

    def _backup_next_snapshot_from_dataset(self, dataset_name, keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]) -> bool:
        restic_repo, _ = self._get_repo_name_and_path(dataset_name)

        snapshots = self._get_dataset_snapshots(dataset_name)
        snapshots_in_restic = self._get_snapshots_in_restic(restic_repo)
        if self.dry_run:
            snapshots_in_restic.update(self._dry_run_finished_backups)
        parent_restic_snapshot = None
        newest_snapshot_in_restic = "00000000"
        if len(snapshots_in_restic) > 0:
            newest_snapshot_in_restic = self._find_newest_snapshot_in_restic(snapshots_in_restic)
            parent_restic_snapshot = snapshots_in_restic[newest_snapshot_in_restic]
        snapshot = self._find_next_snapshot(dataset_name, snapshots, newest_snapshot_in_restic, keep_last_n, keep_weekly_n, keep_monthly_n)
        if snapshot is None:
            print(f"No further snapshots need to backuped for {dataset_name}.")
            return False
        self._backup_single_snapshot(dataset_name, snapshot, parent_restic_snapshot)
        return True

    def backup_next_snapshot_from_dataset(self, dataset_name, keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]):
        self._pre(dataset_name)
        self._backup_next_snapshot_from_dataset(dataset_name, keep_last_n, keep_weekly_n, keep_monthly_n)
        self._post(dataset_name)

    def _backup_dataset(self, dataset_name: str, keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]):
        while self._backup_next_snapshot_from_dataset(dataset_name, keep_last_n, keep_weekly_n, keep_monthly_n):
            pass

    def backup_dataset(self, dataset_name: str, keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]):
        self._pre(dataset_name)
        self._backup_dataset(dataset_name, keep_last_n, keep_weekly_n, keep_monthly_n)
        self._post(dataset_name)


def main():
    if os.geteuid() != 0:
        print("Please run as root.")
        exit(1)
    parser = argparse.ArgumentParser(description='Migrate zfs backups to restic.')
    parser.add_argument('-r', '--restic-repo-prefix', required=True,
                        help='The prefix used for the restic repo. It is appended with the dataset name.')
    parser.add_argument('-c', '--zfs-dataset-common-prefix', default="",
                        help='The prefix which should be removed from each dataset name for use in the restic repo. Eg. backup01')
    parser.add_argument('-p', '--restic-password-file', required=True,
                        help='The path to the restic password file.')
    parser.add_argument('--dry-run', required=False, action='store_true',
                        help='Perform a dryrun, do not backup anything.')

    subparsers = parser.add_subparsers(title='commands', description="The command to run", required=True, dest='subparser_name')

    parser_single_snapshot = subparsers.add_parser('single_snapshot', help='Backup a single snapshot')
    parser_single_snapshot.add_argument('dataset_name',
                                        help="The name of the dataset to backup.")
    parser_single_snapshot.add_argument('snapshot_name',
                                        help="The name of the snapshot to backup.")
    parser_single_snapshot.add_argument('-P', '--parent_snapshot', default=None,
                                        help="The name of the parent snapshot.")

    parser_next_snapshot = subparsers.add_parser('next_snapshot_in_dataset', help='Backup the next snapshots of a dataset')
    parser_next_snapshot.add_argument('dataset_name',
                                      help="The name of the dataset to backup.")
    parser_next_snapshot.add_argument('--keep-last-n', default=None, type=int,
                                      help="Keep the last n snapshots. Defaults to all")
    parser_next_snapshot.add_argument('--keep-weekly-n', default=None, type=int,
                                      help="Keep the last n weekly snapshots. A weekly snapshot is the newest snapshot in a week. Defaults to all")
    parser_next_snapshot.add_argument('--keep-monthly-n', default=None, type=int,
                                      help="Keep the last n monthly snapshots. A monthly snapshot is the newest snapshot in a month. Defaults to all")

    parser_single_dataset = subparsers.add_parser('dataset', help='Backup all snapshots of a dataset')
    parser_single_dataset.add_argument('dataset_name',
                                       help="The name of the dataset to backup.")
    parser_single_dataset.add_argument('--keep-last-n', default=None, type=int,
                                       help="Keep the last n snapshots. Defaults to all")
    parser_single_dataset.add_argument('--keep-weekly-n', default=None, type=int,
                                       help="Keep the last n weekly snapshots. A weekly snapshot is the newest snapshot in a week. Defaults to all")
    parser_single_dataset.add_argument('--keep-monthly-n', default=None, type=int,
                                       help="Keep the last n monthly snapshots. A monthly snapshot is the newest snapshot in a month. Defaults to all")

    args = parser.parse_args()

    backuper = Backuper(restic_repo_prefix=args.restic_repo_prefix, zfs_dataset_common_prefix=args.zfs_dataset_common_prefix, restic_password_file=args.restic_password_file, dry_run=args.dry_run)

    if args.subparser_name == "single_snapshot":
        if args.parent_snapshot is None:
            print("Caution: No parent specified. This can greatly reduce performance.")
        backuper.backup_single_snapshot(dataset_name=args.dataset_name, snapshot_name=args.snapshot_name, parent_restic_snapshot=args.parent_snapshot)
    elif args.subparser_name == "next_snapshot_in_dataset":
        backuper.backup_next_snapshot_from_dataset(dataset_name=args.dataset_name, keep_last_n=args.keep_last_n, keep_weekly_n=args.keep_weekly_n, keep_monthly_n=args.keep_monthly_n)
    elif args.subparser_name == "dataset":
        backuper.backup_dataset(dataset_name=args.dataset_name, keep_last_n=args.keep_last_n, keep_weekly_n=args.keep_weekly_n, keep_monthly_n=args.keep_monthly_n)


if __name__ == "__main__":
    main()
