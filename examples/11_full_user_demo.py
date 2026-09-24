#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example 11: Полный пример с регистрацией, QR и контактами.

Демонстрирует:
1. Регистрацию пользователя
2. Вход в систему
3. Генерацию QR-кода контакта
4. Добавление контакта из QR
5. Отправку сообщения контакту
6. Список контактов
"""
from inevionet import InevioNet
from inevionet.users import get_user_manager
import json

def main():
    print("=" * 70)
    print(" EXAMPLE 11: ПОЛНЫЙ ПРИМЕР — РЕГИСТРАЦИЯ + QR + КОНТАКТЫ")
    print("=" * 70)
    
    um = get_user_manager()
    
    # 1. РЕГИСТРАЦИЯ
    print("\n1. РЕГИСТРАЦИЯ")
    print("-" * 70)
    try:
        profile = um.register("alice", "alice1234")
        print(f"   ✅ Создан пользователь: {profile.username}")
        print(f"   Node ID: {profile.node_id}")
        print(f"   Public Key: {profile.public_key_hex[:32]}...")
    except ValueError as e:
        print(f"   ℹ️  {e}")
        profile = um.login("alice", "alice1234")
        print(f"   ✅ Вошёл как: {profile.username}")
    
    # 2. ГЕНЕРАЦИЯ QR
    print("\n2. ГЕНЕРАЦИЯ QR-КОДА")
    print("-" * 70)
    qr_path = um.generate_contact_qr()
    if qr_path:
        print(f"   ✅ QR создан: {qr_path}")
        qr_data = profile.to_qr_data()
        print(f"   Данные QR:")
        print(f"   {json.dumps(qr_data, indent=4, ensure_ascii=False)}")
    else:
        print("   ⚠️  QR не создан (нет qrcode библиотеки)")
    
    # 3. СОЗДАЁМ ВТОРОГО ПОЛЬЗОВАТЕЛЯ (симуляция)
    print("\n3. СОЗДАНИЕ ВТОРОГО ПОЛЬЗОВАТЕЛЯ (BOB)")
    print("-" * 70)
    try:
        bob = um.register("bob", "bob1234")
        print(f"   ✅ Создан: {bob.username} ({bob.node_id})")
    except ValueError:
        bob = um.login("bob", "bob1234")
        print(f"   ✅ Вошёл как: {bob.username}")
    
    # 4. ДОБАВЛЕНИЕ КОНТАКТА
    print("\n4. ДОБАВЛЕНИЕ КОНТАКТА ALICE В БОБА")
    print("-" * 70)
    alice_qr = profile.to_qr_data()
    added = um.add_contact(alice_qr)
    if added:
        print(f"   ✅ Контакт добавлен: {profile.username}")
    else:
        print(f"   ℹ️  Контакт уже существует")
    
    # 5. СПИСОК КОНТАКТОВ
    print("\n5. СПИСОК КОНТАКТОВ BOB")
    print("-" * 70)
    contacts = um.get_contacts()
    print(f"   Всего контактов: {len(contacts)}")
    for c in contacts:
        print(f"   👤 {c['username']}")
        print(f"      Node ID: {c['node_id']}")
        print(f"      Public Key: {c.get('public_key', '')[:32]}...")
    
    # 6. ОТПРАВКА СООБЩЕНИЯ
    print("\n6. ОТПРАВКА СООБЩЕНИЯ")
    print("-" * 70)
    net = InevioNet(password="demo_pwd", node_id=bob.node_id, auto_start=True)
    try:
        print(f"   От: {bob.username} ({bob.node_id})")
        print(f"   Кому: {profile.username} ({profile.node_id})")
        
        packet = net.send(profile.node_id, "Привет, Alice! Это Bob.")
        if packet:
            print(f"   ✅ Отправлено! Packet ID: {packet.packet_id[:16]}...")
        else:
            print(f"   ⚠️  Пакет создан, но не доставлен (нет сети)")
    finally:
        net.stop()
    
    # 7. УДАЛЕНИЕ КОНТАКТА
    print("\n7. УДАЛЕНИЕ КОНТАКТА")
    print("-" * 70)
    removed = um.remove_contact(profile.node_id)
    print(f"   Удалено: {removed}")
    print(f"   Осталось контактов: {len(um.get_contacts())}")
    
    print("\n" + "=" * 70)
    print(" ✅ ПРИМЕР ЗАВЕРШЁН")
    print("=" * 70)

if __name__ == "__main__":
    main()
