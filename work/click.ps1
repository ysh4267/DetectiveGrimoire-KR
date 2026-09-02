param(
  [int]$X = 960,
  [int]$Y = 540,
  [int]$Times = 1,
  [int]$DelayMs = 800,
  [string]$ProcName = "Detective Grimoire"
)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Clk {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  public struct RECT { public int L, T, R, B; }
  public const uint DOWN = 0x0002, UP = 0x0004;
}
"@

$p = Get-Process | Where-Object { $_.ProcessName -eq $ProcName -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { Write-Output "NO WINDOW"; exit 1 }
[void][Clk]::SetForegroundWindow($p.MainWindowHandle)
Start-Sleep -Milliseconds 400

$r = New-Object Clk+RECT
[void][Clk]::GetWindowRect($p.MainWindowHandle, [ref]$r)

for ($i = 0; $i -lt $Times; $i++) {
  [void][Clk]::SetCursorPos($r.L + $X, $r.T + $Y)
  Start-Sleep -Milliseconds 120
  [Clk]::mouse_event([Clk]::DOWN, 0, 0, 0, [IntPtr]::Zero)
  Start-Sleep -Milliseconds 60
  [Clk]::mouse_event([Clk]::UP, 0, 0, 0, [IntPtr]::Zero)
  Start-Sleep -Milliseconds $DelayMs
}
Write-Output "clicked $Times x at ($X,$Y) in window at ($($r.L),$($r.T))"
