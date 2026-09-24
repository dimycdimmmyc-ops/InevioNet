# Patch 2: evolution/engine.py - catastrophe + reward + best_strategy
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$BackupDir = Join-Path $ProjectRoot "_backup_engine"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

$path = Join-Path $ProjectRoot "inevionet\evolution\engine.py"
Copy-Item $path (Join-Path $BackupDir "engine.py") -Force
Write-Host "Backup: $BackupDir\engine.py"

$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$content = $content -replace "`r`n", "`n"
$content = $content -replace "`r", "`n"

# === 1. Добавить катастрофу в evolve() ===
if ($content.Contains("self._catastrophe()")) {
    Write-Host "[!!] _catastrophe already added" -ForegroundColor Yellow
} else {
    $oldEvolve = "        self.population = new_population[:self.population_size]`n" +
                 "        self._update_best()`n" +
                 "        self.history.append({"
    $newEvolve = "        self.population = new_population[:self.population_size]`n" +
                 "        self._update_best()`n`n" +
                 "        if self.generation > 0 and self.generation % 50 == 0:`n" +
                 "            self._catastrophe()`n`n" +
                 "        self.history.append({"
    if ($content.Contains($oldEvolve)) {
        $content = $content.Replace($oldEvolve, $newEvolve)
        Write-Host "[OK] Catastrophe hook added" -ForegroundColor Green
    } else {
        Write-Host "[!!] evolve() pattern not found" -ForegroundColor Yellow
    }
}

# === 2. Добавить методы перед _update_best ===
if ($content.Contains("def _catastrophe")) {
    Write-Host "[!!] methods already added" -ForegroundColor Yellow
} else {
    $oldUpdate = "    def _update_best(self):"
    $newMethods = @'
    def _catastrophe(self):
        """P13: РЎРґРІРёРі fitness landscape + РёРЅР¶РµРєС†РёСЏ СЃР»СѓС‡Р°Р№РЅС‹С… РіРµРЅРѕРІ."""
        logger.info("[Evolution] CATASTROPHE at generation %d", self.generation)
        keep = max(1, int(len(self.population) * 0.7))
        self.population = sorted(
            self.population, key=lambda g: g.fitness, reverse=True
        )[:keep]
        while len(self.population) < self.population_size:
            g = create_random_genome()
            g.mutation_rate = self.mutation_rate
            g.calculate_fitness(self.fitness_weights)
            self.population.append(g)
        logger.info("[Evolution] after catastrophe: pop=%d, diversity=%.3f",
                    len(self.population), self._diversity())

    def reward(self, strategy_type, strategy_value, success, delta=0.1):
        """P13: РќР°РіСЂР°РґР° РіРµРЅРѕРјР°Рј РїРѕ СЂРµР·СѓР»СЊС‚Р°С‚Р°Рј."""
        if not self.population:
            return 0
        attr_map = {
            "penetration": "penetration_strategy",
            "masking": "masking_channel",
            "stego": "stego_method",
            "industrial": "industrial_protocol",
            "protocol": "protocol_name",
        }
        attr = attr_map.get(strategy_type)
        if not attr:
            return 0
        reward = delta if success else -delta * 0.5
        matched = 0
        for genome in self.population:
            if getattr(genome, attr, None) == strategy_value:
                genome.fitness = max(0.0, min(1.0, genome.fitness + reward))
                matched += 1
        return matched

    def best_strategy(self, strategy_type):
        """P13: Р›СѓС‡С€Р°СЏ СЃС‚СЂР°С‚РµРіРёСЏ РїРѕ С‚РёРїСѓ."""
        if not self.population:
            return None
        attr_map = {
            "penetration": "penetration_strategy",
            "masking": "masking_channel",
            "stego": "stego_method",
            "industrial": "industrial_protocol",
            "protocol": "protocol_name",
        }
        attr = attr_map.get(strategy_type)
        if not attr:
            return None
        top = sorted(self.population, key=lambda g: g.fitness, reverse=True)[:10]
        votes = {}
        for g in top:
            v = getattr(g, attr, None)
            if v:
                votes[v] = votes.get(v, 0.0) + g.fitness
        if not votes:
            return None
        return max(votes, key=votes.get)

    def _update_best(self):
'@
    if ($content.Contains($oldUpdate)) {
        $content = $content.Replace($oldUpdate, $newMethods)
        Write-Host "[OK] methods added" -ForegroundColor Green
    } else {
        Write-Host "[!!] _update_best not found" -ForegroundColor Yellow
    }
}

# === 3. Убрать dead code в конце ===
$deadCode = '    print("EvolutionEngine module OK")' + "`n`n" +
            '    def inject_random_mutations(self, fraction=0.2):'
if ($content.Contains($deadCode)) {
    $start = $content.IndexOf($deadCode)
    $content = $content.Substring(0, $start) + '    print("EvolutionEngine module OK")' + "`n"
    Write-Host "[OK] dead code removed" -ForegroundColor Green
}

# Сохраняем
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $content, $utf8)
Write-Host "[OK] engine.py saved" -ForegroundColor Green

# Проверка
python -c "import ast; ast.parse(open(r'$path', encoding='utf-8').read()); print('OK')"