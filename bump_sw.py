# -*- coding: utf-8 -*-
"""把离线缓存（Service Worker）版本号升一档。

为什么必须做：Chrome 对「同一个 sw.js URL」的更新检查有约 24 小时节流，
已装到手机主屏的 PWA 会一直卡在旧版本。把注册 URL 改成 sw.js?v=N+1
（缓存名同步改成 invest-vN+1），浏览器就会立刻去拉新文件。

用法：  python bump_sw.py            # 自动 +1
        python bump_sw.py 12         # 直接指定版本号
"""
import io
import os
import re
import sys

SRC = r"D:\OneDrive-SYY\OneDrive\【我的工作台】\投资实证工作台"
DEPLOY = r"D:\invest-workbench-site"

CACHE_RE = re.compile(rb"invest-v(\d+)")
URL_RE = re.compile(rb"sw\.js\?v=(\d+)")


def read(p):
    with open(p, "rb") as f:
        return f.read()


def write(p, b):
    with open(p, "wb") as f:
        f.write(b)


def main():
    sw_path = os.path.join(DEPLOY, "sw.js")
    sw = read(sw_path)

    m = CACHE_RE.search(sw)
    if not m:
        print("未在 sw.js 中找到 invest-vN，放弃")
        return 1

    cur = int(m.group(1))
    nxt = int(sys.argv[1]) if len(sys.argv) > 1 else cur + 1
    if nxt == cur:
        print("版本未变化：invest-v%d" % cur)
        return 0

    new_sw = CACHE_RE.sub(("invest-v%d" % nxt).encode(), sw)
    write(sw_path, new_sw)

    for d in (DEPLOY, SRC):
        for name in ("index.html", "投资实证工作台.html"):
            p = os.path.join(d, name)
            if not os.path.exists(p):
                continue
            b = read(p)
            if URL_RE.search(b):
                write(p, URL_RE.sub(("sw.js?v=%d" % nxt).encode(), b))
            else:
                print("  警告：%s 里没找到 sw.js?v=N" % name)

    # 源目录的 sw.js 与部署目录保持同一版本
    write(os.path.join(SRC, "sw.js"), new_sw)
    # 源目录的 index.html 是本地直接打开用的，同步成最新
    src_html = os.path.join(SRC, "投资实证工作台.html")
    if os.path.exists(src_html):
        write(os.path.join(SRC, "index.html"), read(src_html))

    print("SW 版本：invest-v%d -> invest-v%d（注册 URL 已同步）" % (cur, nxt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
