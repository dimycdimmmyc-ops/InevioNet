# InevioNet — Модули

## core/

- crypto.py — InevioCrypto, AES + RSA
- packet.py — GDPPacket
- logger.py — Логирование
- constants.py — DataPaths, режимы
- exceptions.py — Исключения
- cache.py — LRU-кэш
- beacon.py — Multicast beacons
- async_utils.py — Асинхронность
- stats_aggregator.py — Статистика

## network/

- tcp.py — TCPClient, TCPServer
- udp.py — UDPClient, UDPHolePuncher, STUN
- dns.py — DNSClient (QNAME/TXT)
- http.py — HTTPClient (headers)
- icmp.py — ICMPClient (raw socket)
- websocket.py — WSClient
- transport.py — UniversalTransport
- rf_scanner.py — WiFi + BT + BLE + LTE + GPS
- ble_scanner.py — BLE через bleak
- lte_scanner.py — LTE через netsh mbn
- cellular_scanner.py — Оператор + геолокация
- tor_transport.py — SOCKS5 через Tor
- i2p_transport.py — SAM bridge
- webrtc_bridge.py — WebRTC DataChannel
- bridge_broker.py — Координатор relay
- relay_node.py — Узел-релей

## mycelium/

- engine.py — MyceliumEngine
- penetration.py — 6 методов проникновения
- spores.py — SporeManager, Spore
- pheromones.py — PheromoneEngine

## evolution/

- genome.py — ProtocolGenome, 14 генов
- engine.py — EvolutionEngine, catastrophe, reward

## masking/

- masking_engine.py — Главный движок
- polymorphic.py — Фрагментация
- ambient.py — Адаптация к трафику
- bayesian.py — Байесовский выбор
- channel_selector.py — Селектор каналов
- firewall_model.py — Модель firewall
- detection.py — KL-дивергенция
- vulnerability_map.py — Карта уязвимостей
- probing.py — Зондирование

## steganography/

- engine.py — SteganographyEngine
- dns_tunnel.py — DNS-туннель
- http_headers.py — HTTP-заголовки
- icmp_payload.py — ICMP-payload
- timing.py — Timing channel

## industrial/

- base.py — IndustrialProtocol
- modbus.py — ModbusTCP, ModbusRTU
- mqtt.py — MQTTClient
- opcua.py — OPCUA
- dnp3.py — DNP3

## identity/

- device_id.py — DeviceID
- identity.py — DeviceIdentity
- registry.py — DeviceRegistry
- discovery.py — DiscoveryEngine
- trust.py — TrustEngine
- presence.py — PresenceManager
- fingerprint.py — DeviceFingerprint

## Остальные

- mesh/auto_topology.py — Авто-топология
- symbiotic/ecosystem.py — Экосистема
- ai/selector.py — ProtocolSelector
- ai/recursion.py — WeightedRecursion
- web/app.py — Flask API
- web/templates/index.html — iOS 27 UI
- orchestrator.py — Главный класс
