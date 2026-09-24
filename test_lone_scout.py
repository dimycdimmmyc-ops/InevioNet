#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚁 Тест: Одинокий узел-разведчик
Даже один запущенный узел:
1. Сканирует RF-эфир
2. Находит потенциальные узлы
3. Оставляет споры в обнаруженных сетях
4. Строит топологию
5. Адаптируется под окружение (ambient)
"""
import time
from inevionet import InevioNet

def main():
    print("=" * 70)
    print("  🚁 ТЕСТ: ОДИНОКИЙ УЗЕЛ-РАЗВЕДЧИК")
    print("=" * 70)
    
    # Создаём ОДИН узел
    print("\n1. Создаём единственный узел...")
    net = InevioNet(
        password="lone_scout_password",
        node_id="lone_scout_001",
        mode="standard",
        auto_start=True,
    )
    print(f"   ✅ Узел создан: {net.node_id}")
    print(f"   📡 Режим: {net.mode}")
    
    # 2. RF-сканирование
    print("\n2. Сканирование RF-эфира...")
    try:
        env = net.scan_environment()
        print(f"   📊 Сигналов обнаружено: {env['scan']['signals']}")
        print(f"   📊 Метод: {env['scan']['method']}")
        print(f"   📊 Длительность: {env['scan']['duration_ms']:.0f} мс")
        
        if env['signals_by_type']:
            print(f"   📊 По типам:")
            for sig_type, count in env['signals_by_type'].items():
                print(f"      {sig_type}: {count}")
    except Exception as e:
        print(f"   ⚠️  RF-сканирование недоступно: {e}")
    
    # 3. Построение mesh-топологии
    print("\n3. Построение mesh-топологии...")
    try:
        mesh = net.build_mesh_topology()
        build_info = mesh.get('build', {})
        print(f"   🕸️  Узлов: {build_info.get('nodes', 0)}")
        print(f"   🕸️  Рёбер: {build_info.get('edges', 0)}")
        print(f"   🕸️  Успех: {build_info.get('success', False)}")
    except Exception as e:
        print(f"   ⚠️  Mesh-топология недоступна: {e}")
    
    # 4. Ambient-маскировка
    print("\n4. Ambient-адаптация...")
    try:
        net.enable_ambient_masking()
        print(f"   ✅ Ambient-маскировка включена")
        
        # Отправляем тестовое сообщение с адаптацией
        success, packet = net.send_ambient_masked("target_node", "Test message")
        print(f"   📤 Отправка: {'✅' if success else '❌'}")
    except Exception as e:
        print(f"   ⚠️  Ambient недоступен: {e}")
    
    # 5. Мицелий — оставляем споры
    print("\n5. Распространение мицелия (оставляем споры)...")
    try:
        networks = ["5G", "WiFi", "Satellite", "IoT"]
        results = net.spread_mycelium(networks)
        for network, success in results.items():
            status = "✅" if success else "❌"
            print(f"   {status} {network}")
    except Exception as e:
        print(f"   ⚠️  Мицелий недоступен: {e}")
    
    # 6. Статистика
    print("\n6. Статистика узла:")
    stats = net.get_stats()
    print(f"    Отправлено: {stats['packets_sent']}")
    print(f"   📊 Доставлено: {stats['packets_delivered']}")
    print(f"   📊 Ошибок: {stats['packets_failed']}")
    print(f"   📊 Uptime: {stats['uptime']:.1f} сек")
    
    # 7. Агрегированная статистика
    print("\n7. Агрегированная статистика:")
    try:
        agg_stats = net.get_aggregated_stats()
        summary = agg_stats.get('summary', {})
        print(f"   📊 Компонентов: {summary.get('components_count', 0)}")
        print(f"   📊 Delivery rate: {summary.get('delivery_rate', 0):.2%}")
    except Exception as e:
        print(f"   ⚠️  Агрегатор недоступен: {e}")
    
    # Завершение
    net.stop()
    
    print("\n" + "=" * 70)
    print("  ✅ ТЕСТ ЗАВЕРШЁН")
    print("=" * 70)
    print("\n🚁 Вывод:")
    print("   Даже один узел может:")
    print("   • Сканировать эфир и находить сигналы")
    print("   • Строить топологию сети")
    print("   • Адаптироваться под окружение")
    print("   • Оставлять споры для будущих узлов")
    print("\n «Пространство заполнено сигналами —")
    print("       значит, есть за что зацепиться!»")

if __name__ == "__main__":
    main()
