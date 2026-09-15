# -*- coding: utf-8 -*-
"""
投资实证工作台 · 选股数据刷新脚本
--------------------------------------------------
作用：抓取 A 股全市场基本面数据，生成 stocks_data.js 供工作台读取。
原理：东财 clist 拿全市场快照 -> 腾讯行情批量补 PE(TTM) -> ROE = PB / PE(TTM)

用法：双击同目录下的「刷新选股数据.bat」，或在命令行运行 python refresh_stocks.py
说明：财报数据一个季度才变一次，所以每季度跑一次即可，不用天天刷。
      纯 Python 标准库实现，无需 pip install 任何东西。
"""
import json
import os
import sys
import time
import urllib.request
import datetime
from concurrent.futures import ThreadPoolExecutor

MAX_WORKERS = 8        # 并发线程数：56 页顺序抓取要 4 分钟，并发后 30 秒内完成

# ---------------------------------------------------------------- 配置
MIN_MKTCAP_YI = 20.0     # 只保留总市值 >= 20 亿的股票（过滤微盘股与壳股）
BATCH_QQ = 60            # 腾讯行情每批请求股票数
OUT_FILE = "stocks_data.js"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "*/*",
}
EM_FIELDS = "f12,f14,f2,f3,f9,f23,f100,f20,f21,f162,f167,f184,f185,f187,f188,f45,f105,f113"
EM_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"   # 沪深主板 + 创业板 + 科创板


def log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("gbk", "ignore").decode("gbk", "ignore"), flush=True)


def fetch(url, retries=4, timeout=30, encoding="utf-8"):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode(encoding, "ignore")
        except Exception as e:
            last = e
            time.sleep(0.4 * (i + 1))
    raise last


def fetch_json(url, retries=4, timeout=30):
    return json.loads(fetch(url, retries, timeout))


# ---------------------------------------------------------------- 1. 东财全市场
def em_page(page):
    url = ("https://push2.eastmoney.com/api/qt/clist/get"
           "?pn={}&pz=100&po=1&np=1&fltt=2&invt=2&fid=f12"
           "&fs={}&fields={}").format(page, EM_FS, EM_FIELDS)
    return fetch_json(url, retries=6, timeout=35)


def pull_eastmoney():
    log("[1/5] 正在从东方财富抓取全市场快照 ...")
    probe = em_page(1)
    if not probe or not probe.get("data"):
        log("  首页抓取失败，请检查网络。")
        return []
    total = probe["data"]["total"]
    pages = (total + 99) // 100
    log("  全市场共 {} 只，分 {} 页，{} 线程并发".format(total, pages, MAX_WORKERS))
    stocks = list(probe["data"]["diff"])

    def one(page):
        try:
            d = em_page(page)
            if d and d.get("data") and d.get("data").get("diff"):
                return d["data"]["diff"]
        except Exception:
            pass
        return []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for rows in ex.map(one, range(2, pages + 1)):
            stocks.extend(rows)

    got = len({r.get("f12") for r in stocks if r.get("f12")})
    if got < total:
        log("  拿到 {} / {} 只，正在补抓缺失页 ...".format(got, total))
        have = {r.get("f12") for r in stocks if r.get("f12")}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            for rows in ex.map(one, range(1, pages + 1)):
                for r in rows:
                    c = r.get("f12")
                    if c and c not in have:
                        have.add(c)
                        stocks.append(r)

    # 按代码去重
    seen, uniq = set(), []
    for r in stocks:
        c = r.get("f12")
        if c and c not in seen:
            seen.add(c)
            uniq.append(r)
    log("  拿到 {} 条唯一记录 / 全市场 {}".format(len(uniq), total))
    return uniq


def pull_hs300_history(start_date="2015-01-01"):
    """抓取沪深300 收盘历史，用于收益对照曲线"""
    log("[4/5] 抓取沪深300 历史收盘（对照曲线用）...")
    for secid, tag in (("1.000300", "沪深300"), ("1.H00300", "沪深300全收益")):
        url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
               "?secid={}&fields1=f1,f2,f3&fields2=f51,f53&klt=101&fqt=0"
               "&beg={}&end=20500101&lmt=100000").format(secid, start_date.replace("-", ""))
        try:
            d = fetch_json(url, retries=4, timeout=40)
        except Exception:
            continue
        kl = (d.get("data") or {}).get("klines") if d else None
        if not kl:
            continue
        out = []
        for line in kl:
            p = line.split(",")
            if len(p) >= 2:
                out.append([p[0], round(float(p[1]), 2)])
        if len(out) > 100:
            log("  {}：{} 个交易日，{} ~ {}".format(tag, len(out), out[0][0], out[-1][0]))
            return tag, out
    log("  未拿到沪深300 历史，对照曲线将不可用。")
    return None, []


def num(v, scale=1.0, default=None):
    """东财 '-' 表示无数据"""
    try:
        if v is None or v == "-" or v == "":
            return default
        return float(v) / scale
    except Exception:
        return default


# ---------------------------------------------------------------- 2. 腾讯补 PE(TTM)
def qq_code(code):
    if code.startswith(("60", "68", "11", "5")):
        return "sh" + code
    if code.startswith(("00", "30", "12", "1")):
        return "sz" + code
    return "sh" + code


