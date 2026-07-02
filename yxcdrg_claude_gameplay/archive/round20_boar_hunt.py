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

def where(s):
    b = send(s, b"look\r\n", quiet=2.0)
    t = clean(b)
    locs = [("南城客栈","kezhan"),("十字街头","shizikou"),("天监台","tianjiantai"),
            ("朱雀大街","zhuque"),("白虎大街","baihu"),("青龙大街","qinglong"),
            ("玄武大街","xuanwu"),("长安武馆","wuguan"),("兵器铺","weaponshop"),
            ("董记当铺","dangpu"),("望南街","wangnan"),("进士场","jinshi"),
            ("碑林","beilin"),("大官道","guandao"),("货行","huohang")]
    for kw, name in locs:
        if kw in t:
            return name, t, b
    return "other", t, b

def go_to_shizikou(s):
    for _ in range(8):
        loc, desc, _ = where(s)
        if loc == "shizikou": return True
        nav = {"kezhan":"west north","zhuque":"north","baihu":"east",
               "qinglong":"west","xuanwu":"south","dangpu":"east north",
               "tianjiantai":"east south","wuguan":"south west",
               "weaponshop":"north west","wangnan":"north","jinshi":"east north",
               "guandao":"north","huohang":"west north","beilin":"south east"}
        dirs = nav.get(loc, "south").split()
        for d in dirs:
            go(s, d)
    return False

print("Round 20: HUNT THE BOAR - 野猪精 at 望南街!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
if "y/n" in clean(b):
    send(s, b"y\r\n", quiet=4.0)

send(s, b"set wimpy 15\r\n", quiet=1.0)

# Check if we already have the blade
b = send(s, b"i\r\n", quiet=2.0)
inv = clean(b)
show("INVENTORY", b)

if "钢刀" not in inv:
    print("\n  Need to buy weapon first!")
    go_to_shizikou(s)
    go(s, "east")   # qinglong
    go(s, "south")  # weaponshop
    b = send(s, b"buy blade from xiao xiao\r\n", quiet=2.0)
    show("BUY BLADE", b)
    b = send(s, b"wield blade\r\n", quiet=2.0)
    show("WIELD", b)

# Also buy food if low
if "炸鸡腿" not in inv:
    go_to_shizikou(s)
    go(s, "south")  # zhuque
    go(s, "east")   # kezhan
    send(s, b"buy jitui from xiao er\r\n", quiet=2.0)
    send(s, b"buy jitui from xiao er\r\n", quiet=2.0)
    send(s, b"buy jiudai from xiao er\r\n", quiet=2.0)
    send(s, b"eat jitui\r\n", quiet=2.0)
    send(s, b"drink jiudai\r\n", quiet=2.0)

b = send(s, b"hp\r\n", quiet=2.0)
show("HP READY", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)

# ============================================
# Navigate to 望南街 area and search for 野猪精
# Path: shizikou -> east -> east -> east (qinglong-e3) -> south (wangnan1)
# Then search all wangnan rooms + connected rooms
# ============================================
print("\n========== SEARCHING 望南街 FOR 野猪精 ==========")
go_to_shizikou(s)

# Go to wangnan via qinglong east
go(s, "east")   # qinglong-e1
go(s, "east")   # qinglong-e2
go(s, "east")   # qinglong-e3
go(s, "south")  # wangnan1

# Search pattern: cover all wangnan + nearby rooms
# wangnan1 -> huohang -> back -> sw -> wangnan2 -> jinshi -> back
# -> south -> wangnan3 -> guandao2 -> back -> west -> wangnan4
# -> jinshi -> back -> sw -> wangnan5 -> guandao1 -> back
search_path = [
    # wangnan1
    ("look", "wangnan1"),
    ("east", "huohang"),
    ("west", "back to wangnan1"),
    ("southwest", "wangnan2"),
    ("west", "jinshi"),
    ("east", "back to wangnan2"),
    ("south", "wangnan3"),
    ("southeast", "guandao2"),
    ("northwest", "back to wangnan3 area"),
    ("west", "wangnan4"),
    ("north", "jinshi from south"),
    ("south", "back to wangnan4"),
    ("southwest", "wangnan5"),
    ("southeast", "guandao1"),
    ("northwest", "back to wangnan5 area"),
    # Also check beilin
    ("northeast", "back to wangnan4"),
    ("east", "wangnan3"),
    ("north", "wangnan2"),
    ("northeast", "wangnan1"),
    ("north", "qinglong-e3"),
    # Try south of qinglong for more rooms
    ("west", "qinglong-e2"),
    ("south", "maybe more rooms"),
    ("north", "back"),
    ("west", "qinglong-e1"),
    ("south", "maybe weaponshop"),
]

found = False
monster_ids = ["yezhu", "yezhu jing"]  # possible IDs for 野猪精

for direction, label in search_path:
    if direction == "look":
        b = send(s, b"look\r\n", quiet=1.5)
    else:
        b = go(s, direction)
        # Also look to get full room description
        b2 = send(s, b"look\r\n", quiet=1.5)
        b = b + b2

    desc = clean(b)

    # Check for 野猪精 or yezhu
    if "野猪" in desc or "yezhu" in desc.lower():
        print(f"\n  ** FOUND 野猪精 at {label}! **")
        show("MONSTER ROOM", b)
        found = True

        # KILL IT!
        print("\n  >> KILLING 野猪精!")
        # Try multiple ID formats
        for mid in ["yezhu", "yezhu jing", "jing"]:
            b = send(s, f"kill {mid}\r\n".encode(), quiet=2.0)
            r = clean(b)
            if "想攻击谁" not in r and "没有" not in r and "什么" not in r:
                show("KILL!", b)
                break
        else:
            # Try fight
            for mid in ["yezhu", "yezhu jing", "jing"]:
                b = send(s, f"fight {mid}\r\n".encode(), quiet=2.0)
                r = clean(b)
                if "想攻击谁" not in r and "什么" not in r:
                    show("FIGHT!", b)
                    break

        # Watch combat
        killed = False
        for i in range(35):
            time.sleep(3)
            b = drain(s, quiet=2.0, maxt=5.0)
            if b:
                r = clean(b)
                if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开"]):
                    show("*** VICTORY! ***", b)
                    killed = True
                    break
                elif "承让" in r:
                    show("LOST", b)
                    break
                elif "找机会逃跑" in r:
                    # We're fleeing - try to come back
                    show("FLEEING (trying to return)", b)
                    time.sleep(3)
                    b = drain(s, quiet=2.0, maxt=3.0)
                    if b: show("AFTER FLEE", b)
                    break
                elif i % 5 == 0:
                    show(f"COMBAT {i+1}", b)

        if killed:
            print("\n  ************************************")
            print("  ***  YUAN MISSION COMPLETE!!!   ***")
            print("  ************************************")
            time.sleep(3)
            b = drain(s, quiet=2.0, maxt=5.0)
            if b: show("AFTERMATH", b)

            # Go back to yuan to report
            go_to_shizikou(s)
            go(s, "north")  # xuanwu
            go(s, "west")   # tianjiantai
            b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
            show("REPORT TO YUAN", b)
        break

if not found:
    print("\n  !! 野猪精 not found in 望南街 area")
    print("  !! It may have despawned or be in a room we didn't search")
    print("  !! Try asking yuan again for a new mission")

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

print("\n*** Round 20 ended - NO QUIT ***")
time.sleep(1)
s.close()
