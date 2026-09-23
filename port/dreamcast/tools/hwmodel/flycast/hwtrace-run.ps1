param([string]$Out='trace', [string]$Cue='game.cue', [string]$FrameAddr='', [string]$Count='2401:2520', [string]$Trace='2401:2520:8', [int]$Seconds=3600)
# hwmodel: run the interpreter-mode hwtrace Flycast build (flycast.exe here is NOT the template build).
# Writes per-PC execution counts for frames $Count and full traces for frames $Trace (A:B:STEP)
# into .\$Out\, then Flycast exits by itself (HWTRACE_EXIT). $FrameAddr = physical address of the
# re4dc_pcs LAST_FRAME word (syms.txt 4th offset + 0x0c000000 + 64); derived from syms.txt if empty.
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force $Out | Out-Null
if ($FrameAddr -eq '') {
  $syms = (Get-Content 'syms.txt' -Raw).Trim() -split '\s+'
  $FrameAddr = '{0:x8}' -f ([Convert]::ToInt64($syms[3].Replace('0x',''), 16) + 0x0c000000 + 64)
}
$env:HWTRACE_DIR = (Resolve-Path $Out).Path
$env:HWTRACE_FRAMEADDR = $FrameAddr
$env:HWTRACE_COUNT = $Count
$env:HWTRACE_TRACE = $Trace
$env:HWTRACE_EXIT = '1'
"frameaddr $FrameAddr count $Count trace $Trace" | Out-File "$Out\params.txt" -Encoding ascii
$t0 = Get-Date
powershell -NoProfile -ExecutionPolicy Bypass -File boot2.ps1 -Cue $Cue -Seconds $Seconds *> "$Out\run-output.txt"
"elapsed_s $(((Get-Date) - $t0).TotalSeconds)" | Out-File "$Out\elapsed.txt" -Encoding ascii
