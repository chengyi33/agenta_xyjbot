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

def verified_go(s, direction, expect_keyword):
    """Move, then look and verify keyword is present. Print result."""
    go(s, direction)
    desc, b = look(s)
    ok = expect_keyword in desc
    status = "OK" if ok else "FAIL"
    room = desc.split("\n")[0].strip()[:30] if desc else "?"
    print(f"  {direction:12s} -> [{status}] {room}")
    return ok, desc, b

def is_monster(desc, monster_name, monster_id):
    """Only match NPC lines (lines with parenthesized ID), skip known NPCs."""
    known = ["Board","paizi","sign","Agenta","Snoopl","Snoopy","Xiao er",
        "Da ye","Qianli","Dong push","Fan luping","Wuguan dizi","Xiao xiao",
        "Yuan tiangang","Li bai","Zhang guolao","Jieding","Xiucai","Kong fang",
        "Tie suanpan","Faming","Monk","Heshang","Wu jiang","Xiao bing",
        "Laitou","maolu","Wei shi","Kuli","Jia er","Xiao maolu","Zodiac",
        "Yang zhong","Biao","Lao","Xiao liu","Xiao pizi","Gong","Sen",
        "Hai","Chen","Xu","Ye","Yin","Zu","People","Horse","Maguan"]
    for line in desc.split("\n"):
        line = line.strip()
        if "(" not in line or ")" not in line:
            continue
        if any(k in line for k in known):
            continue
        # Unknown NPC - check if it matches our target
        if monster_name and monster_name in line:
            m = re.search(r'\(([^)]+)\)', line)
            return True, m.group(1).strip().split()[0].lower() if m else monster_id
        if monster_id and monster_id.lower() in line.lower():
            m = re.search(r'\(([^)]+)\)', line)
            return True, m.group(1).strip().split()[0].lower() if m else monster_id
    return False, None

def fight(s, kill_id):
    """Kill monster. Returns True if killed."""
    print(f"  >> kill {kill_id}")
    r = go(s, f"kill {kill_id}")
    if "想攻击谁" in r or "没有" in r:
        r = go(s, f"fight {kill_id}")
    if not any(w in r for w in ["喝道","想杀","领教","奉陪"]):
        print(f"  !! Can't engage: {r[:80]}")
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
                print("  >> LOST (opponent won)")
                return False
            elif "找机会逃跑" in r:
                print("  >> FLED (wimpy)")
                return False
            elif j % 6 == 0:
                lines = [l.strip() for l in r.split("\n") if l.strip() and ">" not in l]
                if lines: print(f"  [combat {j}] {lines[-1][:60]}")
    return False

# ============================================
# CONNECT
# ============================================
print("Round 26: Verified step-by-step navigation!")
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
# STEP 1: Get to 十字街头 (verified step by step)
# ============================================
print("\n========== STEP 1: Navigate to 十字街头 ==========")
desc, b = look(s)
room1 = desc.split("\n")[0].strip()[:40]
print(f"  Starting at: {room1}")

# Keep trying to reach shizikou with verification
for attempt in range(20):
    desc, b = look(s)
    if "十字街头" in desc:
        print("  >> AT 十字街头! (verified)")
        break
    # Try directions based on keywords in FULL description
    if "南城客栈" in desc:
        verified_go(s, "west", "朱雀")
        verified_go(s, "north", "十字")
    elif "朱雀大街" in desc:
        if "客栈" in desc:  # zhuque-s1 level
            verified_go(s, "north", "十字")
        else:
            verified_go(s, "north", "")  # go north, check after
    elif "白虎大街" in desc:
        verified_go(s, "east", "")
    elif "青龙大街" in desc:
        verified_go(s, "west", "")
    elif "玄武大街" in desc:
        verified_go(s, "south", "十字")
    elif "天监台" in desc:
        verified_go(s, "east", "玄武")
    elif "当铺" in desc:
        verified_go(s, "east", "朱雀")
    elif "武馆" in desc:
        verified_go(s, "south", "青龙")
    elif "兵器铺" in desc:
        verified_go(s, "north", "青龙")
    elif "药铺" in desc or "回春" in desc:
        verified_go(s, "west", "朱雀")
    elif "南城口" in desc:
        verified_go(s, "north", "")
    elif "东门" in desc:
        verified_go(s, "west", "")
    elif "朝阳门" in desc:
        verified_go(s, "south", "玄武")
    elif "国子监" in desc:
        verified_go(s, "west", "玄武")
    elif "化生寺" in desc:
        verified_go(s, "north", "白虎")
    elif "方丈" in desc or "大雄" in desc:
        verified_go(s, "west", "")
        verified_go(s, "north", "")
    elif "书局" in desc or "三联" in desc:
        verified_go(s, "south", "白虎")
    elif "钱庄" in desc:
        verified_go(s, "north", "白虎")
    elif "背阴" in desc:
        verified_go(s, "north", "")  # or east
    elif "小酒馆" in desc:
        verified_go(s, "south", "")
    elif "开封" in desc or "辰龙" in desc or "汴京" in desc or "舜王" in desc:
        verified_go(s, "west", "")
    elif "乐坊" in desc or "乐府" in desc:
        verified_go(s, "east", "朱雀")  # lefang -> zhuque-s2
    elif "毛货" in desc or "鞋帽" in desc:
        verified_go(s, "north", "")  # shops on zhuque-s3
    elif "泾水" in desc:
        verified_go(s, "north", "")
    else:
        print(f"  ?? Unknown room, trying north: {desc[:40]}")
        verified_go(s, "north", "")
