@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 投资实证工作台 - 刷新选股数据
echo.
echo   ┌────────────────────────────────────────┐
echo   │   投资实证工作台 · 选股数据刷新         │
echo   └────────────────────────────────────────┘
echo.
echo   正在抓取 A 股全市场数据，大约需要 10-30 秒。
echo   （财报数据一个季度才变一次，不用天天刷）
echo.

set "PY="

if exist "C:\Users\yyshe\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
  set "PY=C:\Users\yyshe\.workbuddy\binaries\python\versions\3.13.12\python.exe"
  goto :run
)

py -3 -c "print(1)" >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
  goto :run
)

python -c "print(1)" >nul 2>nul
if %errorlevel%==0 (
  set "PY=python"
  goto :run
)

echo   [!] 没有找到 Python。
echo.
echo   请先安装 Python 3：https://www.python.org/downloads/
echo   安装时务必勾选 "Add Python to PATH"。
echo.
pause
exit /b 1

:run
echo   使用解释器：%PY%
echo.
%PY% refresh_stocks.py
if %errorlevel% neq 0 (
  echo.
  echo   [!] 抓取失败，请检查网络连接后重试。
)

echo.
echo   ────────────────────────────────────────
echo   完成后回到工作台刷新页面即可看到新数据。
echo.
pause
