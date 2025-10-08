@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem 使用 UTF-8，中文訊息較不易亂碼（可依你環境調整）
chcp 65001 >nul

rem 讓工作目錄切到這個 bat 檔所在資料夾
cd /d "%~dp0"

echo ==========================================================
echo   Git Sync - 一鍵提交、更新並推送到 GitHub
echo   目前資料夾：%CD%
echo ==========================================================

rem 檢查是否已安裝 Git
where git >nul 2>&1
if errorlevel 1 (
  echo [錯誤] 找不到 git，請先安裝 Git for Windows 再重試。
  pause
  exit /b 1
)

rem 檢查是否為 Git 專案
if not exist ".git" (
  echo [錯誤] 這個資料夾不是 Git 專案：缺少 .git 目錄
  pause
  exit /b 1
)

rem 取得目前分支名稱
for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD') do set CURRENT_BRANCH=%%i

if "%CURRENT_BRANCH%"=="" (
  echo [錯誤] 無法取得目前分支（可能是 detached HEAD）
  pause
  exit /b 1
)

rem 檢查是否有設定 origin 遠端
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo [錯誤] 尚未設定遠端 'origin'。
  echo 建議先執行：
  echo   git remote add origin https://github.com/<你的帳號>/<repo>.git
  pause
  exit /b 1
)

echo 目前分支：%CURRENT_BRANCH%
echo.

set /p COMMIT_MSG=請輸入此次提交的 commit 訊息（直接 Enter 會使用預設 "update"）： 
if "%COMMIT_MSG%"=="" set COMMIT_MSG=update

echo.
echo [1/4] 追蹤並加入所有變更...
git add -A

echo [2/4] 提交變更（若無變更會略過）...
git diff --cached --quiet && (
  echo 沒有可提交的變更，略過 commit。
) || (
  git commit -m "%COMMIT_MSG%"
  if errorlevel 1 (
    echo [錯誤] commit 失敗，請檢查訊息或檔案狀態。
    pause
    exit /b 1
  )
)

echo [3/4] 先拉取遠端更新並 rebase：origin/%CURRENT_BRANCH% ...
git pull --rebase origin %CURRENT_BRANCH%
if errorlevel 1 (
  echo [錯誤] pull --rebase 發生衝突或失敗。請先解決衝突後再執行本工具。
  pause
  exit /b 1
)

echo [4/4] 推送到遠端：origin/%CURRENT_BRANCH% ...
git push origin %CURRENT_BRANCH%
if errorlevel 1 (
  echo [錯誤] push 失敗。可能是權限或網路問題（若使用 HTTPS，請使用 Personal Access Token 當密碼）。
  pause
  exit /b 1
)

echo.
echo ✅ 完成！已同步到 GitHub：origin/%CURRENT_BRANCH%
pause
