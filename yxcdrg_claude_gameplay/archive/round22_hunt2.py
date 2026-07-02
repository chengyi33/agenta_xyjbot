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
        if "化生寺" in t: go(s,"north"); go(s,"east"); continue
        if "方丈" in t or "大雄" in t: go(s,"west"); go(s,"north"); go(s,"east"); continue
        if "钱庄" in t: go(s,"north"); go(s,"east"); continue
        if "书局" in t: go(s,"south"); go(s,"east"); continue
        if "南城口" in t: go(s,"north"); go(s,"north"); go(s,"north"); continue
        if "泾水" in t: go(s,"north"); continue
        if "背阴" in t: go(s,"east"); go(s,"north"); continue
        if "小酒馆" in t: go(s,"south"); go(s,"east"); go(s,"north"); continue
        if "碑林" in t: go(s,"south"); continue
        go(s, "north")
    return False

print("Round 22: Hunt boar - comprehensive city search!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
if "y/n" in clean(b):
    send(s, b"y\r\n", quiet=4.0)

send(s, b"set wimpy 15\r\n", quiet=1.0)

# Make sure we have weapon
b = send(s, b"i\r\n", quiet=2.0)
inv = clean(b)
if "钢刀" not in inv:
    print("  Buying weapon...")
    go_to_hub(s)
    go(s,"east"); go(s,"south")
    send(s, b"buy blade from xiao xiao\r\n", quiet=1.5)
    send(s, b"wield blade\r\n", quiet=1.5)

# First ask yuan - maybe we get a new mission or old one expired
print("\n========== ASK YUAN ==========")
go_to_hub(s)
go(s,"north"); go(s,"west")
b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
yuan_resp = clean(b)
show("YUAN", b)

# Parse monster name from ANY format yuan uses
monster_name = None
monster_id_short = None

# Format 1: new mission "近有XXX(Yyy)在ZZZ出没"
m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan_resp)
if m:
    monster_name = m.group(1)
    monster_id_short = m.group(2).strip().split()[0].lower()
    print(f"  NEW MISSION: {monster_name} (id: {monster_id_short})")

# Format 2: reminder "收服XXX吗"
if not monster_name:
    m2 = re.search(r'收服(.+?)吗', yuan_resp)
    if m2:
        monster_name = m2.group(1)
        # Guess the ID from common patterns
        name_to_id = {"野猪精":"yezhu", "青蛇怪":"qingshe", "灰狼怪":"huilang",
                      "獭精":"ta", "鹿精":"lu", "蛇精":"she", "狼精":"lang",
                      "猪精":"zhu", "虎精":"hu", "鸡精":"ji", "牛精":"niu"}
        for cn, pid in name_to_id.items():
            if cn in monster_name:
                monster_id_short = pid
                break
        if not monster_id_short:
            monster_id_short = "guai"  # generic fallback
        print(f"  EXISTING MISSION: {monster_name} (guessed id: {monster_id_short})")

# Format 3: mission complete "妖魔已经除尽了"
if "除尽" in yuan_resp:
    print("  MISSION ALREADY COMPLETE!")
    # Ask again for new mission
    b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
    yuan_resp = clean(b)
    show("YUAN NEW", b)
    m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan_resp)
    if m:
        monster_name = m.group(1)
        monster_id_short = m.group(2).strip().split()[0].lower()
        print(f"  NEW MISSION: {monster_name} (id: {monster_id_short})")

if not monster_name:
    print(f"  Could not determine mission. Yuan said: {yuan_resp[:200]}")

# ============================================
# COMPREHENSIVE CITY SEARCH
# The yaoguai wanders randomly, could be in ANY room
# Search systematically from shizikou
# ============================================
print(f"\n========== SEARCHING FOR {monster_name} ==========")

go(s,"east"); go(s,"south")  # back to shizikou

