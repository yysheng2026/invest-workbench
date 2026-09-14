#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投资实证工作台 · 桌面版启动器
------------------------------------------------
把工作台以「独立应用窗口」打开（无浏览器地址栏/标签栏），数据存在本机文件里，
完全离线可用（行情、选股数据读本地缓存，联网时才刷新）。

用法：双击「投资实证工作台.bat」，或直接 python 启动投资实证.py
"""
import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
os.makedirs(DATA_DIR, exist_ok=True)
PORT_FILE = os.path.join(DATA_DIR, "port.txt")


# ---------- 找一个空闲端口 ----------
def free_port(prefer=8765):
    for p in [prefer] + list(range(8766, 8866)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", p))
                return p
        except OSError:
            continue
    raise RuntimeError("找不到空闲端口")


class Handler(http.server.SimpleHTTPRequestHandler):
    """静态文件服务 + 数据读写接口（数据存 data/save.json，不依赖浏览器缓存）"""

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def log_message(self, *a):
        pass  # 安静模式

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/load"):
            f = os.path.join(DATA_DIR, "save.json")
            if os.path.exists(f):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        return self._json(json.load(fp))
                except Exception as e:
                    return self._json({"error": str(e)}, 500)
            return self._json({"empty": True})
        if self.path.startswith("/api/ping"):
            return self._json({"ok": True, "dir": DATA_DIR})
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/save"):
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n)
            try:
                obj = json.loads(raw.decode("utf-8"))
            except Exception as e:
                return self._json({"error": "bad json: %s" % e}, 400)
            f = os.path.join(DATA_DIR, "save.json")
            # 原子写：先写临时文件再替换，避免断电/崩溃写坏
            tmp = f + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fp:
                json.dump(obj, fp, ensure_ascii=False, indent=1)
            os.replace(tmp, f)
            # 顺手留一份带日期的备份，最多保留 30 份
            try:
                stamp = time.strftime("%Y%m%d")
                bak = os.path.join(DATA_DIR, "backup_%s.json" % stamp)
                if not os.path.exists(bak):
                    with open(bak, "w", encoding="utf-8") as fp:
                        json.dump(obj, fp, ensure_ascii=False, indent=1)
                baks = sorted([x for x in os.listdir(DATA_DIR)
                               if x.startswith("backup_") and x.endswith(".json")])
                for old in baks[:-30]:
                    os.remove(os.path.join(DATA_DIR, old))
            except Exception:
                pass
            return self._json({"ok": True, "saved": len(raw)})
        return self._json({"error": "not found"}, 404)


def find_browser():
    """优先 Edge（Windows 必装），其次 Chrome"""
    cands = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def main():
    port = free_port()
    with open(PORT_FILE, "w", encoding="utf-8") as fp:
        fp.write(str(port))

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    url = "http://127.0.0.1:%d/index.html" % port
    profile = os.path.join(DATA_DIR, "browser_profile")
    os.makedirs(profile, exist_ok=True)

    exe = find_browser()
    if exe:
        cmd = [exe, "--app=" + url,
               "--user-data-dir=" + profile,
               "--no-first-run", "--no-default-browser-check",
               "--window-size=1280,900"]
        try:
            subprocess.Popen(cmd)
        except Exception:
            webbrowser.open(url)
    else:
        webbrowser.open(url)

    print("投资实证工作台已启动：%s" % url)
    print("数据目录：%s" % DATA_DIR)
    print("关掉应用窗口后，回到这个黑窗口按 Ctrl+C 可完全退出。")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
