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

def vgo(s, d, expect):
    go(s, d)
    desc, b = look(s)
    ok = expect in desc
    room = desc.split("\n")[0].strip()[:30]
    print(f"  {d:12s} -> [{('OK' if ok else '??')}] {room}")
    return ok, desc, b

known_npcs = ["Board","paizi","Agenta","Snoopl","Snoopy","Xiao er","Da ye",
    "Qianli","Fan luping","Wuguan dizi","Xiao xiao","Yuan tiangang",
    "Li bai","Zhang guolao","Jieding","Xiucai","Wei shi","Xiao bing",
    "Laitou","Zodiac","Yang zhong","Monk","Heshang","Faming",
    "Dong push","Kong fang","Tie suanpan","Kuli","Jia er","Horse",
    "Maguan","People","Zhike","Luren","Youke","Sengren","Bing",
    "Dai","Girl","Hai","Chen","Xu","Ye","Yin","Zu","Xgong",
    "Yahuan","Yang","Chaniang","Hu","Xiaotong","Gongwei","Siguan",
    "Wu jiang","Zhubing","Reporting","Lao tou","Xiao liumang",
    "Biao","Xiao pizi","Lao wei","Xiao wang","Gui tong","Dahan",
    "Haoke","Tiejiang","Huangbiao","Feng","Jin","Huian","Nuocha",
    "Zhangmen","Shizhe"]

def is_monster(desc, name, mid):
    for line in desc.split("\n"):
        line = line.strip()
        if "(" not in line or ")" not in line: continue
        if any(k in line for k in known_npcs): continue
        if name and name in line:
            m = re.search(r'\(([^)]+)\)', line)
            return True, m.group(1).strip().split()[0].lower() if m else mid
        if mid and mid.lower() in line.lower():
            m = re.search(r'\(([^)]+)\)', line)
            return True, m.group(1).strip().split()[0].lower() if m else mid
    return False, None

def fight(s, kid):
    r = go(s, f"kill {kid}")
    if "想攻击谁" in r or "没有" in r:
        r = go(s, f"fight {kid}")
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
            elif "承让" in r: print("  >> LOST"); return False
            elif "找机会逃跑" in r: print("  >> FLED"); return False
            elif j % 6 == 0:
                lines = [l for l in r.split("\n") if l.strip() and ">" not in l]
                if lines: print(f"  [combat {j}] {lines[-1].strip()[:60]}")
    return False

# ============================================
print("Round 30: ESCAPE PUTUO (fixed exits) → YUAN → HUNT!")
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
# PHASE 1: ESCAPE PUTUO - hardcoded exact path
# shanglu2: south → tingjing → south → island → swim → seashore → north x16
# ============================================
print("\n========== PHASE 1: ESCAPE PUTUO ==========")
desc, _ = look(s)
print(f"  At: {desc[:50]}")

# Try south first (shanglu2 exit), then southdown (shanglu exit)
print("  Trying south/southdown to reach island...")
for _ in range(5):
    go(s, "south")
    go(s, "southdown")

desc, _ = look(s)
print(f"  After south attempts: {desc[:50]}")

if "听经" in desc:
    print("  At tingjing! Going south to island...")
    go(s, "south")
    desc, _ = look(s)

if "小岛" in desc or "island" in desc.lower():
    print("  At island! Swimming...")
    go(s, "swim")
    desc, _ = look(s)
    print(f"  After swim: {desc[:50]}")

if "南海之滨" in desc:
    print("  At seashore! Going north x16 to shizikou...")
    for i in range(20):
        go(s, "north")
        desc, _ = look(s)
        if "十字街头" in desc:
            print(f"  >> SHIZIKOU after {i+1} norths!")
            break
        room = desc.split("\n")[0].strip()[:30]
        if i % 4 == 0: print(f"  north [{i+1}] {room}")

desc, _ = look(s)
if "十字街头" not in desc:
    # Still not there — keep trying north
    for i in range(10):
        go(s, "north")
        desc, _ = look(s)
        if "十字街头" in desc:
            print("  >> SHIZIKOU!")
            break

desc, b = look(s)
show("CURRENT", b)