def pull_qq_pe(codes):
    """返回 {code: (pe_ttm, pb, price)}，并发抓取"""
    chunks = [codes[i:i + BATCH_QQ] for i in range(0, len(codes), BATCH_QQ)]

    def one(chunk):
        res = {}
        url = "https://qt.gtimg.cn/q=" + ",".join(qq_code(c) for c in chunk)
        try:
            txt = fetch(url, retries=3, timeout=25, encoding="gbk")
        except Exception:
            return res
        for seg in txt.split(";"):
            seg = seg.strip()
            if not seg.startswith("v_"):
                continue
            try:
                head, body = seg.split("=", 1)
                code = head.replace("v_", "").strip()[2:]
                f = body.strip().strip('"').split("~")
                if len(f) < 47:
                    continue
                res[code] = (num(f[39]), num(f[46]), num(f[3]))
            except Exception:
                continue
        return res

    out = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for res in ex.map(one, chunks):
            out.update(res)
    return out


# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    raw = pull_eastmoney()
    if not raw:
        log("抓取失败，请检查网络后重试。")
        return 1

    log("[2/5] 清洗与过滤（总市值 >= {} 亿）...".format(MIN_MKTCAP_YI))
    items = []
    for r in raw:
        code = r.get("f12") or ""
        name = (r.get("f14") or "").strip()
        if not code or not name:
            continue
        if "ST" in name.upper() or "退" in name:
            continue
        mc = num(r.get("f20"), 1e8)          # 总市值（亿元）
        if mc is None or mc < MIN_MKTCAP_YI:
            continue
        pe_dyn = num(r.get("f162"), 100) or num(r.get("f9"), 100)
        pb = num(r.get("f167"), 100) or num(r.get("f23"), 100)
        fc = num(r.get("f21"), 1e8)
        items.append({
            "c": code,
            "n": name.replace(" ", ""),
            "p": num(r.get("f2")),
            "pe": pe_dyn,
            "pb": pb,
            "mc": round(mc, 1) if mc else None,
            "fc": round(fc, 1) if fc else None,
            "rv": num(r.get("f184")),        # 营收同比 %
            "ni": num(r.get("f185")),        # 净利同比 %
            "nm": num(r.get("f187")),        # 净利率 %
            "dr": num(r.get("f188")),        # 资产负债率 %
            "np": num(r.get("f45")),         # 净利润（元）
            "ind": r.get("f100") or "",
        })
    log("  过滤后剩 {} 只".format(len(items)))

    # 只对 PE>0（盈利）的股票补 TTM PE，省请求
    need = [it["c"] for it in items if (it.get("pe") or 0) > 0]
    log("[3/5] 用腾讯行情补齐 PE(TTM)，共 {} 只，分 {} 批 ...".format(
        len(need), (len(need) + BATCH_QQ - 1) // BATCH_QQ))
    qq = pull_qq_pe(need)

    log("[4/5] 计算 ROE 与市场温度指标 ...")
    hit = 0
    for it in items:
        pe_ttm, pb_qq, _ = qq.get(it["c"], (None, None, None))
        pb = pb_qq if pb_qq else it.get("pb")
        it["pb"] = round(pb, 2) if pb else None
        if pe_ttm and pe_ttm > 0:
            it["pe"] = round(pe_ttm, 2)
            hit += 1
        roe = None
        if it.get("pe") and it.get("pb") and it["pe"] > 0:
            roe = it["pb"] / it["pe"] * 100.0
        it["roe"] = round(roe, 2) if roe is not None else None
        if pb_qq and pb_qq > 0:
            pass
    log("  PE(TTM) 补齐 {} 只".format(hit))

    # 市场温度原始指标（横截面，不需要历史数据）
    pes = sorted([it["pe"] for it in items if it.get("pe") and 0 < it["pe"] < 300])
    pbs = sorted([it["pb"] for it in items if it.get("pb") and 0 < it["pb"] < 50])
    tot_pb = len([it for it in items if it.get("pb")])
    broken = len([it for it in items if it.get("pb") and 0 < it["pb"] < 1])

    def med(a):
        n = len(a)
        if not n:
            return None
        return round(a[n // 2], 2) if n % 2 else round((a[n // 2 - 1] + a[n // 2]) / 2, 2)

    market = {
        "date": datetime.date.today().strftime("%Y-%m-%d"),
        "count": len(items),
        "pe_median": med(pes),
        "pb_median": med(pbs),
        "broken_ratio": round(broken * 100.0 / tot_pb, 2) if tot_pb else None,
        "pe_p25": round(pes[len(pes) // 4], 2) if pes else None,
        "pe_p75": round(pes[len(pes) * 3 // 4], 2) if pes else None,
        "profitable_ratio": round(len(pes) * 100.0 / len(items), 2) if items else None,
    }
    log("  市场指标：PE中位数 {} / PB中位数 {} / 破净率 {}%".format(
        market["pe_median"], market["pb_median"], market["broken_ratio"]))

    bench_tag, bench = pull_hs300_history()
    log("[5/5] 写入文件 ...")

    payload = {"updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
               "market": market, "stocks": items,
               "benchName": bench_tag, "bench": bench}
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUT_FILE)
    js = "window.__STOCKS_DATA__ = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(js)

    size_kb = os.path.getsize(out_path) / 1024.0
    log("")
    log("完成！已写入 {}".format(OUT_FILE))
    log("  股票 {} 只 / 对照 {} 个交易日，文件 {:.0f} KB，耗时 {:.1f} 秒".format(
        len(items), len(bench), size_kb, time.time() - t0))
    log("  数据截至：{}".format(payload["updated"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log("出错了：{}".format(e))
        import traceback
        traceback.print_exc()
        time.sleep(3)
        sys.exit(1)
