@echo off
chcp 65001 >nul
title 投资实证工作台
cd /d "%~dp0"

set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" where py >nul 2>nul && set PY=py

rem 本机 managed python（WorkBuddy 自带）
if "%PY%"=="" if exist "C:\Users\%USERNAME%\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
  set PY=C:\Users\%USERNAME%\.workbuddy\binaries\python\versions\3.13.12\python.exe
)

if "%PY%"=="" (
  echo.
  echo   没有找到 Python。
  echo.
  echo   两个办法：
  echo   1^) 直接双击「投资实证工作台.html」，也能用（数据存在浏览器里）；
  echo   2^) 装一个 Python 后重新双击本文件。
  echo.
  pause
  exit /b 1
)

echo 正在启动投资实证工作台...
"%PY%" "%~dp0启动投资实证.py"
if errorlevel 1 pause
