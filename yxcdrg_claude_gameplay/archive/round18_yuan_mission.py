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
    b = send(s, d.encode() + b"\r\n", quiet=2.0)
    return clean(b), b

def look(s):
    b = send(s, b"look\r\n", quiet=2.0)
    r = clean(b)
    # Extract short name
    for line in r.split("\n"):
        line = line.strip()
        if " - " in line and len(line) > 3:
            return line.split(" - ")[0].strip(), r, b
    return "?", r, b

def verified_go(s, direction, expect):
    """Move and verify arrival. Returns (success, room_name, desc)."""
    go(s, direction)
    name, desc, b = look(s)
    ok = expect in name or expect in desc
    if not ok:
        print(f"  !! {direction} -> {name} (expected {expect})")
    else:
        print(f"  >> {direction} -> {name} OK")
    return ok, name, desc

print("Round 18: YUAN MISSION - proper process!")
print("1. Ask yuan  2. Gear up  3. Find & kill target")
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
# STEP 0: Figure out where we are
# ============================================
name, desc, b = look(s)
show("STARTING AT", b)
print(f"  Room: {name}")

# ============================================
# STEP 1: Navigate to 十字街头 (city hub)
# Smart navigation from known positions
# ============================================
print("\n========== STEP 1: GET TO HUB ==========")

# Keep going east until we hit 十字街头
for attempt in range(6):
    name, desc, b = look(s)
    if "十字" in name:
        print(f"  >> At 十字街头!")
        break
    elif "白虎" in name:
        go(s, "east")
    elif "客栈" in name or "南城客栈" in name:
        go(s, "west"); go(s, "north")
    elif "朱雀" in name:
        go(s, "north")
    elif "青龙" in name:
        go(s, "west")
    elif "当铺" in name:
        go(s, "east"); go(s, "north")
    elif "玄武" in name:
        go(s, "south")
    elif "天监" in name:
        go(s, "east"); go(s, "south")
    elif "武馆" in name:
        go(s, "south"); go(s, "west")
    elif "兵器" in name:
        go(s, "north"); go(s, "west")
    elif "化生" in name:
        go(s, "north")  # huasheng -> baihu
        go(s, "east")   # baihu -> shizikou
    elif "钱庄" in name:
        go(s, "north")  # qianzhuang -> baihu
        go(s, "east")
    elif "方丈" in name or "大雄" in name:
        go(s, "west")   # inner temple rooms
        go(s, "north")
        go(s, "east")
    elif "国子监" in name:
        go(s, "west"); go(s, "south")
    else:
        print(f"  !! Unknown: {name}, trying north")
        go(s, "north")

name, desc, b = look(s)
show("AT HUB", b)

# ============================================
# STEP 1b: Go to Yuan Tiangang (十字->north->west)
# ============================================
print("\n========== STEP 1b: ASK YUAN ==========")
verified_go(s, "north", "玄武")
verified_go(s, "west", "天监")

b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
show("YUAN'S MISSION", b)
yuan_resp = clean(b)
print(f"\n  ** MISSION: {yuan_resp.strip()} **")

# Parse monster name and location from response
# Format: "近有XXX(Yyy)在ZZZ出没"
monster_match = re.search(r'近有(.+?)\((\w+[^)]*)\)在(.+?)出没', yuan_resp)
if monster_match:
    monster_name = monster_match.group(1)
    monster_id = monster_match.group(2).strip().lower()
    monster_location = monster_match.group(3)
    print(f"  Monster: {monster_name} (ID: {monster_id})")
    print(f"  Location: {monster_location}")
else:
    # Try alternate parse
    monster_id = None
    monster_location = None
    print("  !! Could not parse mission details")

# ============================================
# STEP 2: GEAR UP - buy weapon at 兵器铺
# 天监->east->south->east->south
# ============================================
print("\n========== STEP 2: GEAR UP ==========")
verified_go(s, "east", "玄武")
verified_go(s, "south", "十字")
verified_go(s, "east", "青龙")
verified_go(s, "south", "兵器")

