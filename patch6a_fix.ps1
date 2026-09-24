$cardHtml = @'
<div class="card">
<h3>Industrial</h3>
<div class="form-group"><label>Target (IP or host:port)</label>
<input id="industrialTarget" placeholder="192.168.1.1:502"></div>
<button class="btn secondary" onclick="scanIndustrial()">Scan Modbus MQTT OPCUA DNP3</button>
<div id="industrialResults"></div>
</div>

<div class="card">
<h3>Stego</h3>
<div class="form-group"><label>Target</label>
<input id="stegoTarget" value="httpbin.org"></div>
<div class="form-group"><label>Method</label>
<select id="stegoMethod">
<option>HTTP_HEADERS</option>
<option>HTTP_COOKIE</option>
<option>HTTP_USER_AGENT</option>
<option>DNS_QNAME</option>
<option>DNS_TXT</option>
<option>ICMP_PAYLOAD</option>
<option>TIMING</option>
</select></div>
<div class="form-group"><label>Data</label>
<textarea id="stegoData" rows="2">test message</textarea></div>
<button class="btn secondary" onclick="sendStego()">Send via stego</button>
</div>

<div class="card">
<h3>Evolution</h3>
<button class="btn secondary" onclick="forceCatastrophe()">Force catastrophe</button>
<button class="btn small" onclick="loadBestStrategies()">Best strategies</button>
<div id="evolutionBest"></div>
</div>

'@

$ProjectRoot = "E:\InevioNet"
$path = Join-Path $ProjectRoot "web\templates\index.html"
$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$content = $content -replace "`r`n", "`n"

if ($content.Contains("industrialTarget")) {
    Write-Host "[!!] Cards already added" -ForegroundColor Yellow
    return
}

# Найдём id="logContainer"
$marker = 'id="logContainer"'
$pos = $content.IndexOf($marker)

if ($pos -lt 0) {
    Write-Host "[!!] logContainer not found" -ForegroundColor Red
    return
}

Write-Host "logContainer at: $pos" -ForegroundColor Cyan

# Откатываемся назад - найдём открывающий div карточки
$backPos = $content.LastIndexOf('<div class="card">', $pos)

if ($backPos -lt 0) {
    Write-Host "[!!] Card div not found" -ForegroundColor Red
    return
}

Write-Host "Card div at: $backPos" -ForegroundColor Cyan

# Вставляем карточки ПЕРЕД карточкой логов
$content = $content.Substring(0, $backPos) + $cardHtml + $content.Substring($backPos)

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $content, $utf8)
Write-Host "[OK] Cards inserted" -ForegroundColor Green