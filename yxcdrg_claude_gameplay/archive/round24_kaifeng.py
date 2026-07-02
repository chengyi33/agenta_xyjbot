import socket, time, re, sys
sys.stdout.reconfigure(line_buffering=True)

def drain(s, quiet=1.5, maxt=10.0):
    s.setblocking(False); buf=b""; start=time.time(); last=time.time()
    while True:
        try:
            c=s.recv(4096)
            if c: buf+=c; last=time.time()
            else: break
        except BlockingIOError:
            if buf and (time.time()-last)>quiet: break
            if (time.time()-start)>maxt: break
            time.sleep(0.04)
    return buf

def send(s, d, quiet=2.0):
    s.sendall(d); return drain(s, quiet=quiet)

def clean(b):
    for enc in ["utf-8", "gbk"]:
        try:
            t = b.replace(b"\x00", b"").decode(enc)
            return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", t)
        except:
            pass
    return b.replace(b"\x00", b"").decode("gbk", errors="replace")

def show(label, b):
    t = clean(b)
    print(f"\n--- {label} ---")
    print(t[-2500:] if len(t) > 2500 else t)

def go(s, d):
    return send(s, d.encode() + b"\r\n", quiet=1.0)

def is_monster_here(desc, monster_name, monster_id):
    for line in desc.split("\n"):
        line = line.strip()
        if "(" in line and ")" in line:
            if any(skip in line for skip in ["Board","paizi","sign","Agenta","Snoopl","Snoopy",
                "Xiao er","Da ye","Qianli","Dong push","Fan luping","Wuguan dizi",
                "Xiao xiao","Yuan tiangang","Li bai","Zhang guolao","Jieding",
                "Xiucai","Kong fang","Tie suanpan","Faming","Monk","Heshang",
                "Wu jiang","Xiao bing","Laitou","maolu"]):
                continue
            if monster_name and monster_name in line:
                m = re.search(r'\(([^)]+)\)', line)
                return True, m.group(1).strip().split()[0].lower() if m else monster_id
            if monster_id and monster_id.lower() in line.lower():
                m = re.search(r'\(([^)]+)\)', line)
                return True, m.group(1).strip().split()[0].lower() if m else monster_id
    return False, None

def go_to_hub(s):
    for _ in range(10):
        b = send(s, b"look\r\n", quiet=1.5)
        t = clean(b)
        if "十字街头" in t: return True
        if "南城客栈" in t: go(s,"west"); go(s,"north"); continue
        if "朱雀大街" in t: go(s,"north"); continue
        if "白虎大街" in t: go(s,"east"); continue
        if "青龙大街" in t: go(s,"west"); continue
        if "玄武大街" in t: go(s,"south"); continue
        if "天监台" in t: go(s,"east"); go(s,"south"); continue
        if "武馆" in t: go(s,"south"); go(s,"west"); continue
        if "兵器铺" in t: go(s,"north"); go(s,"west"); continue
        if "当铺" in t: go(s,"east"); go(s,"north"); continue
        if "东门" in t: go(s,"west"); continue
        if "开封" in t or "辰龙" in t or "汴京" in t: go(s,"west"); continue
        if "大官道" in t: go(s,"west"); continue
        if "望南街" in t: go(s,"north"); continue
        go(s, "west")
    return False

def fight_monster(s, kill_id):
    b = send(s, f"kill {kill_id}\r\n".encode(), quiet=2.0)
    r = clean(b)
    if "想攻击谁" in r or "没有" in r:
        b = send(s, f"fight {kill_id}\r\n".encode(), quiet=2.0)
        r = clean(b)
    show("ATTACK!", b)

    if not any(w in r for w in ["喝道","想杀","领教","奉陪"]):
        print(f"  !! Failed to engage {kill_id}")
        return False

    for j in range(35):
        time.sleep(3)
        b = drain(s, quiet=2.0, maxt=5.0)
        if b:
            r = clean(b)
            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                show("**** VICTORY! ****", b)
                return True
            elif "承让" in r:
                show("LOST", b)
                return False
            elif "找机会逃跑" in r:
                show("FLED", b)
                return False
            elif j % 5 == 0:
                show(f"COMBAT {j+1}", b)
    return False

