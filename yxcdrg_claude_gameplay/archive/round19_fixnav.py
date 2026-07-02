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

def where_am_i(s):
    """Get current location using keyword matching on full look output."""
    b = send(s, b"look\r\n", quiet=2.0)
    t = clean(b)

    # Map of keywords -> location names
    locations = [
        ("南城客栈", "kezhan"),
        ("十字街头", "shizikou"),
        ("天监台", "tianjiantai"),
        ("朱雀大街", "zhuque"),
        ("白虎大街", "baihu"),
        ("青龙大街", "qinglong"),
        ("玄武大街", "xuanwu"),
        ("长安武馆", "wuguan"),
        ("兵器铺", "weaponshop"),
        ("董记当铺", "dangpu"),
        ("国子监", "guozijian"),
        ("化生寺", "huasheng"),
        ("三联书局", "bookshop"),
        ("相记钱庄", "bank"),
        ("方丈室", "fangzhang"),
        ("大雄宝殿", "temple"),
        ("南城口", "southgate"),
        ("泾水", "river"),
        ("背阴巷", "beiyin"),
        ("小酒馆", "bar"),
        ("民居", "minju"),
    ]

    for keyword, name in locations:
        if keyword in t:
            return name, t, b

    return "unknown", t, b

def go_to(s, target):
    """Navigate to target location step by step."""
    max_steps = 12
    for step in range(max_steps):
        loc, desc, _ = where_am_i(s)
        if loc == target:
            print(f"  >> Arrived at {target}!")
            return True

        # Navigation table: (current, target) -> direction
        # This encodes the city map
        moves = {
            # To shizikou (hub)
            ("kezhan", "shizikou"): "west north",
            ("zhuque", "shizikou"): "north",
            ("baihu", "shizikou"): "east",
            ("qinglong", "shizikou"): "west",
            ("xuanwu", "shizikou"): "south",
            ("dangpu", "shizikou"): "east north",
            ("tianjiantai", "shizikou"): "east south",
            ("wuguan", "shizikou"): "south west",
            ("weaponshop", "shizikou"): "north west",
            ("guozijian", "shizikou"): "west south",
            ("huasheng", "shizikou"): "north east",
            ("bank", "shizikou"): "north east",
            ("bookshop", "shizikou"): "south east",
            ("fangzhang", "shizikou"): "west north east",
            ("temple", "shizikou"): "north north east",
            ("southgate", "shizikou"): "north north north",
            ("river", "shizikou"): "north north north north",

            # To tianjiantai (yuan)
            ("shizikou", "tianjiantai"): "north west",
            ("xuanwu", "tianjiantai"): "west",

            # To weaponshop
            ("shizikou", "weaponshop"): "east south",
            ("qinglong", "weaponshop"): "south",
            ("wuguan", "weaponshop"): "south south",

            # To wuguan
            ("shizikou", "wuguan"): "east north",
            ("qinglong", "wuguan"): "north",

            # To kezhan
            ("shizikou", "kezhan"): "south east",
            ("zhuque", "kezhan"): "east",
            ("dangpu", "kezhan"): "east east",
        }

        # Find path: try direct, then via shizikou
        key = (loc, target)
        if key in moves:
            dirs = moves[key].split()
            for d in dirs:
                send(s, d.encode() + b"\r\n", quiet=1.5)
                print(f"  {loc} -> {d}")
        elif loc != "shizikou":
            # Go to shizikou first
            key2 = (loc, "shizikou")
            if key2 in moves:
                dirs = moves[key2].split()
                for d in dirs:
                    send(s, d.encode() + b"\r\n", quiet=1.5)
                    print(f"  {loc} -> {d} (via hub)")
            else:
                print(f"  !! Don't know how to leave {loc}, trying south")
                send(s, b"south\r\n", quiet=1.5)
        else:
            print(f"  !! Don't know path from {loc} to {target}")
            return False

    return False

