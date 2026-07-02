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
    return send(s, d.encode() + b"\r\n", quiet=1.5)

def look_for(s, keyword):
    """Look in current room for keyword. Returns (found, description)."""
    b = send(s, b"look\r\n", quiet=1.5)
    t = clean(b)
    return keyword.lower() in t.lower() or keyword in t, t, b

def go_to_hub(s):
    """Get to shizikou from anywhere."""
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
        if "碑林" in t: go(s,"south"); continue
        if "国子监" in t: go(s,"west"); go(s,"south"); continue
        if "化生寺" in t: go(s,"north"); go(s,"east"); continue
        if "方丈" in t or "大雄" in t: go(s,"west"); go(s,"north"); go(s,"east"); continue
        if "钱庄" in t: go(s,"north"); go(s,"east"); continue
        if "书局" in t: go(s,"south"); go(s,"east"); continue
        if "南城口" in t: go(s,"north"); go(s,"north"); go(s,"north"); continue
        if "泾水" in t: go(s,"north"); continue
        if "背阴" in t: go(s,"east"); go(s,"north"); continue
        if "小酒馆" in t: go(s,"south"); go(s,"east"); go(s,"north"); continue
        go(s, "north")  # fallback
    return False

print("Round 21: FAST HUNT - prepare, ask yuan, go kill IMMEDIATELY!")
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
# PHASE 1: PREPARE (weapon + food)
# ============================================
print("\n========== PHASE 1: PREPARE ==========")
b = send(s, b"i\r\n", quiet=2.0)
inv = clean(b)

if "钢刀" not in inv:
    print("  Buying weapon...")
    go_to_hub(s)
    go(s, "east"); go(s, "south")  # qinglong -> weaponshop
    send(s, b"buy blade from xiao xiao\r\n", quiet=2.0)
    send(s, b"wield blade\r\n", quiet=2.0)
    print("  Blade equipped!")

# Buy food
print("  Buying food...")
go_to_hub(s)
go(s, "south"); go(s, "east")  # zhuque -> kezhan
send(s, b"buy jitui from xiao er\r\n", quiet=1.5)
send(s, b"buy jitui from xiao er\r\n", quiet=1.5)
send(s, b"buy jiudai from xiao er\r\n", quiet=1.5)
send(s, b"eat jitui\r\n", quiet=1.5)
send(s, b"eat jitui\r\n", quiet=1.5)
send(s, b"drink jiudai\r\n", quiet=1.5)

b = send(s, b"hp\r\n", quiet=2.0)
show("HP READY", b)
b = send(s, b"score\r\n", quiet=3.0)
show("COMBAT STATS", b)

# ============================================
# PHASE 2: ASK YUAN (get fresh mission)
# ============================================
print("\n========== PHASE 2: GET MISSION ==========")
go_to_hub(s)
go(s, "north"); go(s, "west")  # xuanwu -> tianjiantai
b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
yuan_resp = clean(b)
show("YUAN MISSION", b)

# Parse monster and location
m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan_resp)
if m:
    monster_name = m.group(1)
    monster_id = m.group(2).strip()
    monster_location = m.group(3)
    # Get first word of ID for the kill command
    monster_id_short = monster_id.split()[0].lower()
    print(f"\n  MONSTER: {monster_name} (ID: {monster_id}, short: {monster_id_short})")
    print(f"  LOCATION: {monster_location}")
else:
    # Yuan might say "go do the previous one" or give a new one
    # Check for the "不是请您去收服" pattern (reminding of existing mission)
    if "收服" in yuan_resp:
        m2 = re.search(r'收服(.+?)吗', yuan_resp)
        if m2:
            monster_name = m2.group(1)
            monster_id_short = None
            print(f"  EXISTING MISSION: go kill {monster_name}")
        else:
            monster_name = None
            monster_id_short = None
    else:
        monster_name = None
        monster_id_short = None
    print(f"  Yuan says: {yuan_resp[:200]}")

# ============================================
# PHASE 3: GO HUNT IMMEDIATELY!
# Search the area mentioned by yuan
# ============================================
print("\n========== PHASE 3: HUNT! ==========")

if monster_name:
    # Go back to hub first
    go(s, "east"); go(s, "south")  # tianjiantai -> xuanwu -> shizikou

    # Determine search area based on location hint
    # City area search: walk through ALL city streets + east area
    search_routes = {
        "city": [
            # From shizikou, systematic city search
            "south", "east",  # zhuque, kezhan
            "west",  # zhuque
            "south", "south", "south",  # south zhuque streets
            "east",  # wangnan5 (eastway)
            "northeast", "east", "north", "northeast",  # wangnan 4,3,2,1
            "east",  # huohang
            "west", "north",  # back to qinglong-e3
            "west", "west",  # qinglong-e2, e1
            "north",  # wuguan
            "south", "south",  # weaponshop
            "north", "west",  # back to shizikou
            "west", "south",  # baihu, beiyin1
            "east", "south",  # back to baihu, beiyin2/huasheng
            "north", "west", "south",  # more baihu, beiyin
            "north", "east", "east",  # back to shizikou
            "north", "east",  # xuanwu, guozijian
            "west", "west",  # xuanwu, tianjiantai
            "east", "south",  # back to shizikou
        ],
    }

    route = search_routes["city"]
    found = False

    for i, d in enumerate(route):
        go(s, d)
        b = send(s, b"look\r\n", quiet=1.0)
        desc = clean(b)

        # Check for the monster
        if monster_name and monster_name in desc:
            print(f"\n  ** FOUND {monster_name} at step {i}! **")
            show("MONSTER ROOM", b)
            found = True
        elif monster_id_short and monster_id_short in desc.lower():
            print(f"\n  ** FOUND {monster_id_short} at step {i}! **")
            show("MONSTER ROOM", b)
            found = True

        if found:
            # KILL IT NOW!
            print(f"\n  >> ATTACKING!")
            # Try kill with various ID formats
            killed = False
            for mid in [monster_id_short, monster_id.lower() if monster_id_short else "guai",
                        "jing", "guai", "yao"]:
                if not mid: continue
                b = send(s, f"kill {mid}\r\n".encode(), quiet=2.0)
                r = clean(b)
                if "喝道" in r or "想杀" in r or "领教" in r or "赐教" in r:
                    show("ENGAGED!", b)
                    # Combat!
                    for j in range(35):
                        time.sleep(3)
                        b = drain(s, quiet=2.0, maxt=5.0)
                        if b:
                            r = clean(b)
                            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                                show("**** VICTORY! ****", b)
                                killed = True
                                break
                            elif "承让" in r:
                                show("LOST (opponent won)", b)
                                break
                            elif "找机会逃跑" in r:
                                show("FLED", b)
                                break
                            elif j % 5 == 0:
                                show(f"COMBAT {j+1}", b)
                    break

            if killed:
                print("\n  ********************************************")
                print("  ***    YUAN MISSION COMPLETE!!!          ***")
                print("  ***    FIRST KILL ACHIEVED!!!            ***")
                print("  ********************************************")
                time.sleep(3)
                b = drain(s, quiet=2.0, maxt=5.0)
                if b: show("AFTERMATH", b)

                # Report back to yuan
                print("\n  Reporting to Yuan...")
                go_to_hub(s)
                go(s, "north"); go(s, "west")
                b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
                show("YUAN REPORT", b)
            break

    if not found:
        print(f"\n  !! {monster_name} not found in city search ({len(route)} rooms)")
        print(f"  !! Location: {monster_location}")
        print(f"  !! The monster may be in a remote area outside the city")

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

print("\n*** Round 21 ended - NO QUIT ***")
time.sleep(1)
s.close()
