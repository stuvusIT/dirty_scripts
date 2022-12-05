#!/usr/bin/env python3
from typing import List, Optional, Tuple, Dict, Any

import os
import argparse
import subprocess
import datetime
import json
import udatetime

ZFS_SNAPSHOTDIR = '.zfs/snapshot'

SNAPSHOT_TAG = "snapshot="
LOGICAL_REFERENCED_TAG = "logicalreferenced="

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


def _get_year(timestamp: int) -> int:
    return datetime.datetime.fromtimestamp(timestamp).year


def _get_month(timestamp: int) -> int:
    return datetime.datetime.fromtimestamp(timestamp).month


def _get_week(timestamp: int) -> int:
    return datetime.datetime.fromtimestamp(timestamp).isocalendar()[1]


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
        self._dry_run_finished_backups: List[Dict[str, Any]] = []

    def _restic_cmd(self, restic_repo: str, restic_command: str, flags: List[str] = []) -> str:
        initial_args = ["-r", restic_repo, "--password-file", self.restic_password_file, restic_command]
        args = initial_args + flags
        arg_string = " ".join([f"'{arg}'" for arg in args])
        return f"restic {arg_string}"

    def _get_dataset_snapshots(self, dataset_name: str) -> List[Dict[str, Any]]:
        lines = _eval(f"sudo zfs list -Hp -o name,creation,used,logicalreferenced -t snapshot '{dataset_name}'")
        snapshots: List[Dict[str, Any]] = []
        for line in lines.split("\n"):
            if len(line) == 0:
                continue
            values = line.split("\t")
            snapshot: Dict[str, Any] = {
                "name": values[0].split("@")[-1],
                "creation": int(values[1]),
                "used": int(values[2]),
                "logicalreferenced": int(values[3]),
            }
            snapshots.append(snapshot)
        snapshots_with_size = []
        for i, snapshot in enumerate(snapshots):
            if i == 0 or snapshots[i - 1]["used"] != 0:
                snapshots_with_size.append(snapshot)
                continue
            parent_name = snapshots[i - 1]["name"]
            snapshot_name = snapshot["name"]
            if "0\n" != _eval(f"zfs diff {dataset_name}@{parent_name} {dataset_name}@{snapshot_name} 2>&1 | head -c1 | wc -c"):
                snapshots_with_size.append(snapshot)
                continue
            print(F"Not considering snapshot {dataset_name}@{snapshot_name} because of zero diff.")
        return snapshots_with_size

    def _get_snapshot_tag(self, datum: Dict[str, Any]) -> str:
        tags = datum["tags"]
        tag: str
        for tag in tags:
            if tag.startswith(SNAPSHOT_TAG):
                return tag[len(SNAPSHOT_TAG):]
        raise Exception("Snapshot does not have a valid snapshot tag.")

    def _get_snapshots_in_restic(self, restic_repo: str) -> List[Dict[str, Any]]:
        json_data = _eval(self._restic_cmd(restic_repo, "snapshots", ["--json"]))
        data = json.loads(json_data)
        return [{
            "id": datum["id"],
            "name": self._get_snapshot_tag(datum),
            "creation": datetime.datetime.timestamp(udatetime.from_string(datum["time"])),
        } for datum in data]

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

    def _backup_single_snapshot(self, dataset_name: str, snapshot: Dict[str, Any], parent_restic_snapshot_id: Optional[str]):
        snapshot_name = snapshot["name"]
        restic_repo, path_in_restic_repo = self._get_repo_name_and_path(dataset_name)

        ds_mountpoint = _eval(f"zfs get -Hp -o value mountpoint '{dataset_name}'").strip()
        snapshot_path = "/".join([ds_mountpoint, ZFS_SNAPSHOTDIR, snapshot_name])

        snapshot_time_readable = str(datetime.datetime.fromtimestamp(snapshot["creation"]))

        # Use proot to "mount" coorect path. See https://github.com/restic/restic/issues/2092
        proot_command = f"proot -b '{snapshot_path}':'{path_in_restic_repo}'"
        logical_referenced = snapshot["logicalreferenced"]
        tags = [f"{SNAPSHOT_TAG}{snapshot_name}",
                f"{LOGICAL_REFERENCED_TAG}{logical_referenced}"]
        tags_with_flag = []
        for tag in tags:
            tags_with_flag.append("--tag")
            tags_with_flag.append(tag)
        restic_backup_args = ["--ignore-ctime", "--time", snapshot_time_readable, "--compression", "max"] + tags_with_flag
        if parent_restic_snapshot_id is not None:
            restic_backup_args += ["--parent", parent_restic_snapshot_id]
        restic_backup_args.append(path_in_restic_repo)
        restic_command = self._restic_cmd(restic_repo, "backup", restic_backup_args)
        print(f"Starting backup of {dataset_name}@{snapshot_name} into {restic_repo} under {path_in_restic_repo}")
        if self.dry_run:
            print(f"Would run: {proot_command} {restic_command}")
            id = len(self._dry_run_finished_backups)
            self._dry_run_finished_backups.append({
                "id": f"__dry_run_{id}",
                "name": snapshot["name"],
                "creation": snapshot["creation"],
            })
        else:
            _run(f"{proot_command} {restic_command}")

    def backup_single_snapshot(self, dataset_name: str, snapshot_name: str, parent_restic_snapshot_id: Optional[str]):
        self._pre(dataset_name)
        snapshots = self._get_dataset_snapshots(dataset_name)
        snapshots_with_correct_name = [snapshot for snapshot in snapshots if snapshot["name"] == snapshot_name]
        if len(snapshots_with_correct_name) < 1:
            raise Exception("Did not find a snapshot with that name")
        self._backup_single_snapshot(dataset_name, snapshots_with_correct_name[0], parent_restic_snapshot_id)
        self._post(dataset_name)

    def _is_among_n_newest(self, snapshots_to_consider: List[Dict[str, Any]], snapshot: Dict[str, Any], n: int):
        num_newer = sum(s["creation"] > snapshot["creation"] for s in snapshots_to_consider)
        return num_newer < n

    def _is_weekly(self, snapshots: List[Dict[str, Any]], snapshot: Dict[str, Any]) -> bool:
        year = _get_year(snapshot["creation"])
        week = _get_week(snapshot["creation"])
        snapshots_in_that_week = [snapshot for snapshot in snapshots if _get_week(snapshot["creation"]) == week and _get_year(snapshot["creation"]) == year]
        return self._is_among_n_newest(snapshots_in_that_week, snapshot, 1)

    def _is_monthly(self, snapshots: List[Dict[str, Any]], snapshot: Dict[str, Any]) -> bool:
        year = _get_year(snapshot["creation"])
        month = _get_month(snapshot["creation"])
        snapshots_in_that_month = [snapshot for snapshot in snapshots if _get_month(snapshot["creation"]) == month and _get_year(snapshot["creation"]) == year]
        return self._is_among_n_newest(snapshots_in_that_month, snapshot, 1)

    def _must_keep(self, snapshots: List[Dict[str, Any]], snapshot: Dict[str, Any], keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]) -> bool:
        if keep_last_n is None and keep_weekly_n is None and keep_monthly_n is None:
            return True

        # Last n
        if keep_last_n is not None and self._is_among_n_newest(snapshots, snapshot, keep_last_n):
            return True

        # Weekly n
        if keep_weekly_n is not None and self._is_weekly(snapshots, snapshot):
            # This is a weekly snapshot
            weekly_snapshots = [snapshot for snapshot in snapshots if self._is_weekly(snapshots, snapshot)]
            if self._is_among_n_newest(weekly_snapshots, snapshot, keep_weekly_n):
                return True

        # Monthly n
        if keep_monthly_n is not None and self._is_monthly(snapshots, snapshot):
            # This is a monthly snapshot
            monthly_snapshots = [snapshot for snapshot in snapshots if self._is_monthly(snapshots, snapshot)]
            if self._is_among_n_newest(monthly_snapshots, snapshot, keep_monthly_n):
                return True

        return False

    def _find_next_snapshot(self, dataset_name: str, snapshots: List[Dict[str, Any]], snapshots_in_restic: List[Dict[str, Any]],
                            keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]) -> Optional[Dict[str, Any]]:
        """
        `snapshots` must be sorted by creation time.
        """
        snapshot_names_in_restic = set([s["name"] for s in snapshots_in_restic])
        for snapshot in snapshots:
            snapshot_name = snapshot["name"]
            if not self._must_keep(snapshots, snapshot, keep_last_n, keep_weekly_n, keep_monthly_n):
                print(F"Skipping snapshot {dataset_name}@{snapshot_name} because it does not need to be kept according to the policy.")
                continue
            if snapshot_name in snapshot_names_in_restic:
                print(F"Skipping snapshot {dataset_name}@{snapshot_name} because it's already migrated.")
                continue
            return snapshot
        return None

    def _backup_next_snapshot_from_dataset(self, dataset_name, snapshots: List[Dict[str, Any]], keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]) -> Optional[Dict[str, Any]]:
        restic_repo, _ = self._get_repo_name_and_path(dataset_name)

        snapshots_in_restic = self._get_snapshots_in_restic(restic_repo)
        if self.dry_run:
            snapshots_in_restic += self._dry_run_finished_backups

        snapshot = self._find_next_snapshot(dataset_name, snapshots, snapshots_in_restic, keep_last_n, keep_weekly_n, keep_monthly_n)
        if snapshot is None:
            print(f"No further snapshots need to backuped for {dataset_name}.")
            return None

        parent_restic_snapshot_id = None
        ancestors_in_restic = [ancestor for ancestor in snapshots_in_restic if ancestor["creation"] < snapshot["creation"]]
        if len(ancestors_in_restic) > 0:
            parent_restic_snapshot_id = ancestors_in_restic[-1]["id"]
        self._backup_single_snapshot(dataset_name, snapshot, parent_restic_snapshot_id)
        return snapshot

    def backup_next_snapshot_from_dataset(self, dataset_name, keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]):
        self._pre(dataset_name)
        snapshots = self._get_dataset_snapshots(dataset_name)
        self._backup_next_snapshot_from_dataset(dataset_name, snapshots, keep_last_n, keep_weekly_n, keep_monthly_n)
        self._post(dataset_name)

    def _backup_dataset(self, dataset_name: str, keep_last_n: Optional[int], keep_weekly_n: Optional[int], keep_monthly_n: Optional[int]):
        snapshots = self._get_dataset_snapshots(dataset_name)
        while True:
            added_snapshot = self._backup_next_snapshot_from_dataset(dataset_name, snapshots, keep_last_n, keep_weekly_n, keep_monthly_n)
            if added_snapshot is None:
                break
            index = snapshots.index(added_snapshot)
            snapshots = snapshots[index + 1:]

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
