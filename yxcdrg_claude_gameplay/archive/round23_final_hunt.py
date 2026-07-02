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
    """Check if monster NPC is in room. Only match NPC lines with (id)."""
    for line in desc.split("\n"):
        line = line.strip()
        # NPC lines have format: Chinese_Name(English_id)
        if "(" in line and ")" in line:
            # Skip known non-monster NPCs and room items
            if any(skip in line for skip in ["Board","paizi","sign","Agenta","Snoopl","Snoopy"]):
                continue
            # Check if this NPC matches our target
            if monster_name and monster_name in line:
                m = re.search(r'\(([^)]+)\)', line)
                return True, m.group(1).strip().split()[0].lower() if m else monster_id
            if monster_id and monster_id in line.lower():
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
        if "望南街" in t or "货行" in t: go(s,"north"); continue
        if "进士场" in t: go(s,"east"); go(s,"north"); continue
        if "大官道" in t: go(s,"north"); continue
        if "国子监" in t: go(s,"west"); go(s,"south"); continue
        if "化生寺" in t or "方丈" in t or "大雄" in t:
            go(s,"north"); go(s,"east"); continue
        if "钱庄" in t: go(s,"north"); go(s,"east"); continue
        if "书局" in t: go(s,"south"); go(s,"east"); continue
        if "南城口" in t: go(s,"north"); go(s,"north"); go(s,"north"); continue
        if "泾水" in t: go(s,"north"); continue
        if "背阴" in t or "小酒馆" in t: go(s,"east"); go(s,"north"); continue
        if "碑林" in t: go(s,"south"); continue
        if "开封" in t or "辰龙" in t or "汴京" in t:
            go(s,"west"); continue  # try to get back
        if "东门" in t or "dongmen" in t.lower():
            go(s,"west"); continue
        go(s, "north")
    return False

def search_area(s, directions, monster_name, monster_id):
    """Search rooms following direction list. Returns (found, kill_id) or (False, None)."""
    for i, d in enumerate(directions):
        go(s, d)
        b = send(s, b"look\r\n", quiet=0.8)
        desc = clean(b)
        found, kill_id = is_monster_here(desc, monster_name, monster_id)
        if found:
            print(f"\n  ** FOUND {monster_name} at step {i}! ID: {kill_id} **")
            show("MONSTER ROOM", b)
            return True, kill_id
    return False, None

def fight_monster(s, kill_id):
    """Fight and try to kill the monster. Returns True if killed."""
    b = send(s, f"kill {kill_id}\r\n".encode(), quiet=2.0)
    r = clean(b)
    if "想攻击谁" in r or "没有" in r:
        # Try alternate
        b = send(s, f"fight {kill_id}\r\n".encode(), quiet=2.0)
        r = clean(b)
    show("ATTACK!", b)

    if "喝道" not in r and "想杀" not in r and "领教" not in r and "奉陪" not in r:
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

# ============================================
# START
# ============================================
print("Round 23: FINAL HUNT with proper monster detection!")
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
inv = clean(b)
if "钢刀" not in inv:
    go_to_hub(s)
    go(s,"east"); go(s,"south")
    send(s, b"buy blade from xiao xiao\r\n", quiet=1.5)
    send(s, b"wield blade\r\n", quiet=1.5)

# ============================================
# ASK YUAN
# ============================================
print("\n========== ASK YUAN ==========")
go_to_hub(s)
go(s,"north"); go(s,"west")  # tianjiantai
b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
yuan = clean(b)
show("YUAN", b)

# Parse
monster_name = None
monster_id = None
location = None

m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
if m:
    monster_name = m.group(1)
    monster_id = m.group(2).strip().split()[0].lower()
    location = m.group(3)
else:
    m2 = re.search(r'收服(.+?)吗', yuan)
    if m2:
        monster_name = m2.group(1)
        monster_id = "guai"  # will need to find real ID in room

if "除尽" in yuan:
    # Previous mission done, get new one
    b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
    yuan = clean(b)
    show("YUAN NEW", b)
    m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
    if m:
        monster_name = m.group(1)
        monster_id = m.group(2).strip().split()[0].lower()
        location = m.group(3)

print(f"  Monster: {monster_name}, ID: {monster_id}, Location: {location}")

# ============================================
# NAVIGATE TO AREA AND SEARCH
# ============================================
print("\n========== HUNT! ==========")

# Go back to hub
go(s,"east"); go(s,"south")

if location and "开封" in location:
    # Navigate to Kaifeng: shizikou -> east x4 (dongmen) -> east (kaifeng)
    print("  >> Target in 开封城! Navigating...")
    go(s,"east"); go(s,"east"); go(s,"east"); go(s,"east")  # dongmen
    go(s,"east")  # kaifeng/east1

    # Search kaifeng streets
    kaifeng_search = [
        "east",  # east2/gate area
        "east",  # chenlong
        "east",  # chenlong2
        "east",  # bianjing tower area
        "north", # shunwang street
        "north", "north", "north", "north",  # up shunwang
        "east",  # yuxiangfu area!
        "west",  # back
        "south", "south", "south", "south",  # back to tower
        "south", # yaowang street
        "south", "south",  # more yaowang
        "east",  # side streets
        "west",
        "north", "north", "north",  # back to tower
        "east",  # urao street
        "north", "north", "north", "north",
        "south", "south", "south", "south",
        "west",  # back
        "northwest",  # guting area
        "north", "north",
        "south", "south",
        "east", "east",
        "west", "west",
        "south",
    ]
    found, kill_id = search_area(s, kaifeng_search, monster_name, monster_id)

elif location and ("长安" in location or "city" in (location or "").lower()):
    # Search Chang'an
    print("  >> Target in 长安城! Searching...")
    city_search = [
        "south","east","west",  # zhuque, kezhan, back
        "south","south","south",  # south zhuque
        "east","northeast","east","north","northeast",  # eastway/wangnan
        "east","west","north",  # huohang, back, qinglong-e3
        "west","west","north","south","south","north",  # qinglong, wuguan, weaponshop
        "west",  # shizikou
        "west","south","east","south","south","east","southeast","south",  # west city
        "north","east","north","north","north","east",  # back
        "north","east","west","south",  # xuanwu, guozijian
    ]
    found, kill_id = search_area(s, city_search, monster_name, monster_id)

else:
    # Unknown area, search city anyway
    print(f"  >> Unknown area '{location}', searching city...")
    city_search = [
        "south","east","west","south","south","south",
        "east","northeast","east","north","northeast","east","west","north",
        "west","west","north","south","south","north","west",
        "west","south","east","south","south","east","southeast","south",
        "north","east","north","north","north","east",
        "north","east","west","south",
    ]
    found, kill_id = search_area(s, city_search, monster_name, monster_id)

if found and kill_id:
    killed = fight_monster(s, kill_id)
    if killed:
        print("\n  ********************************************")
        print("  ***    FIRST KILL!!!                     ***")
        print("  ***    YUAN MISSION COMPLETE!!!          ***")
        print("  ********************************************")
        time.sleep(3)
        b = drain(s, quiet=2.0, maxt=5.0)
        if b: show("AFTERMATH", b)

        go_to_hub(s)
        go(s,"north"); go(s,"west")
        b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
        show("YUAN REPORT", b)
elif not found:
    print(f"\n  !! {monster_name} not found in search")

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

print("\n*** Round 23 ended - NO QUIT ***")
time.sleep(1)
s.close()
