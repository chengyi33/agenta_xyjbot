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
    "Haoke","Tiejiang","Huangbiao","Feng","Jin"]

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

def goto_shizikou(s):
    """Get to shizikou from ANYWHERE including remote areas."""
    for attempt in range(30):
        desc, _ = look(s)
        if "十字街头" in desc: return True

        # === PUTUO/NANHAI escape ===
        if "山门" in desc: go(s,"southdown"); continue
        if "山路" in desc: go(s,"southdown"); continue
        if "听经" in desc: go(s,"south"); continue
        if "小岛" in desc: go(s,"swim"); continue
        if "南海之滨" in desc:
            for _ in range(16): go(s,"north")
            continue
        if "竹林" in desc or "落伽" in desc or "洞" in desc or "走廊" in desc:
            go(s,"south"); continue
        if "广场" in desc and "普陀" in desc: go(s,"south"); continue
        if "禅房" in desc or "书院" in desc or "学院" in desc:
            go(s,"out"); continue

        # === KAIFENG escape ===
        if "开封" in desc or "辰龙" in desc or "汴京" in desc or "舜王" in desc or "尧王" in desc:
            go(s,"west"); continue
        if "御相" in desc: go(s,"east"); continue

        # === Standard Chang'an nav ===
        if "南城客栈" in desc: go(s,"west"); go(s,"north"); continue
        if "朱雀大街" in desc:
            if "客栈" in desc: go(s,"north")
            else: go(s,"north")
            continue
        if "白虎" in desc: go(s,"east"); continue
        if "青龙" in desc: go(s,"west"); continue
        if "玄武" in desc: go(s,"south"); continue
        if "天监" in desc: go(s,"east"); go(s,"south"); continue
        if "当铺" in desc: go(s,"east"); go(s,"north"); continue
        if "武馆" in desc: go(s,"south"); go(s,"west"); continue
        if "兵器" in desc: go(s,"north"); go(s,"west"); continue
        if "药铺" in desc or "回春" in desc: go(s,"west"); go(s,"north"); continue
        if "南城口" in desc:
            go(s,"north"); go(s,"north"); go(s,"north"); go(s,"north")
            continue
        if "朝阳门" in desc: go(s,"south"); continue
        if "国子监" in desc: go(s,"west"); go(s,"south"); continue
        if "化生" in desc or "方丈" in desc or "大雄" in desc:
            go(s,"north"); go(s,"east"); continue
        if "书局" in desc or "三联" in desc: go(s,"south"); go(s,"east"); continue
        if "钱庄" in desc: go(s,"north"); go(s,"east"); continue
        if "背阴" in desc or "小酒馆" in desc or "民居" in desc: go(s,"north"); continue
        if "东门" in desc: go(s,"west"); continue
        if "大官道" in desc or "终南" in desc or "南岳" in desc or "泾水" in desc:
            go(s,"north"); continue

        # Generic fallback
        go(s,"north")
    return False

# ============================================
print("Round 29: Escape Putuo → Yuan → Gear → Hunt → KILL!")
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
# PHASE 1: ESCAPE to shizikou
# ============================================
print("\n========== PHASE 1: ESCAPE TO SHIZIKOU ==========")
desc, _ = look(s)
print(f"  Starting: {desc[:40]}")
ok = goto_shizikou(s)
desc, b = look(s)
if "十字街头" in desc:
    print("  >> AT SHIZIKOU!")
else:
    print(f"  !! Failed to reach shizikou: {desc[:40]}")

# ============================================
# PHASE 2: GEAR UP
# ============================================
print("\n========== PHASE 2: GEAR + FOOD ==========")
vgo(s, "east", "青龙")
vgo(s, "south", "兵器")
desc, _ = look(s)
if "兵器" in desc:
    send(s, b"buy blade from xiao xiao\r\n", quiet=1.5)
    send(s, b"wield blade\r\n", quiet=1.5)
    print("  Blade!")

vgo(s, "north", "青龙")
vgo(s, "west", "十字")
vgo(s, "south", "朱雀")
vgo(s, "east", "客栈")
desc, _ = look(s)
if "客栈" in desc:
    send(s, b"buy jitui from xiao er\r\n", quiet=1.0)
    send(s, b"buy jitui from xiao er\r\n", quiet=1.0)
    send(s, b"buy jiudai from xiao er\r\n", quiet=1.0)
    send(s, b"eat jitui\r\n", quiet=1.0)
    send(s, b"eat jitui\r\n", quiet=1.0)
    send(s, b"drink jiudai\r\n", quiet=1.0)
    print("  Fed!")

b = send(s, b"score\r\n", quiet=3.0)
show("READY", b)

# ============================================
# PHASE 3: ASK YUAN (FRESH MISSION)
# ============================================
print("\n========== PHASE 3: YUAN ==========")
vgo(s, "west", "朱雀")
vgo(s, "north", "十字")
vgo(s, "north", "玄武")
vgo(s, "west", "天监")
desc, _ = look(s)
if "天监" not in desc:
    print(f"  !! Not at yuan: {desc[:40]}")
else:
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

    print(f"\n  TARGET: {monster_name} (id: {monster_id})")
    print(f"  AREA: {location}")

    # ============================================
    # PHASE 4: TRAVEL + SEARCH + KILL
    # ============================================
    if monster_name:
        print(f"\n========== PHASE 4: HUNT {monster_name} ==========")
        vgo(s, "east", "玄武")
        vgo(s, "south", "十字")
        loc = location or ""

        if "普陀" in loc:
            print("  Route: south x16 → swim → north x4")
            for _ in range(16): go(s, "south")
            go(s, "swim"); go(s, "north"); go(s, "north"); go(s, "northup"); go(s, "northup")
            search = ["north"]*4 + ["east","west"] + ["south"]*4 + ["west"]*2 + ["east"]*3 + \
                     ["south"]*3 + ["northeast","northwest","south"]*2 + ["enter","out"]

        elif "开封" in loc:
            print("  Route: east x13 → northwest → search")
            for _ in range(13): go(s, "east")
            go(s, "northwest")
            search = ["north"]*4 + ["west","east"] + ["south"]*4 + ["southeast"] + \
                     ["south"]*4 + ["east","west"] + ["north"]*4

        elif "望南" in loc:
            print("  Route: east x3 → south → search")
            for _ in range(3): go(s, "east")
            go(s, "south")
            search = ["southwest","south","west","southwest","northeast","east",
                      "north","northeast","east","west"]

        else:
            print(f"  Searching city for '{loc}'")
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
                print(f"\n  ** FOUND {monster_name} at step {i}! ID: {kid} **")
                show("MONSTER!", b)
                killed = fight(s, kid)
                if killed:
                    print("\n  ********************************************")
                    print("  ***    FIRST KILL!!!                     ***")
                    print("  ***    YUAN MISSION COMPLETE!!!          ***")
                    print("  ********************************************")
                    time.sleep(3)
                    b2 = drain(s, quiet=2.0, maxt=5.0)
                    if b2: show("AFTERMATH", b2)
                found = True
                break

        if not found:
            print(f"\n  !! {monster_name} not found in {len(search)} rooms")

# FINAL
print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)
print("\n*** Round 29 ended - NO QUIT ***")
time.sleep(1)
s.close()
