#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 1: Hello World - простейшее использование InevioNet."""
from inevionet import InevioNet

def main():
    print("=" * 60)
    print(" EXAMPLE 1: HELLO WORLD")
    print("=" * 60)
    
    # Инициализация сети (2 строки кода)
    net = InevioNet(password="my_secret_password", node_id="node_alice", auto_start=True)
    
    try:
        print(f"\n[+] Узел инициализирован: {net.node_id}")
        
        # Отправка сообщения
        print("[+] Отправка сообщения узлу 'bob'...")
        packet = net.send("bob", "Привет, это тестовое сообщение!")
        
        if packet:
            print(f"[✓] Успешно! ID пакета: {packet.packet_id[:16]}...")
        else:
            print("[✗] Ошибка отправки")
            
    finally:
        net.stop()
        print("\n[+] Сеть остановлена.")

if __name__ == "__main__":
    main()
