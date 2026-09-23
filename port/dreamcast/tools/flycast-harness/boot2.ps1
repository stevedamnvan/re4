param([string]$Cue='game.cue',[int]$Seconds=30,[string]$Peek='',[string]$Press='')
# Parallel-safe variant (D367): up to $MaxInstances (8) Flycasts may run at once, one per
# evidence dir. Guest RAM is read per-PID (ReadProcessMemory), logs are per-dir, and the
# GDB stub gets a per-instance port (3263..3299, written to gdb.port), so instances don't share anything. Waits for a slot
# instead of refusing.
$MaxInstances = 8
Set-Location $PSScriptRoot
$mine = $null
if (Test-Path 'flycast.pid') { $mine = (Get-Content 'flycast.pid' -Raw).Trim() }
if ($mine) { Stop-Process -Id $mine -Force -ErrorAction SilentlyContinue }
$waited = 0
while (@(Get-Process flycast -ErrorAction SilentlyContinue).Count -ge $MaxInstances) {
  if ($waited -eq 0) { Write-Output "[waiting for a Flycast slot]" }
  Start-Sleep -Seconds 5; $waited += 5
  if ($waited -gt 3600) { throw "no Flycast slot after 1 hour" }
}
Start-Sleep -Milliseconds (Get-Random -Minimum 200 -Maximum 1500)
# Per-instance GDB port: first free TCP port in 3263..3299 goes into this dir's emu.cfg.
$port = $null
foreach ($cand in 3263..3299) {
  $inUse = @(Get-NetTCPConnection -LocalPort $cand -State Listen -ErrorAction SilentlyContinue).Count -gt 0
  if (-not $inUse) { $port = $cand; break }
}
if ($port) {
  (Get-Content emu.cfg) -replace "^Debug.GDBPort = \d+", "Debug.GDBPort = $port" | Set-Content emu.cfg -Encoding ascii
  Set-Content -Path gdb.port -Value $port -Encoding ascii -NoNewline
  Write-Output "[gdb port $port]"
} else {
  (Get-Content emu.cfg) -replace "^Debug.GDBEnabled = yes", "Debug.GDBEnabled = no" | Set-Content emu.cfg -Encoding ascii
  Write-Output "[no free gdb port; GDB disabled for this run]"
}
foreach ($f in 'flycast.log','serial.txt','serial.err.txt') { if (Test-Path $f) { Remove-Item $f -Force } }
$syms = (Get-Content 'syms.txt' -Raw).Trim() -split '\s+'
$p = Start-Process -FilePath '.\flycast.exe' -ArgumentList $Cue -PassThru -WindowStyle Hidden -RedirectStandardOutput 'serial.txt' -RedirectStandardError 'serial.err.txt'
Set-Content -Path 'flycast.pid' -Value $p.Id -Encoding ascii -NoNewline
if ($Press -ne '') { Start-Process -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','press.ps1','-Schedule',$Press) -RedirectStandardOutput 'press.log' -WindowStyle Hidden | Out-Null }
$pcsProc = $null
if ($syms.Count -ge 4) { $pcsProc = Start-Process -FilePath python -ArgumentList @('read_pcs.py',$syms[3],'run.pcs',"$Seconds") -PassThru -NoNewWindow -RedirectStandardOutput 'pcs.log' }
python read_log.py $syms[0] $syms[1] $syms[2] $Seconds | Tee-Object -FilePath boot.log
if ($pcsProc) { $pcsProc.WaitForExit(10000) | Out-Null }
if ($Peek -ne '') { Write-Output "=== peek"; Invoke-Expression "python peek.py $Peek" | Tee-Object -FilePath peek.log }
Stop-Process -Id $p.Id -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Write-Output "=== flycast.log tail"
Get-Content flycast.log -Tail 6
