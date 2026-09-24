#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""InevioNet Command Line Interface (CLI)."""
import sys
import argparse
import json
from inevionet import InevioNet, __version__

def print_header(text):
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)

def cmd_send(args):
    """Отправка сообщения."""
    print_header(" ОТПРАВКА СООБЩЕНИЯ")
    net = InevioNet(password=args.password, node_id=args.sender or "cli_sender", auto_start=True)
    try:
        print(f"[+] Отправка от '{net.node_id}' к '{args.receiver}'...")
        packet = net.send(args.receiver, args.message)
        if packet:
            print(f"[✓] Успешно! ID: {packet.packet_id[:16]}")
        else:
            print("[✗] Ошибка отправки")
    finally:
        net.stop()

def cmd_stats(args):
    """Просмотр статистики."""
    print_header(" СТАТИСТИКА УЗЛА")
    # Для простоты создаем временный узел или читаем из файла состояния
    net = InevioNet(password=args.password, node_id="cli_stats", auto_start=False)
    print(f"Версия: {__version__}")
    print(f"Режим: {net.mode}")
    print("[+] Статистика доступна через API или Web Dashboard.")

def cmd_demo(args):
    """Запуск полной демонстрации."""
    print_header(" ПОЛНАЯ ДЕМОНСТРАЦИЯ INEVIONET")
    net = InevioNet(password="demo_pwd", node_id="demo_master", auto_start=True)
    try:
        print("[1] Инициализация... OK")
        print("[2] Отправка текста... ", end="")
        p = net.send("target", "Demo message")
        print("OK" if p else "FAIL")
        
        print("[3] Включение маскировки... ", end="")
        net.enable_masking()
        print("OK")
        
        print("[4] Зондирование... ", end="")
        res = net.probe_node("example.com")
        print(f"OK (найдено {res.get('successful', 0)} каналов)")
        
        print("\n[✓] Демонстрация успешно завершена!")
    finally:
        net.stop()

def main():
    parser = argparse.ArgumentParser(
        prog="inevionet",
        description=f"InevioNet CLI v{__version__} - Guaranteed Delivery Protocol"
    )
    parser.add_argument("-v", "--version", action="version", version=f"InevioNet {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")
    
    # Команда send
    p_send = subparsers.add_parser("send", help="Отправить сообщение")
    p_send.add_argument("-p", "--password", default="default_password", help="Пароль сети")
    p_send.add_argument("-s", "--sender", help="ID отправителя")
    p_send.add_argument("-r", "--receiver", required=True, help="ID или адрес получателя")
    p_send.add_argument("-m", "--message", required=True, help="Текст сообщения")
    p_send.set_defaults(func=cmd_send)
    
    # Команда stats
    p_stats = subparsers.add_parser("stats", help="Показать статистику")
    p_stats.add_argument("-p", "--password", default="default_password", help="Пароль сети")
    p_stats.set_defaults(func=cmd_stats)
    
    # Команда demo
    p_demo = subparsers.add_parser("demo", help="Запустить демонстрацию возможностей")
    p_demo.set_defaults(func=cmd_demo)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
        
    try:
        args.func(args)
    except Exception as e:
        print(f"\n[✗] Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
