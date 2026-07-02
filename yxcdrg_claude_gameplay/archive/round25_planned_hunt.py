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
    return clean(send(s, d.encode() + b"\r\n", quiet=1.0))

def look(s):
    b = send(s, b"look\r\n", quiet=1.5)
    return clean(b), b

def is_monster(desc, monster_name, monster_id):
    """Check if monster NPC is in room description - only match NPC lines."""
    skip_list = ["Board","paizi","sign","Agenta","Snoopl","Snoopy","Xiao er",
        "Da ye","Qianli","Dong push","Fan luping","Wuguan dizi","Xiao xiao",
        "Yuan tiangang","Li bai","Zhang guolao","Jieding","Xiucai","Kong fang",
        "Tie suanpan","Faming","Monk","Heshang","Wu jiang","Xiao bing",
        "Laitou","maolu","Wei shi","Kuli","Jia er","Xiao maolu","Zodiac"]
    for line in desc.split("\n"):
        line = line.strip()
        if "(" not in line or ")" not in line:
            continue
        if any(skip in line for skip in skip_list):
            continue
        # This is an unrecognized NPC - could be our monster
        if monster_name and monster_name in line:
            m = re.search(r'\(([^)]+)\)', line)
            return True, m.group(1).strip().split()[0].lower() if m else None
        if monster_id and monster_id.lower() in line.lower():
            m = re.search(r'\(([^)]+)\)', line)
            return True, m.group(1).strip().split()[0].lower() if m else None
    return False, None

def fight(s, kill_id):
    """Kill the monster. Returns True if killed."""
    print(f"  >> kill {kill_id}")
    r = go(s, f"kill {kill_id}")
    if "想攻击谁" in r or "没有" in r:
        r = go(s, f"fight {kill_id}")
    if not any(w in r for w in ["喝道","想杀","领教","奉陪"]):
        print(f"  !! Can't engage. Response: {r[:100]}")
        return False
    print("  >> FIGHTING!")
    for j in range(40):
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
            elif j % 6 == 0:
                # Show brief combat status
                lines = [l.strip() for l in r.split("\n") if l.strip() and ">" not in l]
                if lines:
                    print(f"  [combat {j}] {lines[-1][:60]}")
    return False

