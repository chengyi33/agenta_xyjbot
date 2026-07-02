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
    print(f"  {d:12s} -> [{('OK' if ok else 'FAIL')}] {room}")
    return ok, desc, b

def is_monster(desc, name, mid):
    known = ["Board","paizi","Agenta","Snoopl","Snoopy","Xiao er","Da ye",
        "Qianli","Fan luping","Wuguan dizi","Xiao xiao","Yuan tiangang",
        "Li bai","Zhang guolao","Jieding","Xiucai","Wei shi","Xiao bing",
        "Laitou","Zodiac","Yang zhong","Monk","Heshang","Faming",
        "Dong push","Kong fang","Tie suanpan","Kuli","Jia er","Horse",
        "Maguan","People","Zhike"]
    for line in desc.split("\n"):
        line = line.strip()
        if "(" not in line or ")" not in line: continue
        if any(k in line for k in known): continue
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
            elif "承让" in r:
                print("  >> LOST"); return False
            elif "找机会逃跑" in r:
                print("  >> FLED"); return False
            elif j % 6 == 0:
                lines = [l for l in r.split("\n") if l.strip() and ">" not in l]
                if lines: print(f"  [combat {j}] {lines[-1].strip()[:60]}")
    return False

# ============================================
print("Round 27: SWIM TO PUTUO AND KILL 海狸精!")
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
# STEP 1: Get to shizikou (verified)
# ============================================
print("\n========== STEP 1: To shizikou ==========")
for attempt in range(15):
    desc, b = look(s)
    if "十字街头" in desc:
        print("  >> AT shizikou!")
        break
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
    if "南城口" in desc: go(s,"north"); go(s,"north"); go(s,"north"); go(s,"north"); continue
    go(s,"north"); continue

# ============================================
# STEP 2: Confirm mission still active
# ============================================
print("\n========== STEP 2: Check yuan ==========")
vgo(s, "north", "玄武")
vgo(s, "west", "天监")
b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
yuan = clean(b)
show("YUAN", b)

monster_name = None; monster_id = None
m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
if m:
    monster_name = m.group(1)
    monster_id = m.group(2).strip().split()[0].lower()
    print(f"  NEW: {monster_name} (id: {monster_id}) at {m.group(3)}")
elif "收服" in yuan:
    m2 = re.search(r'收服(.+?)吗', yuan)
    if m2:
        monster_name = m2.group(1)
        monster_id = "haili"  # from previous: 海狸精
        print(f"  EXISTING: {monster_name} (id: {monster_id})")
elif "除尽" in yuan:
    print("  Mission done! Getting new...")
    b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
    yuan = clean(b); show("NEW", b)
    m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
    if m:
        monster_name = m.group(1)
        monster_id = m.group(2).strip().split()[0].lower()

# Go back to shizikou
vgo(s, "east", "玄武")
vgo(s, "south", "十字")

if not monster_name:
    print("  !! No mission!")
else:
    # ============================================
    # STEP 3: Travel south to 南海之滨, then SWIM
    # ~16 souths from shizikou
    # ============================================
    print(f"\n========== STEP 3: Travel to 普陀山 for {monster_name} ==========")
    print("  Going south to the sea...")

    # Track position as we go south
    for i in range(20):
        go(s, "south")
        desc, b = look(s)
        room = desc.split("\n")[0].strip()[:40]
        print(f"  south [{i+1}] -> {room}")

        if "南海之滨" in desc or "southseashore" in desc.lower() or "海滨" in desc:
            print("\n  >> AT THE SEASHORE! SWIMMING!")
            r = go(s, "swim")
            desc2, b2 = look(s)
            show("AFTER SWIM", b2)

            if "小岛" in desc2 or "island" in desc2.lower() or "岛" in desc2:
                print("  >> ON THE ISLAND! Going north to Putuo...")
                go(s, "north")   # tingjing
                go(s, "north")   # shanglu2
                go(s, "northup") # shanglu
                go(s, "northup") # gate
                desc3, b3 = look(s)
                show("AT PUTUO GATE?", b3)

                # ============================================
                # STEP 4: Search nanhai for the monster
                # ============================================
                print(f"\n========== STEP 4: Search for {monster_name} ==========")
                # Search nanhai rooms systematically
                nanhai_search = [
                    "north",  # from gate -> guangchang or road
                    "north", "north", "north",
                    "east", "west",
                    "south", "south", "south", "south",
                    "east", "east",
                    "west", "west",
                    "north", "north",
                    "west", "west",
                    "east", "east",
                    "south", "south",
                    "northeast", "southwest",
                    "northwest", "southeast",
                    "north", "north", "north",
                    "enter",
                    "out",
                    "south", "south", "south",
                ]

                found = False
                for j, d in enumerate(nanhai_search):
                    go(s, d)
                    desc4, b4 = look(s)
                    f, kid = is_monster(desc4, monster_name, monster_id)
                    if f:
                        print(f"\n  ** FOUND {monster_name}! ID: {kid} **")
                        show("MONSTER!", b4)
                        killed = fight(s, kid)
                        if killed:
                            print("\n  ********************************************")
                            print("  ***    FIRST KILL!!!                     ***")
                            print("  ***    YUAN MISSION COMPLETE!!!          ***")
                            print("  ********************************************")
                            time.sleep(3)
                            b5 = drain(s, quiet=2.0, maxt=5.0)
                            if b5: show("AFTERMATH", b5)
                        found = True
                        break

                if not found:
                    print(f"\n  !! {monster_name} not found in {len(nanhai_search)} nanhai rooms")
            break

        if "什么" in desc or len(desc.strip()) < 10:
            print("  !! Can't go further south, dead end")
            break

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

print("\n*** Round 27 ended - NO QUIT ***")
time.sleep(1)
s.close()
