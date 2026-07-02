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
    "Zhangmen","Shizhe","Sanhua","Xiao liu","Boy","Rat",
    "Oldman","Oldwoman","Keeper","Eryi","Woman","Youxia","Bookseller"]

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
print("Round 31: SPRINT TO 粮仓 — kill 黑狮精 NOW!")
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
# PHASE 1: Get to shizikou FAST
# ============================================
print("\n========== GET TO SHIZIKOU ==========")
for _ in range(15):
    desc, _ = look(s)
    if "十字街头" in desc: print("  >> SHIZIKOU!"); break
    if "南城客栈" in desc: go(s,"west"); go(s,"north"); continue
    if "朱雀" in desc:
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
    if "南城口" in desc: go(s,"north"); go(s,"north"); go(s,"north"); go(s,"north"); continue
    if "背阴" in desc: go(s,"north"); continue
    go(s,"north")

# ============================================
# PHASE 2: Go DIRECTLY to 粮仓 area
# Route: shizikou → south x4(zhuque-s4) → west(beiyin5) → northwest(beiyin4) → east(liangdian/粮仓)
# Also search: beiyin3, beiyin2, beiyin1, minju rooms (monster wanders!)
# ============================================
print("\n========== SEARCHING 粮仓 AREA ==========")

# First check: is the mission still active? Or did it expire?
# Don't go to yuan — that wastes time. Just go search.

# Path to 粮仓 and surrounding beiyin area
print("  shizikou → south x4 → west → northwest → east (粮仓)")
go(s,"south"); go(s,"south"); go(s,"south"); go(s,"south")  # zhuque-s4
go(s,"west")     # beiyin5
go(s,"northwest") # beiyin4

# Check beiyin4 first
desc, b = look(s)
show("BEIYIN4", b)
f, kid = is_monster(desc, "黑狮精", "heishi")
found = False

if f:
    print(f"\n  ** FOUND HERE! ID: {kid} **")
    found = True
    killed = fight(s, kid)
else:
    # Go to liangdian (粮仓)
    vgo(s, "east", "粮")
    desc, b = look(s)
    show("LIANGDIAN/粮仓", b)
    f, kid = is_monster(desc, "黑狮精", "heishi")
    if f:
        print(f"\n  ** FOUND at 粮仓! ID: {kid} **")
        found = True
        killed = fight(s, kid)

if not found:
    # Search other beiyin rooms — monster wanders
    print("  Not at 粮仓, searching beiyin area...")
    search = [
        ("west", "beiyin4"),      # back to beiyin4
        ("west", "beiyin3"),      # west
        ("south", "minju3"),      # south (rats room)
        ("north", "beiyin3"),     # back
        ("north", "beiyin2"),     # north
        ("north", "beiyin1"),     # north
        ("east", "minju1"),       # east (girl room)
        ("west", "beiyin1"),      # back
        ("south", "beiyin2"),     # south
        ("east", "jiuguan"),      # east (bar)
        ("west", "beiyin2"),      # back
        ("south", "beiyin3"),     # south
        ("east", "beiyin4"),      # east
        ("southeast", "beiyin5"), # southeast
        ("south", "minju4"),      # south (boy room)
        ("north", "beiyin5"),     # back
        ("west", "zahuopu"),      # west (杂货铺)
        ("east", "beiyin5"),      # back
        ("east", "zhuque-s4"),    # back to zhuque
        # Also search zhuque streets
        ("north", "zhuque-s3"),
        ("east", "xiemao"),       # shoe shop
        ("west", "zhuque-s3"),
        ("west", "maohuo"),       # fur shop
        ("east", "zhuque-s3"),
        ("north", "zhuque-s2"),
        ("east", "yaopu"),        # pharmacy
        ("west", "zhuque-s2"),
        ("west", "lefang"),       # entertainment
        ("east", "zhuque-s2"),
        ("north", "zhuque-s1"),
        ("west", "dangpu"),       # pawn shop
        ("east", "zhuque-s1"),
        ("east", "kezhan"),       # inn
        ("west", "zhuque-s1"),
    ]

    for d, label in search:
        go(s, d)
        desc, b = look(s)
        f, kid = is_monster(desc, "黑狮精", "heishi")
        if f:
            print(f"\n  ** FOUND {label}! ID: {kid} **")
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
        # Also search shizikou area and east city
        go(s,"north")  # shizikou
        for d in ["east","north","south","south","north","east","north","south",
                   "west","west","north","east","west","south"]:
            go(s, d)
            desc, b = look(s)
            f, kid = is_monster(desc, "黑狮精", "heishi")
            if f:
                print(f"\n  ** FOUND! ID: {kid} **")
                show("MONSTER!", b)
                killed = fight(s, kid)
                if killed:
                    print("\n  ********************************************")
                    print("  ***    FIRST KILL!!!                     ***")
                    print("  ********************************************")
                found = True
                break

if not found:
    print("\n  !! 黑狮精 not found anywhere in city")

# FINAL
print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)
print("\n*** Round 31 - NO QUIT ***")
time.sleep(1)
s.close()
