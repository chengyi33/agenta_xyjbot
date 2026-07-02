import sys
from xyjbot import raw_login, m, drain, clean, look_and_id
from xyjmap import XYJMap
sys.stdout.reconfigure(encoding="utf-8")
M = XYJMap()
s = raw_login(M)
print("=== LOOK ===")
print(m(s, "look", q=1.5))
print("=== INVENTORY ===")
print(m(s, "i", q=1.5))
print("=== SCORE (gear/money) ===")
sc = m(s, "score", q=2.5)
for ln in sc.split("\n"):
    if any(k in ln for k in ("兵器","盔甲","两","文","钱","银")):
        print("  ", ln.strip())
print("=== done (socket left open, NO quit) ===")
s.close()