name, desc, b = look(s)
if "兵器" in name or "萧萧" in desc:
    b = send(s, b"buy blade from xiao xiao\r\n", quiet=2.0)
    show("BUY BLADE", b)
    b = send(s, b"wield blade\r\n", quiet=2.0)
    show("WIELD", b)
    b = send(s, b"buy shield from xiao xiao\r\n", quiet=2.0)
    show("BUY SHIELD", b)
    b = send(s, b"wear shield\r\n", quiet=2.0)
    show("WEAR SHIELD", b)
else:
    print(f"  !! Not at weapon shop: {name}")

b = send(s, b"hp\r\n", quiet=2.0)
show("HP STATUS", b)
b = send(s, b"score\r\n", quiet=3.0)
show("COMBAT STATS", b)

# ============================================
# STEP 3: Find the monster
# Navigate to the area yuan mentioned, search rooms
# ============================================
print("\n========== STEP 3: HUNT THE MONSTER ==========")

if monster_id:
    # First go back to hub
    go(s, "north")  # qinglong
    go(s, "west")   # shizikou

    # The monster could be in city area (/d/city) which is chang'an
    # Search city rooms by walking around
    found = False
    search_dirs = ["north", "south", "east", "west",
                   "south", "south", "south",  # south zhuque
                   "north", "north", "north", "north",  # back + north
                   "east", "north",  # qinglong, wuguan area
                   "south", "south",  # weapon shop area
                   "north", "west",   # back to shizikou
                   "west", "south",   # baihu, beiyin area
                   "north", "west", "south",  # more baihu
                   ]

    for d in search_dirs:
        go(s, d)
        name, desc, b = look(s)
        # Check if monster is in this room
        if monster_id and monster_id.lower().split()[0] in desc.lower():
            print(f"\n  ** FOUND {monster_name} at {name}! **")
            show("MONSTER ROOM", b)
            found = True
            break
        # Also check Chinese name
        if monster_name and monster_name in desc:
            print(f"\n  ** FOUND {monster_name} at {name}! **")
            show("MONSTER ROOM", b)
            found = True
            break

    if found:
        # ============================================
        # STEP 4: KILL IT!
        # ============================================
        print(f"\n========== STEP 4: KILL {monster_name}! ==========")
        # Try kill command with the ID
        mid = monster_id.split()[0].lower()
        b = send(s, f"kill {mid}\r\n".encode(), quiet=2.0)
        show("KILL!", b)
        r = clean(b)

        # If kill didn't work try fight
        if "想攻击谁" in r or "什么" in r or "没有" in r:
            # Try with guai as suffix
            b = send(s, f"kill {mid} guai\r\n".encode(), quiet=2.0)
            show("KILL ALT", b)
            r = clean(b)
        if "想攻击谁" in r or "什么" in r or "没有" in r:
            b = send(s, f"fight {mid}\r\n".encode(), quiet=2.0)
            show("FIGHT", b)

        # Watch combat
        killed = False
        for i in range(30):
            time.sleep(3)
            b = drain(s, quiet=2.0, maxt=5.0)
            if b:
                r = clean(b)
                if "死了" in r or "服了" in r or "投降" in r or "领罪" in r or "青烟" in r or "原形" in r:
                    show("*** VICTORY! ***", b)
                    killed = True
                    break
                elif "承让" in r:
                    show("LOST", b)
                    break
                elif "找机会逃跑" in r:
                    show("FLEEING", b)
                    # Don't break - keep fighting if we come back
                elif i % 4 == 0:
                    show(f"COMBAT {i+1}", b)

        if killed:
            print("\n  ************************************")
            print("  *** YUAN'S MISSION COMPLETE!!! ***")
            print("  ************************************")

            # Check for rewards
            time.sleep(2)
            b = drain(s, quiet=2.0, maxt=4.0)
            if b: show("REWARD?", b)
    else:
        print(f"\n  !! Monster not found in search area")
        print(f"  !! Location was: {monster_location}")
        print(f"  !! The monster may be in a remote area we can't reach yet")
else:
    print("  !! No monster ID parsed from yuan's response")

# ============================================
# FINAL STATUS
# ============================================
print("\n========== FINAL STATUS ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)
b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS", b)
b = send(s, b"i\r\n", quiet=2.0)
show("INVENTORY", b)

print("\n*** Round 18 ended - NO QUIT ***")
time.sleep(1)
s.close()
