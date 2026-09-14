# 投资实证工作台

孟岩式投资实证记录工具：规划 / 资产 / 持仓 / 选股 / 日志 / 市场温度 / 股息日历。

- 单文件 HTML，无构建、无依赖
- 数据存在本机（localStorage / data\save.json），不上传服务器
- PWA：可装到手机主屏与电脑桌面，断网可用
- 行情来自腾讯 / 东方财富公开接口

## 部署

源目录：`D:\OneDrive-SYY\OneDrive\【我的工作台】\投资实证工作台`
部署目录：`D:\invest-workbench-site`（本目录）

Cloudflare Pages：Framework 预设 `None`，构建命令留空，输出目录 `/`。

以后改完源码，跑一次 `D:\OneDrive-SYY\OneDrive\【我的工作台】\投资实证工作台\发布更新.sh`
（或手动复制 + commit + push），Cloudflare 会自动重新部署。

## 文件

| 文件 | 说明 |
|---|---|
| `index.html` | 线上入口（= 投资实证工作台.html 的副本） |
| `投资实证工作台.html` | 同一份，供下载离线用 |
| `sw.js` | 离线缓存，改版本时记得 bump `CACHE` 与 index.html 里的 `sw.js?v=N` |
| `stocks_data.js` | 全市场选股数据，由 `刷新选股数据.bat` 重新抓取 |
| `安装到手机.html` | 装到主屏的步骤说明 |
| `启动投资实证.py` / `投资实证工作台.bat` | 可选：本地文件版启动器 |
