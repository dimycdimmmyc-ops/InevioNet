# Patch 9b: exact RF fix via IndexOf
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"
$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"

if ($orch.Contains("wifi_provider=None)")) {
    Write-Host "[--] already patched" -ForegroundColor Yellow
    return
}

# Найдём def _enable_rf_scanning_impl
$startMarker = "def _enable_rf_scanning_impl(self, interface=None):"
$startPos = $orch.IndexOf($startMarker)
if ($startPos -lt 0) {
    Write-Host "[!!] RF impl not found" -ForegroundColor Red
    return
}

# Найдём следующий def
$endPos = $orch.IndexOf("`ndef ", $startPos + 10)
if ($endPos -lt 0) {
    Write-Host "[!!] Next def not found" -ForegroundColor Red
    return
}

Write-Host "RF impl: $startPos .. $endPos" -ForegroundColor Cyan

$newRF = @'
def _enable_rf_scanning_impl(self, interface=None, wifi_provider=None):
    # P13: wifi_provider fix
    from .network.rf_scanner import RFScanner
    if not hasattr(self, '_rf_scanner') or self._rf_scanner is None:
        self._rf_scanner = RFScanner(
            interface=interface,
            wifi_provider=wifi_provider,
        )
        logger.info(f"RF scanning enabled: {self._rf_scanner}")
    return self._rf_scanner

'@

$orch = $orch.Substring(0, $startPos) + $newRF + $orch.Substring($endPos + 1)

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($orchPath, $orch, $utf8)
Write-Host "[OK] orchestrator patched" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$orchPath', encoding='utf-8').read()); print('OK')"