# Comprehensive search path - covers most of the city
search_path = [
    # Main streets from shizikou
    "south",       # zhuque (kezhan level)
    "east",        # kezhan
    "west",        # zhuque
    "west",        # dangpu
    "east",        # zhuque
    "south",       # zhuque-s2
    "east",        # pharmacy area
    "west",        # zhuque-s2
    "west",        # lefang
    "east",        # zhuque-s2
    "south",       # zhuque-s3
    "east",        # shoe shop
    "west",        # zhuque-s3
    "west",        # fur shop
    "east",        # zhuque-s3
    "south",       # zhuque-s4
    # Eastway from zhuque-s4
    "east",        # wangnan5
    "northeast",   # wangnan4
    "east",        # wangnan3
    "north",       # wangnan2
    "northeast",   # wangnan1
    "east",        # huohang
    "west",        # wangnan1
    "north",       # qinglong-e3
    "west",        # qinglong-e2
    "south",       # maybe将军府
    "north",       # qinglong-e2
    "west",        # qinglong-e1
    "north",       # wuguan
    "east",        # wuguan east
    "west",        # wuguan
    "south",       # qinglong-e1
    "south",       # weaponshop
    "north",       # qinglong-e1
    "west",        # shizikou
    # West side
    "west",        # baihu-w1
    "north",       # maybe place
    "south",       # baihu-w1
    "south",       # beiyin1/huasheng
    "east",        # minju1
    "west",        # beiyin1
    "south",       # beiyin2/酒馆area
    "south",       # beiyin3
    "south",       # minju3
    "north",       # beiyin3
    "east",        # beiyin4
    "southeast",   # beiyin5
    "south",       # minju4
    "north",       # beiyin5
    "west",        # zahuopu
    "east",        # beiyin5
    "east",        # zhuque-s4
    "north","north","north","north",  # back to shizikou
    # North side
    "north",       # xuanwu
    "east",        # guozijian
    "east",        # guozijian east?
    "west","west", # back to xuanwu
    "north",       # palace gate area
    "south","south",  # shizikou
    # More west
    "west",        # baihu-w1
    "west",        # baihu-w2
    "north",       # bookshop
    "south",       # baihu-w2
    "south",       # bank/qianzhuang
    "north",       # baihu-w2
    "west",        # baihu-w3
    "north",       # caotang
    "south",       # baihu-w3
]

found = False
rooms_searched = 0

for d in search_path:
    go(s, d)
    b = send(s, b"look\r\n", quiet=0.8)
    desc = clean(b)
    rooms_searched += 1

    # Check for monster by name AND by id
    if monster_name and monster_name in desc:
        found = True
    elif monster_id_short and monster_id_short in desc.lower():
        found = True
    # Also check for generic monster indicators with the specific type
    elif "精" in desc or "怪" in desc or "妖" in desc:
        # Check if it's an NPC line (has parentheses with ID)
        for line in desc.split("\n"):
            if ("精" in line or "怪" in line or "妖" in line) and "(" in line:
                if "Jieding" not in line and "Board" not in line:
                    # This might be our target!
                    print(f"  !! Potential monster: {line.strip()}")
                    found = True
                    break

    if found:
        print(f"\n  ** FOUND MONSTER after searching {rooms_searched} rooms! **")
        show("MONSTER ROOM", b)

        # Extract the NPC ID from the room description
        target_ids = []
        if monster_id_short:
            target_ids.append(monster_id_short)
        # Also try to extract from parentheses in description
        for line in desc.split("\n"):
            if monster_name and monster_name in line and "(" in line:
                m3 = re.search(r'\(([^)]+)\)', line)
                if m3:
                    tid = m3.group(1).strip().split()[0].lower()
                    target_ids.insert(0, tid)

        # Try to kill
        killed = False
        for tid in target_ids:
            b = send(s, f"kill {tid}\r\n".encode(), quiet=2.0)
            r = clean(b)
            if "喝道" in r or "想杀" in r or "领教" in r or "奉陪" in r:
                show("ENGAGED!", b)
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
                            show("LOST", b)
                            break
                        elif "找机会逃跑" in r:
                            show("FLED", b)
                            break
                        elif j % 5 == 0:
                            show(f"COMBAT {j+1}", b)
                break

        if killed:
            print("\n  ********************************************")
            print("  ***    FIRST KILL!!!                     ***")
            print("  ***    YUAN MISSION COMPLETE!!!          ***")
            print("  ********************************************")
            time.sleep(3)
            b = drain(s, quiet=2.0, maxt=5.0)
            if b: show("AFTERMATH", b)

            # Report to yuan
            go_to_hub(s)
            go(s,"north"); go(s,"west")
            b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
            show("YUAN REPORT", b)
        break

if not found:
    print(f"\n  !! Monster not found after {rooms_searched} rooms searched")
    print(f"  !! The boar may have despawned or is in an area we can't reach")

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

print("\n*** Round 22 ended - NO QUIT ***")
time.sleep(1)
s.close()
