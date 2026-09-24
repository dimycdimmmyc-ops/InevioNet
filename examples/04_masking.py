#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 4: Обход DPI и адаптивная маскировка."""
from inevionet import InevioNet

def main():
    print("=" * 60)
    print(" EXAMPLE 4: DPI BYPASS & ADAPTIVE MASKING")
    print("=" * 60)
    
    net = InevioNet(password="masking_pwd", node_id="bypass_node", auto_start=True)
    
    try:
        # Включаем движок маскировки
        net.enable_masking(dpi_profile="high")
        print("[+] Движок маскировки активирован (профиль: high)")
        
        target = "restricted.target.com"
        print(f"\n[+] Зондирование цели: {target}...")
        
        # Автоматическое зондирование
        analysis = net.probe_node(target)
        print(f"[+] Найдено рабочих протоколов: {analysis.get('successful', 0)}/{analysis.get('total', 0)}")
        print(f"[+] Лучшие протоколы: {', '.join(analysis.get('best_protocols', []))}")
        
        # Отправка с гарантией и полиморфизмом
        print(f"\n[+] Отправка замаскированного пакета с полиморфизмом...")
        success, packet = net.send_masked(target, "Критические данные", polymorphic=True)
        
        if success:
            print(f"[✓] Успешно доставлено через адаптивный канал!")
        else:
            print("[✗] Не удалось доставить")

    finally:
        net.stop()

if __name__ == "__main__":
    main()
