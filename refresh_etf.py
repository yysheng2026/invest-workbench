# -*- coding: utf-8 -*-
"""refresh_etf.py —— 抓全市场场内 ETF + 实时溢价率，生成 etf_data.js

套路和 refresh_stocks.py 一样：生成 window.__ETF_DATA__，用 <script src> 加载，
所以双击 HTML（file://）离线也能读到，不依赖联网。

数据源（两个都实测可用）
  1) 天天基金 fundcode_search.js —— 全量基金清单（静态 JS，最稳）
     筛出真正的「场内 ETF」：代码 5x(沪)/1x(深) + 名称含 ETF + 排除「联接」(场外)
  2) 腾讯 qt.gtimg.cn —— 每只 ETF 的 现价/涨跌幅/成交额/规模/净值(IOPV)/溢价率
     ⚠️ 字段位置（88 个字段，split('~')），已逐项实测校验：
        [1]名称 [3]现价 [32]涨跌幅 [35]"价/量/额" [37]成交额(万元)
        [72]规模(元) [77]溢价率% [78]净值/IOPV
     校验方式：溢价率 与「现价 ÷ 净值 − 1」完全吻合
       （纳指ETF国泰 513100：2.196 / 1.9654 → +11.73%，与字段 [77] 一致）

⚠️ 为什么不用东财 clist：那个接口对高频请求会 RemoteDisconnected（限流），
   上面的组合更稳。费率 / 跟踪误差 / 跟踪指数 免费接口拿不到，需在基金公司页面自查。

用法： python refresh_etf.py
输出： 同目录 etf_data.js
"""
import io
import json
import os
import re
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etf_data.js")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"


def http(url, ref="https://gu.qq.com/", decode="utf-8", retry=3):
    last = None
    for _ in range(retry):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", UA)
            req.add_header("Referer", ref)
            with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
                return r.read().decode(decode, "replace")
        except Exception as e:
            last = e
            time.sleep(0.8)
    raise last


# ---------------- 分类：别把 ETF 和「宽基」划等号 ----------------
OV_KW = ["纳指", "纳斯达克", "标普", "道琼斯", "日经", "德国", "法国", "亚太", "中概",
         "海外", "美国", "日本", "东南亚", "沙特", "巴西", "恒生", "港股", "HK",
         "中韩", "全球", "越南", "印度"]
CMD_KW = ["黄金", "豆粕", "原油", "白银", "商品", "有色期货", "能源化工", "铁矿石"]
BOND_KW = ["国债", "政金", "地方政府债", "城投债", "可转债", "短融", "债"]
MON_KW = ["货币", "现金添利", "保证金", "银华日利", "华宝添益"]
BROAD_KW = ["沪深300", "中证500", "中证800", "中证1000", "中证2000", "中证A500",
            "中证A50", "中证100", "上证50", "上证180", "上证380", "科创50", "科创100",
            "科创综指", "创业板", "深证100", "深证50", "中证全指", "国证2000",
            "MSCI", "富时", "罗素", "综指", "中小盘", "A50", "双创"]
STRAT_KW = ["红利", "低波", "价值", "成长", "基本面", "质量", "等权", "ESG",
            "自由现金流", "央视50", "治理", "动量", "高股息", "股息"]


def classify(name):
    n = name or ""
    for kw in OV_KW:
        if kw in n:
            return "overseas"
    for kw in CMD_KW:
        if kw in n:
            return "commodity"
    for kw in MON_KW:
        if kw in n:
            return "money"
    for kw in BOND_KW:
        if kw in n:
            return "bond"
    for kw in BROAD_KW:
        if kw in n:
            return "broad"
    for kw in STRAT_KW:
        if kw in n:
            return "strategy"
    return "sector"


def mkt(code):
    """ETF 代码 → 交易所前缀（沪市 5x / 深市 1x）"""
    c = str(code)
    return ("sh" + c) if c.startswith("5") else (("sz" + c) if c.startswith("1") else None)


def fnum(s):
    try:
        v = float(s)
        return v if v == v and v != float("inf") else None
    except Exception:
        return None


