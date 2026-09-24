#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 7: Industrial protocols."""
from inevionet import InevioNet
from inevionet.industrial import (
    ModbusTCP, ModbusRTU, OPCUA, MQTTClient, DNP3)


def main():
    print("=" * 60)
    print("  EXAMPLE 7: INDUSTRIAL PROTOCOLS")
    print("=" * 60)
    print()

    net = InevioNet("industrial_password", node_id="plc_gateway", auto_start=True)

    # 1. Modbus
    print("1. Modbus TCP:")
    modbus = ModbusTCP("192.168.1.100", 502)
    packet = modbus.wrap_for_inevionet(
        function_code=0x03,
        slave=1,
        address=0,
        count=10)
    print(f"   Packet: {packet}")
    print(f"   Metadata: {packet.metadata}")
    success = net.send("plc_controller", packet.to_bytes())
    print(f"   Sent: {success}")
    print()

    # 2. Modbus RTU
    print("2. Modbus RTU:")
    rtu = ModbusRTU()
    request = rtu.encode(0x03, slave=1, address=0, count=10)
    print(f"   RTU request: {request.hex()}")
    print()

    # 3. OPC UA
    print("3. OPC UA:")
    opcua = OPCUA("opc.tcp://192.168.1.100:4840")
    packet = opcua.read_node("ns=2;s=Temperature")
    print(f"   Packet: {packet}")
    print()

    # 4. MQTT
    print("4. MQTT:")
    mqtt = MQTTClient("test.mosquitto.org", 1883)
    packet = mqtt.publish("sensors/temp", "25.5", qos=1)
    print(f"   Publish packet: {packet}")
    packet = mqtt.subscribe("sensors/#", qos=1)
    print(f"   Subscribe packet: {packet}")
    print()

    # 5. DNP3
    print("5. DNP3:")
    dnp3 = DNP3("192.168.1.100", 20000)
    packet = dnp3.read(address=0, count=10)
    print(f"   Read packet: {packet}")
    print(f"   HEX: {packet.data.hex()}")
    print()

    # 6. Send all via InevioNet
    print("6. Sending all via InevioNet:")
    protocols = [
        ("Modbus", modbus.wrap_for_inevionet(0x03, slave=1, address=0, count=10)),
        ("OPC UA", opcua.read_node("ns=2;s=Temperature")),
        ("MQTT", mqtt.publish("sensors/temp", "25.5")),
        ("DNP3", dnp3.read(address=0, count=10)),
    ]
    for name, pkt in protocols:
        success = net.send("industrial_target", pkt.to_bytes())
        status = "OK" if success else "FAIL"
        print(f"   [{status}] {name}")
    print()

    net.stop()
    print("=" * 60)


if __name__ == "__main__":
    main()
