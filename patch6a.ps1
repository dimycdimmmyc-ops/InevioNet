$cardHtml = @'
<div class="card">
<h3>Промышленные протоколы</h3>
<div class="form-group"><label>Target (IP или host:port)</label>
<input id="industrialTarget" placeholder="192.168.1.1:502"></div>
<button class="btn secondary" onclick="scanIndustrial()">Scan Modbus/MQTT/OPC-UA/DNP3</button>
<div id="industrialResults" style="margin-top:10px;font-family:monospace;font-size:.75em;max-height:150px;overflow:auto;color:var(--dim)"></div>
</div>

<div class="card">
<h3>Стеганография</h3>
<div class="form-group"><label>Target (URL/domain)</label>
<input id="stegoTarget" value="httpbin.org"></div>
<div class="form-group"><label>Метод</label>
<select id="stegoMethod">
<option>HTTP_HEADERS</option>
<option>HTTP_COOKIE</option>
<option>HTTP_USER_AGENT</option>
<option>DNS_QNAME</option>
<option>DNS_TXT</option>
<option>ICMP_PAYLOAD</option>
<option>TIMING</option>
</select></div>
<div class="form-group"><label>Данные</label>
<textarea id="stegoData" rows="2">test message</textarea></div>
<button class="btn secondary" onclick="sendStego()">Отправить через стего</button>
</div>

<div class="card">
<h3>Эволюция</h3>
<button class="btn secondary" onclick="forceCatastrophe()">Форсировать катастрофу</button>
<button class="btn small" onclick="loadBestStrategies()">Best strategies</button>
<div id="evolutionBest" style="margin-top:10px;font-family:monospace;font-size:.75em;color:var(--dim)"></div>
</div>

'@

$ProjectRoot = "E:\InevioNet"
$path = Join-Path $ProjectRoot "web\templates\index.html"
$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$content = $content -replace "`r`n", "`n"

if ($content.Contains("industrialTarget")) {
    Write-Host "[!!] Cards already added" -ForegroundColor Yellow
} else {
    $marker = '<h3>Системный лог</h3>'
    $pos = $content.IndexOf($marker)
    
    if ($pos -lt 0) {
        Write-Host "[!!] Marker not found" -ForegroundColor Red
    } else {
        # Найдём "<div class=" перед маркером
        $backPos = $content.LastIndexOf('<div class="card">', $pos)
        if ($backPos -lt 0) { $backPos = $pos }
        
        $content = $content.Substring(0, $backPos) + $cardHtml + $content.Substring($backPos)
        
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($path, $content, $utf8)
        Write-Host "[OK] Cards inserted" -ForegroundColor Green
    }
}