# InevioNet — Архитектура

## Философия

Сети видят выбор, но выбора нет. Пакет всегда доставляется.

InevioNet — децентрализованная самоэволюционирующая P2P-сеть,
построенная по биомиметической модели: ДНК → Мицелий → P2P.

## Три уровня

### 1. ДНК (генотип)

Файл: inevionet/evolution/genome.py

Каждый узел имеет геном — набор из 14+ генов:

- speed (0.0-1.0)
- reliability (0.0-1.0)
- stealth (0.0-1.0)
- efficiency (0.0-1.0)
- adaptability (0.0-1.0)
- packet_size (64-9000)
- ttl (1-64)
- priority (1-10)
- clone_threshold (1-10)
- penetration_strategy (enum)
- masking_channel (enum)
- industrial_protocol (enum)
- stego_method (enum)
- use_polymorphic (bool)
- use_ambient (bool)
- use_stego (bool)

### 2. Мицелий (фенотип)

Файлы: inevionet/mycelium/*.py

- engine.py — главный движок
- penetration.py — проникновение (6 методов)
- spores.py — автономные агенты
- pheromones.py — маршрутизация по феромонам

### 3. P2P-сеть (экосистема)

Узлы 8 типов:

- self — твой узел (зелёный)
- wifi — Wi-Fi сети (синий)
- super — супер-узлы (белый)
- spore — споры мицелия (розовый)
- ble — Bluetooth LE (голубой)
- bluetooth — BT classic (синий)
- cellular — LTE/5G (жёлтый)
- industrial — Modbus/MQTT (оранжевый)
- peer — другие узлы (фиолетовый)

## Поток данных

send -> encrypt -> sign -> transport
  -> Tor (анонимно)
  -> I2P (анонимно, РФ)
  -> P2P Bridge (WebRTC)
  -> Masking (DPI bypass)
  -> Steganography (4 канала)
  -> Direct (TCP/UDP/DNS/ICMP)

receive <- verify <- decrypt <- decode

## Эволюция

Каждые 4 секунды: сканер обновляет узлы
Каждые 40 секунд: evolve() — новое поколение
Каждые 50 поколений: КАТАСТРОФА — сброс diversity

### Fitness

f(g) = speed*0.25 + reliability*0.30 + stealth*0.20
     + efficiency*0.15 + adaptability*0.10 + bonus

### Reward

Успешная отправка: +0.1 к fitness
Неудачная: -0.05 к fitness

## Модули

core       — 9 файлов, ядро (crypto, packet, logger)
network    — 16 файлов, транспорты (TCP/UDP/DNS/ICMP/WS/WebRTC)
mycelium   — 4 файла, мицелий (penetration, spores, pheromones)
evolution  — 2 файла, генетический алгоритм
masking    — 9 файлов, DPI bypass
steganography — 5 файлов, скрытые каналы
industrial — 5 файлов, Modbus/MQTT/OPCUA/DNP3
identity   — 7 файлов, идентификация
mesh       — 1 файл, авто-топология
symbiotic  — 2 файла, экосистема
ai         — 2 файла, selector + recursion
web        — 2 файла, Flask + UI

ВСЕГО: ~63 файла, ~22000 строк

## Ссылки

- docs/MODULES.md — детали модулей
- docs/MATH.md — формальная математика
- README_FOR_DUMMIES.md — инструкция