# ---------------- 1) 天天基金：筛出真正的场内 ETF ----------------
def fetch_universe():
    txt = http("https://fund.eastmoney.com/js/fundcode_search.js",
               ref="https://fund.eastmoney.com/")
    arr = json.loads(txt[txt.index("["):txt.rindex("]") + 1])
    out, seen = [], set()
    for a in arr:
        if len(a) < 3:
            continue
        code, name = str(a[0]), a[2]
        if not code or not name:
            continue
        if code[0] not in ("1", "5"):      # 场内 ETF 只有 5x(沪) / 1x(深)
            continue
        if "ETF" not in name:
            continue
        if "联接" in name:                  # 排除场外联接基金
            continue
        if code in seen:
            continue
        seen.add(code)
        out.append({"c": code, "n": name})
    return out


# ---------------- 2) 腾讯批量补行情 / 规模 / 溢价 ----------------
def enrich(etfs, batch=60):
    todo = list(dict.fromkeys([mkt(e["c"]) for e in etfs if mkt(e["c"])]))

    def one(codes):
        try:
            # ⚠️ 腾讯响应是 GBK，必须指定，否则中文名乱码 → 分类全部失效
            txt = http("https://qt.gtimg.cn/q=" + ",".join(codes), decode="gbk")
        except Exception:
            return {}
        res = {}
        for m in re.finditer(r'v_([a-z]{2}\d{6})="(.*?)";', txt, re.S):
            key = m.group(1)
            f = m.group(2).split("~")
            if len(f) < 79:
                continue
            amt = fnum(f[37])                # 成交额（万元）
            share = fnum(f[72])              # ⚠️ [72] 是「份额」，不是规模
            iopv = fnum(f[78])
            # 规模 = 份额 × 净值（自检：510300 约千亿级，与已知规模吻合）
            size = (share * iopv) if (share is not None and iopv) else None
            res[key[2:]] = {
                "n": f[1] or None,
                "p": fnum(f[3]),
                "chg": fnum(f[32]),
                "amt": (amt * 10000.0) if amt is not None else None,
                "sh": share,
                "size": size,
                "prem": fnum(f[77]),
                "iopv": iopv,
            }
        return res

    chunks = [todo[i:i + batch] for i in range(0, len(todo), batch)]
    allp = {}
    with ThreadPoolExecutor(6) as ex:
        for r in ex.map(one, chunks):
            allp.update(r)
    n = 0
    keep = []
    for e in etfs:
        g = allp.get(e["c"])
        if not g or g.get("p") is None:
            continue                        # 拿不到行情的（停牌/退市）不写进数据
        e["n"] = g["n"] or e["n"]
        e["p"] = g["p"]
        e["chg"] = g["chg"]
        e["amt"] = g["amt"]
        e["sh"] = g["sh"]
        e["size"] = g["size"]
        e["prem"] = g["prem"]
        e["iopv"] = g["iopv"]
        e["cat"] = classify(e["n"])
        keep.append(e)
        if g["prem"] is not None:
            n += 1
    return keep, n


def main():
    print("① 取全量基金清单，筛出真正的场内 ETF（天天基金）…")
    uni = fetch_universe()
    print("   场内 ETF %d 只" % len(uni))
    print("② 补行情 / 规模 / 净值 / 溢价率（腾讯，字段 [72][77][78]）…")
    etfs, n = enrich(uni)
    print("   拿到行情 %d 只，其中溢价率 %d 只" % (len(etfs), n))

    # 自检：沪深300ETF 规模口径（已知是大块头，若是个位数亿元说明字段取错了）
    chk = [e for e in etfs if e["c"] == "510300"]
    if chk and chk[0].get("size"):
        print("   自检 510300 规模 = %.1f 亿元" % (chk[0]["size"] / 1e8))

    cats = {}
    for e in etfs:
        cats[e["cat"]] = cats.get(e["cat"], 0) + 1
    print("   分类：", cats)

    data = {"updated": time.strftime("%Y-%m-%d %H:%M"), "total": len(etfs), "etfs": etfs}
    io.open(OUT, "w", encoding="utf-8").write(
        "window.__ETF_DATA__=" + json.dumps(data, ensure_ascii=False) + ";\n")
    print("✅ 已写出 %s（%.0f KB）" % (OUT, os.path.getsize(OUT) / 1024.0))

    hi = sorted([e for e in etfs if (e.get("prem") or 0) >= 5],
                key=lambda x: -(x["prem"] or 0))
    if hi:
        print("\n⚠️ 溢价 ≥5%% 的有 %d 只（前 10）：" % len(hi))
        for e in hi[:10]:
            print("   %s %-22s 溢价 %+.2f%%" % (e["c"], e["n"], e["prem"]))


if __name__ == "__main__":
    main()
