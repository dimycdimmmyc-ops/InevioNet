#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 6: Инкапсуляция промышленных протоколов."""
from inevionet import InevioNet
from inevionet.industrial import ModbusTCP, MQTTClient, OPCUA

def main():
    print("=" * 60)
    print(" EXAMPLE 6: INDUSTRIAL PROTOCOLS ENCAPSULATION")
    print("=" * 60)
    
    net = InevioNet(password="industrial_pwd", node_id="plc_gateway", auto_start=True)
    
    try:
        # 1. Modbus TCP
        print("\n[1] Modbus TCP:")
        modbus = ModbusTCP("192.168.1.100", 502)
        packet = modbus.wrap_for_inevionet(function_code=0x03, slave=1, address=0, count=10)
        print(f"    Пакет создан: {len(packet.data)} байт")
        print(f"    Метаданные: {packet.metadata}")

        # 2. MQTT
        print("\n[2] MQTT:")
        mqtt = MQTTClient("test.mosquitto.org", 1883)
        packet = mqtt.publish("sensors/temperature", "25.5", qos=1)
        print(f"    PUBLISH пакет создан: {len(packet.data)} байт")

        # 3. OPC UA
        print("\n[3] OPC UA:")
        opcua = OPCUA("opc.tcp://localhost:4840")
        packet = opcua.read_node("ns=2;s=Temperature")
        print(f"    ReadRequest пакет создан: {len(packet.data)} байт")

        print("\n[+] Все промышленные пакеты готовы к отправке через InevioNet!")

    finally:
        net.stop()

if __name__ == "__main__":
    main()