else:
    print("  !! Could not reach 十字街头 after 20 attempts")

# ============================================
# STEP 2: Ensure weapon + buy food
# ============================================
print("\n========== STEP 2: Weapon + Food ==========")
inv = clean(send(s, b"i\r\n", quiet=2.0))

if "钢刀" not in inv:
    print("  Buying blade: shizikou -> east -> south")
    verified_go(s, "east", "青龙")
    verified_go(s, "south", "兵器")
    send(s, b"buy blade from xiao xiao\r\n", quiet=1.5)
    send(s, b"wield blade\r\n", quiet=1.5)
    print("  Blade bought!")
    verified_go(s, "north", "青龙")
    verified_go(s, "west", "十字")
else:
    print("  Have blade!")

# Food: shizikou -> south -> east -> kezhan
print("  Getting food: shizikou -> south -> east")
verified_go(s, "south", "朱雀")
verified_go(s, "east", "客栈")
send(s, b"buy jitui from xiao er\r\n", quiet=1.5)
send(s, b"buy jitui from xiao er\r\n", quiet=1.5)
send(s, b"buy jiudai from xiao er\r\n", quiet=1.5)
send(s, b"eat jitui\r\n", quiet=1.0)
send(s, b"eat jitui\r\n", quiet=1.0)
send(s, b"drink jiudai\r\n", quiet=1.0)
print("  Fed!")

b = send(s, b"hp\r\n", quiet=2.0)
show("HP READY", b)

# ============================================
# STEP 3: Go to Yuan (kezhan -> west -> north -> north -> west)
# ============================================
print("\n========== STEP 3: Ask Yuan ==========")
print("  Route: kezhan -> west -> north -> north -> west")
verified_go(s, "west", "朱雀")
ok, _, _ = verified_go(s, "north", "十字")
if not ok:
    print("  !! Not at shizikou, retrying north")
    verified_go(s, "north", "十字")
verified_go(s, "north", "玄武")
ok, desc, b = verified_go(s, "west", "天监")

if "天监台" not in desc:
    print(f"  !! NOT at tianjiantai! At: {desc[:40]}")
    print("  Aborting mission.")
else:
    b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
    yuan = clean(b)
    show("YUAN MISSION", b)

    # Parse
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
        print("  Previous mission complete! Getting new...")
        b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
        yuan = clean(b)
        show("NEW MISSION", b)
        m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
        if m:
            monster_name = m.group(1)
            monster_id = m.group(2).strip().split()[0].lower()
            location = m.group(3)

    print(f"\n  MONSTER: {monster_name}")
    print(f"  ID: {monster_id}")
    print(f"  LOCATION: {location}")

    # ============================================
    # STEP 4: Go to target area
    # From tianjiantai -> east -> south = shizikou
    # Then route depends on location
    # ============================================
    if monster_name:
        print(f"\n========== STEP 4: Hunt {monster_name} ==========")
        verified_go(s, "east", "玄武")
        verified_go(s, "south", "十字")

        if location and "开封" in location:
            print("  Route to Kaifeng: east x4 -> east x5 -> east x3 -> nw -> n x3 -> w")
            # shizikou -> dongmen (4 east)
            for i in range(4):
                verified_go(s, "east", "")
            # dongmen -> kaifeng east1-5 -> chengmen (5 east)
            for i in range(5):
                go(s, "east")
            # chengmen -> chen1 -> chen2 -> tieta (3 east)
            for i in range(3):
                go(s, "east")
            # tieta -> shun5 (northwest)
            go(s, "northwest")
            desc, _ = look(s)
            print(f"  At: {desc[:40]}")

            # Search shun streets + yuxiangfu
            search = ["north","north","north","north",  # shun5->1
                      "south","west","east",  # yuxiangfu area from shun2
                      "south","south",  # shun4,5
                      "southeast",  # tieta
                      "south","south","south","south",  # yao streets
                      "east","west","north","north","north","north",
                      "northeast","east","west","southwest",
                      "west","east",
                      ]
        elif location and "望南" in (location or ""):
            print("  Route to wangnan: east x3 -> south")
            for i in range(3):
                verified_go(s, "east", "")
            verified_go(s, "south", "")
            search = ["southwest","south","west","southwest",
                      "northeast","east","north","northeast","east","west"]
        else:
            print(f"  Searching city for {monster_name}")
            search = ["south","east","west","west","east",
                      "south","east","west","south","east","west",
                      "south","north","north","north","north",
                      "east","north","south","east","north","south",
                      "east","south","north","west","west","west",
                      "west","south","north","west","south","north","east","east",
                      "north","east","west","south"]

        # Search!
        found = False
        for i, d in enumerate(search):
            go(s, d)
            desc, b = look(s)
            f, kid = is_monster(desc, monster_name, monster_id)
            if f:
                print(f"\n  ** FOUND {monster_name} at step {i}! ID: {kid} **")
                show("MONSTER!", b)
                killed = fight(s, kid)
                if killed:
                    print("\n  ********************************************")
                    print("  ***    FIRST KILL!!!                     ***")
                    print("  ***    YUAN MISSION COMPLETE!!!          ***")
                    print("  ********************************************")
                    time.sleep(3)
                    b = drain(s, quiet=2.0, maxt=5.0)
                    if b: show("AFTERMATH", b)
                found = True
                break

        if not found:
            print(f"\n  !! {monster_name} not found in {len(search)} rooms")

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

print("\n*** Round 26 ended - NO QUIT ***")
time.sleep(1)
s.close()
