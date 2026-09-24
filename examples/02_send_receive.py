#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 2: Отправка и приём различных типов данных."""
from inevionet import InevioNet
import json

def main():
    print("=" * 60)
    print(" EXAMPLE 2: SEND & RECEIVE (Text, JSON, Bytes)")
    print("=" * 60)
    
    net = InevioNet(password="data_types_pwd", node_id="sender_node", auto_start=True)
    
    try:
        # 1. Текст
        print("\n1. Отправка текста:")
        p1 = net.send_text("receiver", "Обычный текстовый поток")
        print(f"   ID: {p1.packet_id[:16] if p1 else 'FAIL'}")

        # 2. JSON (словарь)
        print("\n2. Отправка JSON:")
        data = {"sensor": "temp", "value": 24.5, "unit": "C"}
        p2 = net.send_json("receiver", data)
        print(f"   ID: {p2.packet_id[:16] if p2 else 'FAIL'}")

        # 3. Байты (бинарные данные)
        print("\n3. Отправка бинарных данных:")
        binary_data = b"\x00\x01\x02\x03\xFF"
        p3 = net.send("receiver", binary_data)
        print(f"   ID: {p3.packet_id[:16] if p3 else 'FAIL'}")

        # Демонстрация приёма (симуляция)
        print("\n4. Симуляция приёма и декодирования:")
        if p2:
            success, decoded = net.receive(p2.to_bytes())
            print(f"   Успех: {success}")
            print(f"   Данные: {decoded}")

    finally:
        net.stop()

if __name__ == "__main__":
    main()