if "十字街头" in desc:
    # ============================================
    # PHASE 2: GEAR + FOOD
    # ============================================
    print("\n========== PHASE 2: GEAR + FOOD ==========")
    vgo(s, "east", "青龙")
    vgo(s, "south", "兵器")
    send(s, b"buy blade from xiao xiao\r\n", quiet=1.5)
    send(s, b"wield blade\r\n", quiet=1.5)
    vgo(s, "north", "青龙")
    vgo(s, "west", "十字")
    vgo(s, "south", "朱雀")
    vgo(s, "east", "客栈")
    for _ in range(3):
        send(s, b"buy jitui from xiao er\r\n", quiet=1.0)
    send(s, b"buy jiudai from xiao er\r\n", quiet=1.0)
    for _ in range(3):
        send(s, b"eat jitui\r\n", quiet=0.8)
    send(s, b"drink jiudai\r\n", quiet=0.8)

    b = send(s, b"score\r\n", quiet=3.0)
    show("READY", b)

    # ============================================
    # PHASE 3: ASK YUAN
    # ============================================
    print("\n========== PHASE 3: YUAN ==========")
    vgo(s, "west", "朱雀")
    vgo(s, "north", "十字")
    vgo(s, "north", "玄武")
    vgo(s, "west", "天监")

    b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
    yuan = clean(b)
    show("MISSION", b)

    monster_name = None; monster_id = None; location = None
    m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
    if m:
        monster_name = m.group(1)
        monster_id = m.group(2).strip().split()[0].lower()
        location = m.group(3)
    elif "除尽" in yuan:
        b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
        yuan = clean(b); show("NEW", b)
        m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
        if m:
            monster_name = m.group(1)
            monster_id = m.group(2).strip().split()[0].lower()
            location = m.group(3)
    elif "收服" in yuan:
        m2 = re.search(r'收服(.+?)吗', yuan)
        if m2: monster_name = m2.group(1); monster_id = "guai"

    print(f"\n  TARGET: {monster_name} (id: {monster_id}) @ {location}")

    if monster_name:
        # ============================================
        # PHASE 4: TRAVEL + SEARCH + KILL
        # ============================================
        print(f"\n========== PHASE 4: HUNT ==========")
        vgo(s, "east", "玄武")
        vgo(s, "south", "十字")
        loc = location or ""

        if "普陀" in loc:
            print("  PUTUO: south x16 → swim → north x4")
            for _ in range(16): go(s, "south")
            go(s, "swim"); go(s, "north"); go(s, "north"); go(s, "northup"); go(s, "northup")
            search = ["north"]*4+["east","west"]+["south"]*4+["west"]*2+["east"]*3+["south"]*3+["enter","out"]
        elif "开封" in loc:
            print("  KAIFENG: east x13 → nw → search")
            for _ in range(13): go(s, "east")
            go(s, "northwest")
            search = ["north"]*4+["west","east"]+["south"]*4+["southeast"]+["south"]*4+["east","west"]+["north"]*4
        elif "望南" in loc:
            print("  WANGNAN: east x3 → south → search")
            for _ in range(3): go(s, "east")
            go(s, "south")
            search = ["southwest","south","west","southwest","northeast","east","north","northeast","east","west"]
        else:
            print(f"  CITY SEARCH: '{loc}'")
            search = ["south","east","west","west","east","south","east","west",
                      "south","south","north","north","north","east","north","south",
                      "east","north","south","west","west","west","south","north",
                      "west","south","north","east","east","north","east","west","south"]

        found = False
        for i, d in enumerate(search):
            go(s, d)
            desc, b = look(s)
            f, kid = is_monster(desc, monster_name, monster_id)
            if f:
                print(f"\n  ** FOUND {monster_name}! ID: {kid} **")
                show("MONSTER!", b)
                killed = fight(s, kid)
                if killed:
                    print("\n  ********************************************")
                    print("  ***    FIRST KILL!!!                     ***")
                    print("  ***    YUAN MISSION COMPLETE!!!          ***")
                    print("  ********************************************")
                found = True
                break
        if not found:
            print(f"\n  !! {monster_name} not found ({len(search)} rooms)")
else:
    print("  !! Not at shizikou, escape failed")

print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
print("\n*** Round 30 - NO QUIT ***")
time.sleep(1)
s.close()
