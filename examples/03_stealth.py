#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 3: Стеганография и скрытая передача данных."""
from inevionet import InevioNet

def main():
    print("=" * 60)
    print(" EXAMPLE 3: STEALTH & STEGANOGRAPHY")
    print("=" * 60)
    
    net = InevioNet(password="stealth_pwd", node_id="ghost_node", auto_start=True)
    
    try:
        secret_message = "Секретные координаты: 55.75, 37.61"
        print(f"\n[+] Исходное сообщение: '{secret_message}'")
        
        # Метод 1: HTTP Headers
        print("\n[1] Маскировка через HTTP Headers...")
        success1 = net.send_stealth(secret_message, method="HTTP_HEADERS", target="http://httpbin.org/get")
        print(f"    Результат: {'УСПЕХ' if success1 else 'ПРОВАЛ'}")

        # Метод 2: DNS TXT Records
        print("\n[2] Маскировка через DNS TXT Records...")
        success2 = net.send_stealth(secret_message, method="DNS_TXT", target="example.com")
        print(f"    Результат: {'УСПЕХ' if success2 else 'ПРОВАЛ'}")

    finally:
        net.stop()

if __name__ == "__main__":
    main()
