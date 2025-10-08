@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Go to script directory
cd /d "%~dp0"
echo.
echo Repo: "%cd%"

REM Check Git availability
git --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Git is not installed or not in PATH.
  pause
  exit /b 1
)

REM Check Git repository
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Current folder is not a Git repository.
  pause
  exit /b 1
)

REM Make sure this script is never uploaded (local exclude)
set "_EXCLUDE=.git\info\exclude"
if not exist ".git\info" mkdir ".git\info" 2>nul
findstr /x /c:"git_sync.bat" "%_EXCLUDE%" >nul 2>&1 || (echo git_sync.bat>>"%_EXCLUDE%")

REM Current branch
for /f "delims=" %%B in ('git rev-parse --abbrev-ref HEAD') do set "BR=%%B"
if /i "!BR!"=="HEAD" (
  echo [INFO] Detached HEAD detected. Using 'main' as default branch.
  set "BR=main"
)

REM Remote
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Remote 'origin' is not configured.
  echo        Run:  git remote add origin https://github.com/<your-account>/<repo>.git
  pause
  exit /b 1
)
for /f "delims=" %%U in ('git remote get-url origin') do set "REMOTE_URL=%%U"
echo Branch: !BR!
echo Remote: !REMOTE_URL!

REM Commit message
echo.
set "MSG="
set /p MSG=Commit message (default: update): 
if "!MSG!"=="" set "MSG=update"

REM Stage and commit first (so workspace is clean for rebase)
echo.
echo === Adding changes ===
git add -A

echo.
echo === Status after add ===
git status -sb

set "HAS_STAGED="
for /f "delims=" %%F in ('git diff --cached --name-only') do (
  set "HAS_STAGED=1"
  goto :has_staged
)
:has_staged

if defined HAS_STAGED (
  echo.
  echo === Committing ===
  git commit -m "!MSG!"
  if errorlevel 1 (
    echo [ERROR] Commit failed.
    pause
    exit /b 1
  )
) else (
  echo.
  echo [INFO] No staged changes to commit.
)

REM Pull with rebase (after commit)
echo.
echo === Fetching ===
git fetch --all --prune

git rev-parse --abbrev-ref --symbolic-full-name @{u} >nul 2>&1
if not errorlevel 1 (
  echo.
  echo === Pulling with rebase ===
  git pull --rebase
  if errorlevel 1 (
    echo [ERROR] Pull --rebase failed. Resolve conflicts (or run ^"git rebase --abort^") and re-run this script.
    pause
    exit /b 1
  )
) else (
  echo.
  echo [INFO] No upstream configured for !BR!. Will set it on push.
)

REM Push (set upstream if missing)
echo.
echo === Pushing ===
git rev-parse --abbrev-ref --symbolic-full-name @{u} >nul 2>&1
if errorlevel 1 (
  git push -u origin "!BR!"
) else (
  git push
)

if errorlevel 1 (
  echo [ERROR] Push failed. If an auth prompt flashed and closed, set credentials:
  echo   git config --global credential.helper manager
  echo Then push once in a terminal to store credentials.
  pause
  exit /b 1
)

echo.
echo Done.
pause
