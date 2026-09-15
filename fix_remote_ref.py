# -*- coding: utf-8 -*-
"""重建本地的远端跟踪分支 refs/remotes/origin/master。

为什么会丢：在某些受限/沙箱环境里，git 往 .git/refs/remotes/ 写新文件会被
静默丢弃（git 自己报成功，但文件没落盘）。结果是 `git status -sb` 显示
`## master...origin/master [gone]`，GitHub Desktop 也会显示异常状态。

用法：  python fix_remote_ref.py [目录]     默认 D:\invest-workbench-site
"""
import os
import subprocess
import sys

DEFAULT = r"D:\invest-workbench-site"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", repo] + list(args), text=True).strip()


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    sha = git(repo, "rev-parse", "HEAD")
    ref_dir = os.path.join(repo, ".git", "refs", "remotes", "origin")
    os.makedirs(ref_dir, exist_ok=True)
    with open(os.path.join(ref_dir, branch), "w", newline="") as f:
        f.write(sha + "\n")
    print("refs/remotes/origin/%s -> %s" % (branch, sha[:7]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