# ============================================
# CONNECT AND LOGIN
# ============================================
print("Round 25: PLANNED hunt with verified map routes!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
if "y/n" in clean(b):
    send(s, b"y\r\n", quiet=4.0)

send(s, b"set wimpy 15\r\n", quiet=1.0)

# ============================================
# STEP 1: Get to kezhan (known reference point)
# Look where we are, navigate to kezhan step by step
# ============================================
print("\n========== STEP 1: GET TO KEZHAN (reference) ==========")
desc, b = look(s)
print(f"  Starting room: {desc[:40].strip()}")

# Hardcoded escape from any known room to kezhan
# Strategy: get to zhuque first, then east to kezhan
for attempt in range(15):
    desc, b = look(s)
    if "南城客栈" in desc:
        print("  >> AT KEZHAN!")
        break
    elif "朱雀大街" in desc and "客栈" in desc:
        go(s, "east")  # zhuque (kezhan level) -> kezhan
    elif "朱雀大街" in desc:
        go(s, "north")  # try to get to kezhan-level zhuque
    elif "十字街头" in desc:
        go(s, "south"); go(s, "east")
    elif "白虎大街" in desc:
        go(s, "east")
    elif "青龙大街" in desc:
        go(s, "west")
    elif "玄武大街" in desc:
        go(s, "south"); go(s, "south"); go(s, "east")
    elif "天监台" in desc:
        go(s, "east"); go(s, "south"); go(s, "south"); go(s, "east")
    elif "武馆" in desc:
        go(s, "south"); go(s, "west"); go(s, "south"); go(s, "east")
    elif "兵器铺" in desc:
        go(s, "north"); go(s, "west"); go(s, "south"); go(s, "east")
    elif "当铺" in desc:
        go(s, "east"); go(s, "east")
    elif "南城口" in desc:
        go(s, "north"); go(s, "north"); go(s, "north"); go(s, "east")
    elif "开封" in desc or "辰龙" in desc or "汴京" in desc or "舜王" in desc:
        # In kaifeng, go west repeatedly to get back
        for _ in range(15): go(s, "west")
        for _ in range(4): go(s, "west")  # through dongmen back to shizikou area
    elif "东门" in desc:
        for _ in range(4): go(s, "west")
        go(s, "south"); go(s, "east")
    elif "朝阳门" in desc:
        go(s, "south"); go(s, "south"); go(s, "east")
    elif "国子监" in desc:
        go(s, "west"); go(s, "south"); go(s, "south"); go(s, "east")
    elif "化生寺" in desc or "方丈" in desc or "大雄" in desc:
        for _ in range(3): go(s, "north")
        go(s, "east")
    else:
        go(s, "south")  # generic fallback

desc, b = look(s)
show("AT KEZHAN", b)

# ============================================
# STEP 2: Ensure weapon equipped
# ============================================
print("\n========== STEP 2: WEAPON CHECK ==========")
b2 = send(s, b"i\r\n", quiet=2.0)
inv = clean(b2)
if "钢刀" not in inv:
    print("  No blade! Buying...")
    # kezhan -> west(zhuque) -> north(shizikou) -> east(qinglong) -> south(weaponshop)
    go(s, "west"); go(s, "north"); go(s, "east"); go(s, "south")
    desc, _ = look(s)
    if "兵器" in desc:
        send(s, b"buy blade from xiao xiao\r\n", quiet=1.5)
        send(s, b"wield blade\r\n", quiet=1.5)
        print("  Blade purchased and wielded!")
    # Go back to kezhan: north(qinglong) -> west(shizikou) -> south(zhuque) -> east(kezhan)
    go(s, "north"); go(s, "west"); go(s, "south"); go(s, "east")
else:
    print("  Blade in inventory!")
    if "□钢刀" not in inv:
        send(s, b"wield blade\r\n", quiet=1.0)

b2 = send(s, b"score\r\n", quiet=3.0)
show("COMBAT STATS", b2)

# ============================================
# STEP 3: Go to Yuan and get mission
# kezhan -> west(zhuque) -> north(shizikou) -> north(xuanwu) -> west(tianjiantai)
# ============================================
print("\n========== STEP 3: ASK YUAN ==========")
go(s, "west"); go(s, "north"); go(s, "north"); go(s, "west")
desc, b = look(s)
show("AT YUAN?", b)

if "天监台" not in desc:
    print("  !! NOT at tianjiantai! Aborting.")
else:
    b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
    yuan = clean(b)
    show("YUAN MISSION", b)

    monster_name = None
    monster_id = None
    location = None

    m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
    if m:
        monster_name = m.group(1)
        monster_id = m.group(2).strip().split()[0].lower()
        location = m.group(3)
    elif "收服" in yuan:
        m2 = re.search(r'收服(.+?)吗', yuan)
        if m2:
            monster_name = m2.group(1)
            monster_id = "guai"
    elif "除尽" in yuan:
        b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
        yuan = clean(b)
        m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
        if m:
            monster_name = m.group(1)
            monster_id = m.group(2).strip().split()[0].lower()
            location = m.group(3)

    print(f"\n  MONSTER: {monster_name}")
    print(f"  ID: {monster_id}")
    print(f"  LOCATION: {location}")

    if monster_name:
        # ============================================
        # STEP 4: Navigate to monster's area
        # From tianjiantai -> east(xuanwu) -> south(shizikou) -> then to area
        # ============================================
        print(f"\n========== STEP 4: GO TO {location} ==========")
        go(s, "east"); go(s, "south")  # back to shizikou
        desc, _ = look(s)
        if "十字" not in desc:
            print(f"  !! Not at shizikou: {desc[:40]}")

        search_dirs = []

        if location and "开封" in location:
            print("  Route: shizikou → dongmen → kaifeng → 御相府 area (19 moves)")
            # Exact verified route from map.md
            travel = ["east"]*4 + ["east"] + ["east"]*4 + ["east"] + ["east","east","east"]
            for d in travel:
                go(s, d)
            go(s, "northwest")  # tieta -> shun5
            # Search all shun streets + side rooms
            search_dirs = [
                "north","north","north","north",  # shun5->shun1
                "west",  # side room
                "east",  # back
                "south",  # shun2
                "west",  # yuxiangfu!
                "east",  # back
                "south","south",  # shun4,shun5
                "southeast",  # back to tieta
                "south",  # yao streets
                "south","south","south",
                "east","west",
                "north","north","north","north",
                "northeast",  # try other direction from tieta
                "east","west",
            ]

        elif location and ("长安" in location or "城" in location):
            if "望南" in location or "东" in location:
                print("  Route: shizikou → qinglong-e3 → wangnan area")
                go(s, "east"); go(s, "east"); go(s, "east"); go(s, "south")
                search_dirs = [
                    "southwest","south","west","southwest",  # wangnan 2,3,4,5
                    "northeast","east","north","northeast",  # back up
                    "east","west",  # huohang
                ]
            else:
                print("  Route: search all city streets from shizikou")
                search_dirs = [
                    "south","east","west",  # zhuque, kezhan, back
                    "west",  # dangpu
                    "east","south","east","west",  # zhuque-s2
                    "south","south",  # zhuque-s3,s4
                    "north","north","north",  # back
                    "east","north","south","south","north","west",  # qinglong, wuguan
                    "west","south","east","south",  # baihu, beiyin
                    "north","east","north",  # back
                    "north","east","west","south",  # xuanwu, guozijian
                ]
        else:
            print(f"  Unknown area: {location}, searching city")
            search_dirs = [
                "south","east","west","south","south","south",
                "east","northeast","east","north","northeast",
                "north","west","west","north","south","south","north","west",
                "west","south","north","west","south","north","east","east",
                "north","east","west","south",
            ]

        # ============================================
        # STEP 5: Search rooms for monster
        # ============================================
        print(f"\n========== STEP 5: SEARCHING ({len(search_dirs)} rooms) ==========")
        found = False
        for i, d in enumerate(search_dirs):
            go(s, d)
            desc, b = look(s)
            f, kid = is_monster(desc, monster_name, monster_id)
            if f:
                print(f"\n  ** FOUND {monster_name} at step {i}! ID: {kid} **")
                show("MONSTER!", b)
                found = True
                killed = fight(s, kid)
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
            print(f"\n  !! {monster_name} not found in {len(search_dirs)} rooms")

# ============================================
# FINAL STATUS
# ============================================
print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)
b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS", b)

print("\n*** Round 25 ended - NO QUIT ***")
time.sleep(1)
s.close()