print("Round 24: GO TO KAIFENG AND KILL 野兔精!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
if "y/n" in clean(b):
    send(s, b"y\r\n", quiet=4.0)

send(s, b"set wimpy 15\r\n", quiet=1.0)

# Ensure weapon
b = send(s, b"i\r\n", quiet=2.0)
if "钢刀" not in clean(b):
    go_to_hub(s)
    go(s,"east"); go(s,"south")
    send(s, b"buy blade from xiao xiao\r\n", quiet=1.5)
    send(s, b"wield blade\r\n", quiet=1.5)

# Ask yuan first
print("\n========== ASK YUAN ==========")
go_to_hub(s)
go(s,"north"); go(s,"west")
b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
yuan = clean(b)
show("YUAN", b)

# Parse monster
monster_name = None
monster_id = "yetu"  # default for 野兔精
location = None

m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
if m:
    monster_name = m.group(1)
    monster_id = m.group(2).strip().split()[0].lower()
    location = m.group(3)
    print(f"  NEW: {monster_name} (id: {monster_id}) at {location}")
elif "收服" in yuan:
    m2 = re.search(r'收服(.+?)吗', yuan)
    if m2:
        monster_name = m2.group(1)
        print(f"  EXISTING: {monster_name} (guessing id: {monster_id})")
elif "除尽" in yuan:
    print("  Mission complete! Getting new one...")
    b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
    yuan = clean(b)
    show("YUAN NEW", b)
    m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
    if m:
        monster_name = m.group(1)
        monster_id = m.group(2).strip().split()[0].lower()
        location = m.group(3)

if not monster_name:
    print(f"  !! No mission. Yuan: {yuan[:200]}")

# ============================================
# GO TO KAIFENG
# Path: tianjiantai -> east(xuanwu) -> south(shizikou) -> east x4(dongmen) -> east(kaifeng)
# ============================================
print(f"\n========== GOING TO KAIFENG FOR {monster_name} ==========")
go(s,"east"); go(s,"south")  # back to shizikou

# shizikou -> east -> east -> east -> east -> dongmen -> east -> kaifeng
go(s,"east")   # qinglong-e1
go(s,"east")   # qinglong-e2
go(s,"east")   # qinglong-e3
go(s,"east")   # dongmen
b = send(s, b"look\r\n", quiet=1.5)
show("DONGMEN?", b)

go(s,"east")   # into kaifeng area
b = send(s, b"look\r\n", quiet=1.5)
show("KAIFENG ENTRY", b)

# Search kaifeng systematically
# Map: 开封城门 -> 辰龙道 -> 辰龙道 -> 汴京铁塔
#       |north                                |north: 舜王街 x4 (with 御相府)
#       马场                                  |south: 尧王街 x4
kaifeng_search = [
    "east", "east", "east",  # through 辰龙道 to 汴京铁塔
    # Search 舜王街 (north side) - 御相府 is here
    "north",  # 舜王街1
    "north",  # 舜王街2
    "east",   # maybe 御相府 or side room
    "west",   # back
    "north",  # 舜王街3
    "east",   # maybe side
    "west",   # back
    "north",  # 舜王街4
    "east",   # maybe side
    "west",   # back
    "north",  # 舜王街5 / top
    "south","south","south","south","south",  # back to tower
    # Search 尧王街 (south side)
    "south",  # 尧王街1
    "east",   # side
    "west",   # back
    "south",  # 尧王街2
    "east",   # side
    "west",   # back
    "south",  # 尧王街3
    "east",   # 兰亭府 area
    "east",   # deeper
    "west","west",  # back
    "south",  # 尧王街4
    "east",   # 七里酒楼
    "west",   # back
    "north","north","north","north",  # back to tower
    # Search west side (古亭道)
    "northwest",  # 古亭道
    "north",
    "north",
    "east","west",  # side rooms
    "south","south",
    "east","west",
    "south",
    # Back and check east sides
    "east",
    "north","north",
    "east","west",
    "south","south",
]

found = False
for i, d in enumerate(kaifeng_search):
    go(s, d)
    b = send(s, b"look\r\n", quiet=0.8)
    desc = clean(b)
    f, kid = is_monster_here(desc, monster_name, monster_id)
    if f:
        print(f"\n  ** FOUND {monster_name} at step {i}! ID: {kid} **")
        show("MONSTER!", b)
        found = True
        killed = fight_monster(s, kid)
        if killed:
            print("\n  ********************************************")
            print("  ***    FIRST KILL!!!                     ***")
            print("  ***    YUAN MISSION COMPLETE!!!          ***")
            print("  ********************************************")
            time.sleep(3)
            b = drain(s, quiet=2.0, maxt=5.0)
            if b: show("AFTERMATH", b)
        break

if not found:
    print(f"\n  !! {monster_name} not found in Kaifeng ({len(kaifeng_search)} rooms)")

# ============================================
# FINAL
# ============================================
print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)
b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS", b)

print("\n*** Round 24 ended - NO QUIT ***")
time.sleep(1)
s.close()
