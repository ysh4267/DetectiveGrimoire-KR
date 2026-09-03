param(
  [ValidateSet('original', 'korean')][string]$Assets = 'korean',
  [ValidateSet('original', 'korean')][string]$Main = 'korean',
  [string]$Tag = 'test',
  [string]$Only = '',            # restore ONLY this relative path to Korean
  [string]$Group = ''            # or every Korean file whose path contains this
)

# derived from this script's own location, so the repo can live anywhere --
# and no literal non-ASCII: Windows PowerShell 5.1 reads .ps1 as ANSI and
# would mangle a hard-coded Korean path
$proj = Split-Path -Parent $PSScriptRoot
$game = 'e:\Program Files\SteamLibrary\steamapps\common\Detective Grimoire'
$orig = Join-Path $proj 'backup\swf-dsk-original'
$kor  = Join-Path $proj 'dist\assets\swf-dsk'

Get-Process | Where-Object { $_.ProcessName -like '*Detective*' } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$n = 0
Get-ChildItem -Path $orig -Recurse -Filter *.swf | ForEach-Object {
  $rel = $_.FullName.Substring($orig.Length + 1)
  $k = Join-Path $kor $rel
  $useKorean = $false
  if ($Assets -eq 'korean') { $useKorean = $true }
  if ($Only  -and $rel -eq $Only) { $useKorean = $true }
  if ($Group -and $rel -like "*$Group*") { $useKorean = $true }
  $from = if ($useKorean -and (Test-Path $k)) { $n++; $k } else { $_.FullName }
  Copy-Item $from (Join-Path "$game\assets\swf-dsk" $rel) -Force
}

$m = if ($Main -eq 'original') { Join-Path $proj 'backup\DetectiveGrimoireDesktopSteam.swf' }
     else { Join-Path $proj 'dist\DetectiveGrimoireDesktopSteam.swf' }
Copy-Item $m "$game\DetectiveGrimoireDesktopSteam.swf" -Force
Write-Output "korean assets installed: $n   main: $Main"

Start-Process -FilePath "$game\Detective Grimoire.exe" -WorkingDirectory $game
Start-Sleep -Seconds 26
Set-Location $proj
& powershell -ExecutionPolicy Bypass -File (Join-Path $proj 'work\shot.ps1') -Out (Join-Path $proj "work\shots\lt_${Tag}_0.png") | Out-Null
& powershell -ExecutionPolicy Bypass -File (Join-Path $proj 'work\click.ps1') -X 960 -Y 572 -Times 1 -DelayMs 2500 | Out-Null
Start-Sleep -Seconds 4
& powershell -ExecutionPolicy Bypass -File (Join-Path $proj 'work\click.ps1') -X 820 -Y 300 -Times 1 -DelayMs 2000 | Out-Null
Start-Sleep -Seconds 15

$p = Get-Process | Where-Object { $_.ProcessName -like '*Detective*' } | Select-Object -First 1
if (-not $p) {
  Write-Output "RESULT[$Tag]: CRASHED"
} else {
  Write-Output ("RESULT[$Tag]: alive responding=" + $p.Responding)
  & powershell -ExecutionPolicy Bypass -File (Join-Path $proj 'work\shot.ps1') -Out (Join-Path $proj "work\shots\lt_${Tag}_1.png") | Out-Null
}
