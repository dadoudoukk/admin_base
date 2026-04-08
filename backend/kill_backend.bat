@echo off
setlocal

set PORT=%1
if "%PORT%"=="" set PORT=8000

echo Stopping backend on port %PORT% ...

for /f %%p in ('powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue ^| Select-Object -Expand OwningProcess -Unique"') do (
  if not "%%p"=="4" (
    for /f %%r in ('powershell -NoProfile -Command "$pid=%%p; $seen=@{}; while($pid -and $pid -gt 0 -and -not $seen.ContainsKey($pid)){ $seen[$pid]=$true; try{ $parent=(Get-CimInstance Win32_Process -Filter \"ProcessId=$pid\").ParentProcessId } catch { $parent=$null }; if($parent -and $parent -gt 0){ $pid=$parent } else { break } }; if($pid){ $pid }"') do (
      if not "%%r"=="4" (
        echo Killing root PID %%r (tree for port %PORT%)
        taskkill /PID %%r /T /F >nul 2>nul
        powershell -NoProfile -Command "try { Stop-Process -Id %%r -Force -ErrorAction Stop } catch {}" >nul 2>nul
      )
    )
    echo Killing listener PID %%p (port %PORT%)
    taskkill /PID %%p /T /F >nul 2>nul
    powershell -NoProfile -Command "try { Stop-Process -Id %%p -Force -ErrorAction Stop } catch {}" >nul 2>nul
  )
)

timeout /t 1 >nul
powershell -NoProfile -Command "$left = Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue; if($left){ exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo Port %PORT% is still occupied.
  echo Try running this terminal as Administrator.
  exit /b 1
) else (
  echo Done. Port %PORT% is free.
  exit /b 0
)
