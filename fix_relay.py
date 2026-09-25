# fix_relay.py
import re
import sys

PATH = r"E:\InevioNet\inevionet\orchestrator.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

# Backup
with open(PATH + ".bak_before_relay", "w", encoding="utf-8") as f:
    f.write(content)

print(f"Backup: {PATH}.bak_before_relay")
print(f"Original size: {len(content)} bytes")

# === 1. Patch try_delivery ===
if "# P13: try relay chain first" in content:
    print("[--] try_delivery already patched")
else:
    # Find: proto = alt["protocol"] inside try_delivery
    pattern = r'(        def try_delivery\(alt, depth\):\n            proto = alt\["protocol"\]\n)'
    match = re.search(pattern, content)
    
    if match:
        insert_after = match.end()
        
        chain_code = (
            "                # P13: try relay chain first\n"
            "                if proto not in ('I2P', 'MQTT', 'MODBUS', 'DNP3', 'OPCUA'):\n"
            "                    try:\n"
            "                        chain_ok, chain_path = self._try_relay_chain(packet, receiver)\n"
            "                        if chain_ok:\n"
            "                            if self.evolution:\n"
            "                                self.evolution.reward('protocol', proto, True)\n"
            "                            return True, 0.95\n"
            "                    except Exception as _ce:\n"
            "                        logger.debug('[Relay] chain try error: %s', _ce)\n"
        )
        
        content = content[:insert_after] + chain_code + content[insert_after:]
        print("[OK] try_delivery patched")
    else:
        print("[!!] try_delivery pattern NOT found")

# === 2. Patch receive() ===
if "# P13: should I relay" in content:
    print("[--] receive() already patched")
else:
    # Find: if not packet: return False, None inside receive
    pattern = r'(    def receive\(self, packet_data\):.*?if not packet: return False, None\n)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        insert_after = match.end()
        
        relay_code = (
            "\n"
            "            # P13: should I relay?\n"
            "            try:\n"
            "                if packet.should_relay(self.node_id):\n"
            "                    logger.info('[Relay] relay request %s (hop %d/%d)',\n"
            "                                packet.packet_id[:16],\n"
            "                                packet.hop_count,\n"
            "                                packet.max_hops)\n"
            "                    packet.add_hop(self.node_id)\n"
            "                    packet.mark_relayed(self.node_id)\n"
            "                    self._forward_packet(packet, packet.route_to)\n"
            "                    return True, None\n"
            "            except Exception as _re:\n"
            "                logger.debug('[Relay] receive check error: %s', _re)\n"
        )
        
        content = content[:insert_after] + relay_code + content[insert_after:]
        print("[OK] receive() patched")
    else:
        print("[!!] receive() pattern NOT found")

# Save
with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print(f"New size: {len(content)} bytes")
print("Saved")

# Syntax check
import ast
try:
    ast.parse(content)
    print("[OK] syntax valid")
except SyntaxError as e:
    print(f"[!!] Syntax error: {e}")
    print(f"    Line {e.lineno}, offset {e.offset}")
    # Restore
    with open(PATH + ".bak_before_relay", "r", encoding="utf-8") as f:
        original = f.read()
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(original)
    print("[!!] restored from backup")
    sys.exit(1)

print("DONE")