print("Round 19: Fixed navigation + Yuan mission!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
resp = clean(b)
if "y/n" in resp:
    b = send(s, b"y\r\n", quiet=4.0)

send(s, b"set wimpy 15\r\n", quiet=1.0)

# ============================================
# STEP 1: Ask Yuan about kill
# ============================================
print("\n========== STEP 1: ASK YUAN ==========")
loc, desc, b = where_am_i(s)
print(f"  Starting at: {loc}")

go_to(s, "tianjiantai")
loc, desc, b = where_am_i(s)
show("AT YUAN?", b)

b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
yuan_resp = clean(b)
show("YUAN MISSION", b)

# Parse monster
monster_match = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan_resp)
monster_name = monster_match.group(1) if monster_match else None
monster_id = monster_match.group(2).strip().lower() if monster_match else None
monster_location = monster_match.group(3) if monster_match else None

if monster_name:
    print(f"\n  MONSTER: {monster_name} (ID: {monster_id})")
    print(f"  LOCATION: {monster_location}")
else:
    # Yuan might be saying "go do the previous one"
    print(f"  Yuan response: {yuan_resp[:200]}")

# ============================================
# STEP 2: Buy weapon
# ============================================
print("\n========== STEP 2: GEAR UP ==========")
go_to(s, "weaponshop")
loc, desc, b = where_am_i(s)
show("AT SHOP?", b)

if loc == "weaponshop":
    b = send(s, b"buy blade from xiao xiao\r\n", quiet=2.0)
    show("BUY", b)
    b = send(s, b"wield blade\r\n", quiet=2.0)
    show("WIELD", b)

b = send(s, b"score\r\n", quiet=3.0)
show("COMBAT STATS", b)

# ============================================
# STEP 3: Search for monster in city area
# ============================================
print("\n========== STEP 3: SEARCH ==========")
if monster_id:
    # Go to hub first
    go_to(s, "shizikou")

    # Systematic search of city rooms
    search_path = [
        "south",  # zhuque
        "south",  # zhuque-s2
        "south",  # zhuque-s3
        "south",  # zhuque-s4
        "west",   # beiyin5
        "northwest",  # beiyin4
        "west",   # beiyin3
        "north",  # beiyin2
        "northwest",  # beiyin1
        "south",  # back to baihu area
        "east",   # baihu-w2
        "east",   # baihu-w1/shizikou
        "north",  # xuanwu
        "east",   # guozijian
        "west",   # xuanwu
        "west",   # tianjiantai
        "east",   # xuanwu
        "south",  # shizikou
        "east",   # qinglong-e1
        "east",   # qinglong-e2
        "east",   # qinglong-e3
        "west", "west", "west",  # back to shizikou
        "south",  # zhuque
        "east",   # kezhan
        "west",   # zhuque
        "west",   # dangpu
    ]

    found = False
    mid = monster_id.split()[0].lower()
    for d in search_path:
        send(s, d.encode() + b"\r\n", quiet=1.5)
        b = send(s, b"look\r\n", quiet=1.5)
        desc = clean(b)
        if mid in desc.lower() or (monster_name and monster_name in desc):
            print(f"\n  ** FOUND {monster_name} HERE! **")
            show("MONSTER ROOM", b)
            found = True

            # KILL IT
            print(f"\n  >> KILLING {mid}!")
            b = send(s, f"kill {mid}\r\n".encode(), quiet=2.0)
            r = clean(b)
            if "想攻击谁" in r or "没有" in r:
                b = send(s, f"fight {mid}\r\n".encode(), quiet=2.0)
                r = clean(b)

            show("ATTACK", b)

            killed = False
            for i in range(30):
                time.sleep(3)
                b = drain(s, quiet=2.0, maxt=5.0)
                if b:
                    r = clean(b)
                    if "死了" in r or "服了" in r or "投降" in r or "青烟" in r or "原形" in r or "领罪" in r:
                        show("*** VICTORY! ***", b)
                        killed = True
                        break
                    elif "承让" in r:
                        show("LOST", b)
                        break
                    elif "找机会逃跑" in r:
                        show("FLED", b)
                        break
                    elif i % 5 == 0:
                        show(f"COMBAT {i+1}", b)

            if killed:
                print("\n  ************************************")
                print("  *** YUAN MISSION COMPLETE!!! ***")
                print("  ************************************")
                time.sleep(2)
                b = drain(s, quiet=2.0, maxt=4.0)
                if b: show("REWARD", b)
            break

    if not found:
        print(f"\n  Monster '{monster_name}' ({monster_id}) not found in city search")
        print(f"  Location hint: {monster_location}")

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

print("\n*** Round 19 ended - NO QUIT ***")
time.sleep(1)
s.close()
