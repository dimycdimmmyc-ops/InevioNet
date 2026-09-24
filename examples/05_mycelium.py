#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 5: Мицелий, споры и феромонная маршрутизация."""
from inevionet import InevioNet

def main():
    print("=" * 60)
    print(" EXAMPLE 5: MYCELIUM & PHEROMONES")
    print("=" * 60)
    
    net = InevioNet(password="mycelium_pwd", node_id="fungus_node", auto_start=True)
    
    try:
        print("[+] Инициализация мицелия...")
        
        # 1. Распространение спор
        print("\n[1] Распространение спор в сети...")
        spores_count = net.mycelium.spread(b"Secret payload data")
        print(f"    Создано и размещено спор: {spores_count}")
        
        # 2. Обучение феромонам (симуляция успешных/неуспешных маршрутов)
        print("\n[2] Обучение феромонным тропам...")
        for _ in range(5):
            net.mycelium.record_success("node_A", "node_B", "HTTPS")
            net.mycelium.record_failure("node_A", "node_C", "ICMP")
            
        best_protocol = net.mycelium.get_best_protocol("node_A", "node_B")
        print(f"    Лучший протокол для маршрута A->B: {best_protocol}")
        
        # 3. Сбор данных
        print("\n[3] Сбор данных из мицелия...")
        harvested = net.mycelium.harvest()
        print(f"    Собрано пакетов: {len(harvested)}")

    finally:
        net.stop()

if __name__ == "__main__":
    main()
