# test_ai.py
from inevionet.ai.selector import ProtocolSelector
from inevionet.ai.recursion import WeightedRecursion

print("=== ProtocolSelector test ===")
s = ProtocolSelector()
print("Initial select:", s.select())

# Correct call: record_success(receiver, protocol)
for i in range(5):
    s.record_success("example.com", "HTTPS")
for i in range(3):
    s.record_success("example.com", "DNS")
s.record_failure("example.com", "ICMP")

print("After training:")
print("  select():", s.select("example.com"))
print("  top-3:", s.select_top_n("example.com", 3))
print("  stats:", s.get_stats())

print()
print("=== WeightedRecursion test ===")
r = WeightedRecursion(max_depth=5, probability_threshold=0.95)

alternatives = [
    {"name": "HTTPS", "metrics": {"reliability": 0.9, "speed": 0.6, "stealth": 0.6}},
    {"name": "DNS",   "metrics": {"reliability": 0.7, "speed": 0.5, "stealth": 0.95}},
    {"name": "ICMP",  "metrics": {"reliability": 0.5, "speed": 0.6, "stealth": 0.9}},
]

def try_func(alt, depth):
    print(f"  Trying: {alt['name']} (depth={depth})")
    return alt['name'] == 'HTTPS', 0.9

result = r.execute(alternatives=alternatives, try_func=try_func)
print("Result:", result)
print("Stats:", r.get_stats())
