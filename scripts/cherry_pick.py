#!/usr/bin/env python3
"""
Cherry-pick a commit (default: latest on main) into all lesson branches.

Branch patterns:
 - Lxx-teacher
 - Lxx-student-starter
 - Lxx-student-end

Default flow:
 1) Ensures a clean working tree
 2) Detects main/master branch
 3) Determines target commit:
	 * Latest on main (default), or
	 * Specific SHA provided via --commit <sha>
 4) Prints commit details & confirms (unless --yes)
 5) Finds lesson branches (local + remote) by pattern (or subset via --only)
 6) Cherry-picks the commit into each branch

Conflict handling modes:
 * Default: if conflict occurs, abort cherry-pick for that branch (leaves branch unchanged) and continue.
 * --main-wins: automatically prefer the incoming commit's version ("theirs" in git strategy terms) for textual conflicts.
	 This uses `git cherry-pick -X theirs` so the main commit content overwrites conflicting hunks on lesson branches.

Requires: git installed and available on PATH.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple
import argparse


def run(cmd: List[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
	"""Run a command and return the completed process, raising on failure when check=True."""
	return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def git(args: List[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
	"""Run a git command and return the completed process."""
	return run(["git", *args], cwd=cwd, check=check)


def ensure_repo_root() -> str:
	"""Return the git repository root directory."""
	try:
		cp = git(["rev-parse", "--show-toplevel"])
	except subprocess.CalledProcessError as e:
		print("Error: not inside a git repository.")
		print(e.stderr.strip())
		sys.exit(1)
	return cp.stdout.strip()


def ensure_clean_worktree(repo: str) -> None:
	"""Fail if there are uncommitted changes or ongoing merges/rebases."""
	# Check for uncommitted changes
	cp = git(["status", "--porcelain"], cwd=repo)
	if cp.stdout.strip():
		print("Error: working tree is not clean. Commit or stash changes first.")
		sys.exit(1)
	# Check for ongoing operations
	cp2 = git(["status", "--porcelain", "--branch"], cwd=repo)
	status_text = cp2.stdout
	for marker in ["rebase", "merge", "cherry-pick", "bisect"]:
		if marker in status_text.lower():
			print(f"Error: repository has an ongoing {marker} operation.")
			sys.exit(1)


def detect_main_branch(repo: str) -> str:
	"""Return 'main' if exists, else 'master' if exists; otherwise abort."""
	for b in ("main", "master"):
		try:
			git(["rev-parse", "--verify", b], cwd=repo)
			return b
		except subprocess.CalledProcessError:
			continue
	print("Error: neither 'main' nor 'master' branch exists.")
	sys.exit(1)


@dataclass
class CommitInfo:
	sha: str
	subject: str
	files: List[str]


def get_commit_info(repo: str, sha: str) -> CommitInfo:
	"""Return CommitInfo for the given SHA (must exist)."""
	try:
		resolved = git(["rev-parse", sha], cwd=repo).stdout.strip()
	except subprocess.CalledProcessError:
		print(f"Error: commit '{sha}' not found.")
		sys.exit(1)
	subject = git(["log", "-1", "--pretty=%s", resolved], cwd=repo).stdout.strip()
	files_raw = git(["diff-tree", "--no-commit-id", "--name-only", "-r", resolved], cwd=repo).stdout
	files = [f.strip() for f in files_raw.splitlines() if f.strip()]
	return CommitInfo(sha=resolved, subject=subject, files=files)


def get_latest_commit_info(repo: str, branch: str) -> CommitInfo:
	"""Convenience: latest commit on branch."""
	latest = git(["rev-parse", branch], cwd=repo).stdout.strip()
	return get_commit_info(repo, latest)


def prompt_confirm(commit: CommitInfo, main_branch: str, assume_yes: bool = False) -> None:
	"""Print commit details and ask for confirmation to continue."""
	print(f"Detected main branch: {main_branch}")
	print(f"Latest commit: {commit.sha} - {commit.subject}")
	print("Changed files:")
	for f in commit.files:
		print(f"  - {f}")
	if assume_yes:
		return
	ans = input("Continue to cherry-pick this commit into lesson branches? [y/N]: ").strip().lower()
	if ans not in ("y", "yes"):
		print("Aborted by user.")
		sys.exit(0)


LESSON_BRANCH_PATTERNS = [
	re.compile(r"^L\d{2}-teacher$"),
	re.compile(r"^L\d{2}-student-starter$"),
	re.compile(r"^L\d{2}-student-end$"),
]


def is_lesson_branch(name: str) -> bool:
	return any(p.match(name) for p in LESSON_BRANCH_PATTERNS)


def fetch_all(repo: str) -> None:
	print("Fetching remotes...")
	try:
		git(["fetch", "--all", "--prune"], cwd=repo)
	except subprocess.CalledProcessError as e:
		print("Warning: git fetch failed:", e.stderr.strip())


def list_branches(repo: str) -> Tuple[List[str], List[str]]:
	"""Return (local_branches, remote_branches)."""
	locals_raw = git(["branch", "--format", "%(refname:short)"], cwd=repo).stdout
	remotes_raw = git(["branch", "-r", "--format", "%(refname:short)"], cwd=repo).stdout
	local_branches = sorted({b.strip() for b in locals_raw.splitlines() if b.strip()})
	remote_branches = sorted({b.strip() for b in remotes_raw.splitlines() if b.strip()})
	return local_branches, remote_branches


def gather_lesson_branches(repo: str) -> List[str]:
	local_branches, remote_branches = list_branches(repo)
	lessons = set()
	for b in local_branches:
		if is_lesson_branch(b):
			lessons.add(b)
	for rb in remote_branches:
		# remote format: origin/Lxx-...
		if "/" in rb:
			_, short = rb.split("/", 1)
		else:
			short = rb
		if is_lesson_branch(short):
			lessons.add(short)
	return sorted(lessons)


def current_branch(repo: str) -> str:
	cp = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
	return cp.stdout.strip()


def branch_contains_commit(repo: str, branch: str, sha: str) -> bool:
	try:
		git(["merge-base", "--is-ancestor", sha, branch], cwd=repo)
		return True
	except subprocess.CalledProcessError:
		return False


def ensure_local_branch(repo: str, branch: str) -> None:
	"""Ensure the local branch exists; if not, try to create from origin/branch."""
	locals_raw = git(["branch", "--list", branch], cwd=repo).stdout.strip()
	if locals_raw:
		return
	# Create tracking branch if remote exists
	rem = f"origin/{branch}"
	rem_exists = git(["branch", "-r", "--list", rem], cwd=repo).stdout.strip()
	if rem_exists:
		print(f"Creating local tracking branch {branch} from {rem}...")
		git(["checkout", "-b", branch, "--track", rem], cwd=repo)
		# Go back to previous branch to keep flow consistent; caller will checkout as needed
		return
	else:
		print(f"Warning: branch {branch} not found locally or on origin; skipping.")


def checkout(repo: str, branch: str) -> None:
	git(["checkout", branch], cwd=repo)


def abort_cherry_pick(repo: str) -> None:
	try:
		git(["cherry-pick", "--abort"], cwd=repo)
	except subprocess.CalledProcessError:
		pass


def cherry_pick_into_branch(repo: str, branch: str, sha: str, *, main_wins: bool) -> Tuple[bool, Optional[str]]:
	"""Attempt cherry-pick into branch.

	Returns:
		(success, error_message)
		success=True & error_message=None  => applied (or already present)
		success=False & error_message=...  => failed / skipped
	"""
	print(f"\n==> Processing {branch}...")
	ensure_local_branch(repo, branch)

	# If still missing locally, skip
	locals_raw = git(["branch", "--list", branch], cwd=repo).stdout.strip()
	if not locals_raw:
		print(f"Skipping {branch}: no local or remote tracking branch found.")
		return False, "branch_missing"

	checkout(repo, branch)

	if branch_contains_commit(repo, branch, sha):
		print(f"Already contains {sha}; skipping.")
		return True, None

	print(f"Cherry-picking {sha} into {branch}...")
	cherry_args = ["cherry-pick"]
	if main_wins:
		# In the context of cherry-pick, "theirs" refers to the incoming commit (from main),
		# which is what we want to dominate conflicts.
		cherry_args.extend(["-X", "theirs"])
	cherry_args.extend(["-x", sha])
	try:
		git(cherry_args, cwd=repo)
		print("Cherry-pick succeeded.")
		return True, None
	except subprocess.CalledProcessError as e:
		err_msg = e.stderr.strip() or e.stdout.strip() or "unknown error"
		# Detect an empty cherry-pick (commit already applied effectively)
		if "cherry-pick is now empty" in err_msg.lower() or "previous cherry-pick is now empty" in err_msg.lower():
			# Skip it gracefully
			try:
				git(["cherry-pick", "--skip"], cwd=repo)
			except subprocess.CalledProcessError:
				# If skip fails just abort to restore cleanliness
				abort_cherry_pick(repo)
			print("Cherry-pick produced no changes (already applied). Marking as success.")
			return True, None
		# If main_wins was requested, attempt an aggressive auto-resolution by forcing commit version
		if main_wins:
			conflict_files_cp = git(["diff", "--name-only", "--diff-filter=U"], cwd=repo, check=False)
			conflict_files = [f.strip() for f in conflict_files_cp.stdout.splitlines() if f.strip()]
			if conflict_files:
				print(f"Attempting forced main-wins resolution on {len(conflict_files)} conflicted file(s)...")
				# For each conflicted file, check out the version from the incoming commit (sha)
				for fpath in conflict_files:
					try:
						git(["checkout", sha, "--", fpath], cwd=repo)
						git(["add", fpath], cwd=repo)
					except subprocess.CalledProcessError as ce:
						print(f"  Failed to force-resolve {fpath}: {(ce.stderr or ce.stdout).strip()}")
				# Try continuing
				try:
					git(["cherry-pick", "--continue"], cwd=repo)
					print("Cherry-pick succeeded after forced main-wins resolution.")
					return True, None
				except subprocess.CalledProcessError as ce2:
					print("Forced resolution failed; aborting cherry-pick.")
					abort_cherry_pick(repo)
					return False, err_msg + f" | forced-resolution-failed: {(ce2.stderr or ce2.stdout).strip()}"
		print("Cherry-pick failed. Aborting.")
		abort_cherry_pick(repo)
		print(f"Aborted cherry-pick due to: {err_msg}")
		return False, err_msg


def get_branch_remote(repo: str, branch: str) -> Tuple[Optional[str], bool]:
	"""Return (remote_name, has_upstream) for the given branch based on git config."""
	try:
		remote = git(["config", "--get", f"branch.{branch}.remote"], cwd=repo, check=False).stdout.strip()
	except subprocess.CalledProcessError:
		remote = ""
	has_upstream = bool(remote)
	if not remote:
		# Fallback to origin if present
		remotes = git(["remote"], cwd=repo, check=False).stdout.splitlines()
		remote = "origin" if "origin" in [r.strip() for r in remotes] else None
	return remote, has_upstream


def push_branch(repo: str, branch: str) -> Tuple[bool, Optional[str]]:
	"""Push branch to its upstream or origin; sets upstream if missing."""
	remote, has_upstream = get_branch_remote(repo, branch)
	if not remote:
		return False, "no-remote"
	args = ["push"]
	if not has_upstream:
		args.append("-u")
	args.extend([remote, f"{branch}:{branch}"])
	try:
		print(f"Pushing {branch} to {remote}...")
		git(args, cwd=repo)
		print(f"Pushed {branch}.")
		return True, None
	except subprocess.CalledProcessError as e:
		err = e.stderr.strip() or e.stdout.strip() or "unknown push error"
		print(f"Push failed for {branch}: {err}")
		return False, err


def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser(description="Cherry-pick a commit (default latest on main) into lesson branches.")
	p.add_argument("--commit", metavar="SHA", help="Specific commit SHA to cherry-pick (default: latest on main).")
	p.add_argument("--yes", action="store_true", help="Assume yes to confirmation prompt.")
	p.add_argument("--main-wins", action="store_true", help="Auto-resolve conflicts by taking main commit changes (git -X theirs).")
	p.add_argument("--only", nargs="*", metavar="BRANCH", help="Limit to specific lesson branches (names must match patterns).")
	return p.parse_args()


def main() -> None:
	args = parse_args()
	repo = ensure_repo_root()
	os.chdir(repo)
	ensure_clean_worktree(repo)

	# Remember original branch to restore later
	orig_branch = current_branch(repo)

	# Detect main branch (even if a specific commit is passed we still fetch & ensure up-to-date refs)
	main_branch = detect_main_branch(repo)
	print(f"Checking out {main_branch} for reference & fetch...")
	checkout(repo, main_branch)
	fetch_all(repo)

	# Determine target commit
	if args.commit:
		commit = get_commit_info(repo, args.commit)
		print(f"Using specified commit: {commit.sha}")
	else:
		commit = get_latest_commit_info(repo, main_branch)
		print(f"Using latest commit on {main_branch}: {commit.sha}")
	prompt_confirm(commit, main_branch, assume_yes=args.yes)

	# Gather lesson branches
	lessons = gather_lesson_branches(repo)
	if args.only:
		requested = set(args.only)
		lessons = [b for b in lessons if b in requested]
	if not lessons:
		print("No lesson branches found. Nothing to do.")
		checkout(repo, orig_branch)
		return

	print("\nBranches to update:")
	for b in lessons:
		print(f" - {b}")

	# Process each branch
	successes: List[str] = []
	skipped: List[str] = []
	failures: List[Tuple[str, str]] = []
	push_failures: List[Tuple[str, str]] = []

	for b in lessons:
		ok, err = cherry_pick_into_branch(repo, b, commit.sha, main_wins=args.main_wins)
		if ok and err is None:
			successes.append(b)
			pok, perr = push_branch(repo, b)
			if not pok and perr:
				push_failures.append((b, perr))
		elif err == "branch_missing":
			skipped.append(b)
		elif ok:  # already contained (this branch isn't used because err is None when ok)
			skipped.append(b)
			pok, perr = push_branch(repo, b)
			if not pok and perr:
				push_failures.append((b, perr))
		else:
			failures.append((b, err))

	# Restore original branch
	print(f"\nRestoring original branch: {orig_branch}")
	checkout(repo, orig_branch)

	# Summary
	print("\nSummary:")
	print(f"  Successful: {len(successes)}")
	for b in successes:
		print(f"    - {b}")
	print(f"  Skipped: {len(skipped)}")
	for b in skipped:
		print(f"    - {b}")
	print(f"  Failed: {len(failures)}")
	for b, err in failures:
		print(f"    - {b}: {err}")
	if push_failures:
		print(f"  Push failures: {len(push_failures)}")
		for b, err in push_failures:
			print(f"    - {b}: {err}")


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print("\nInterrupted.")
		sys.exit(130)
