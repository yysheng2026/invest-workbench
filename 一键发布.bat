@echo off
rem ============================================================================
rem  一键发布.bat —— 投资实证工作台 部署到 GitHub（Cloudflare Pages 自动跟进）
rem
rem  做了什么：
rem    1. 把源目录的最新文件复制到 D:\invest-workbench-site
rem    2. 自动把离线缓存版本 sw vN 升一档（否则手机上的 PWA 会卡在旧版）
rem    3. git commit + push 到 yysheng2026/invest-workbench 的 master 分支
rem
rem  push 若被网络/代理拦住，会自动改用 GitHub API 兜底推送。
rem ============================================================================

set "SRC=D:\OneDrive-SYY\OneDrive\【我的工作台】\投资实证工作台"
set "DEPLOY=D:\invest-workbench-site"
set "PY=C:\Users\yyshe\.workbuddy\binaries\python\versions\3.13.12\python.exe"

echo.
echo  [1/3] 复制文件到部署目录 ...
copy /Y "%SRC%\投资实证工作台.html" "%DEPLOY%\index.html" >nul
copy /Y "%SRC%\投资实证工作台.html" "%DEPLOY%\投资实证工作台.html" >nul
copy /Y "%SRC%\sw.js"                 "%DEPLOY%\sw.js" >nul
copy /Y "%SRC%\manifest.webmanifest"  "%DEPLOY%\manifest.webmanifest" >nul
copy /Y "%SRC%\安装到手机.html"        "%DEPLOY%\安装到手机.html" >nul
copy /Y "%SRC%\apple-touch-icon.png"  "%DEPLOY%\apple-touch-icon.png" >nul
copy /Y "%SRC%\icon-512.png"          "%DEPLOY%\icon-512.png" >nul
copy /Y "%SRC%\stocks_data.js"        "%DEPLOY%\stocks_data.js" >nul
copy /Y "%SRC%\etf_data.js"           "%DEPLOY%\etf_data.js" >nul
copy /Y "%SRC%\refresh_stocks.py"     "%DEPLOY%\refresh_stocks.py" >nul
copy /Y "%SRC%\refresh_etf.py"        "%DEPLOY%\refresh_etf.py" >nul
copy /Y "%SRC%\刷新选股数据.bat"        "%DEPLOY%\刷新选股数据.bat" >nul
copy /Y "%SRC%\刷新ETF数据.bat"         "%DEPLOY%\刷新ETF数据.bat" >nul
copy /Y "%SRC%\启动投资实证.py"         "%DEPLOY%\启动投资实证.py" >nul
copy /Y "%SRC%\投资实证工作台.bat"       "%DEPLOY%\投资实证工作台.bat" >nul
echo        完成

echo.
echo  [2/3] 升离线缓存版本 ...
"%PY%" "%SRC%\bump_sw.py"
if errorlevel 1 (
  echo        升版本失败，已中止
  pause
  exit /b 1
)

echo.
echo  [3/3] 提交并推送 ...
pushd "%DEPLOY%"
git add -A
git diff --cached --quiet
if %errorlevel%==0 (
  echo        没有变化，已跳过推送
) else (
  git commit -m "deploy: %date% %time%" -q
  git push origin master
  if errorlevel 1 (
    echo        git push 被拦，改用 GitHub API 兜底 ...
    "%PY%" "%SRC%\推送到GitHub.py"
  ) else (
    echo        git push 成功
  )
)
popd

echo.
echo  [4/4] 重建本地远端分支引用（避免 GitHub Desktop 显示 gone）...
"%PY%" "%SRC%ix_remote_ref.py"

echo.
echo  完成。线上地址： https://invest-workbench.pages.dev/
echo  （手机上若还是旧版，删掉主屏图标重装一次即可）
echo.
pause
