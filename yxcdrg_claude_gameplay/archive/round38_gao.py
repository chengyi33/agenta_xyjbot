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
def send(s, d, quiet=2.0): s.sendall(d); return drain(s, quiet=quiet)
def clean(b):
    for enc in ["utf-8", "gbk"]:
        try:
            t = b.replace(b"\x00", b"").decode(enc)
            return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", t)
        except: pass
    return b.replace(b"\x00", b"").decode("gbk", errors="replace")
def show(label, b):
    t = clean(b); print(f"\n--- {label} ---"); print(t[-3000:] if len(t) > 3000 else t)
def go(s, d): return clean(send(s, d.encode() + b"\r\n", quiet=1.0))
def look(s):
    b = send(s, b"look\r\n", quiet=1.5); return clean(b), b

known = ["Board","paizi","Agenta","Snoopl","Snoopy","Xiao er","Da ye",
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
    "Zhangmen","Shizhe","Sanhua","Xiao liu","Boy","Rat","Qiong han",
    "Oldman","Oldwoman","Keeper","Eryi","Woman","Youxia","Bookseller",
    "You ke","Xiao maolu","Qianke","Guitong","Jixian","Pablo",
    "Xiushi","Laosun","Shouchen","Xianglan","Xpo","Wei",
    "Daozhang","Libai","Teawaiter","Jiading","Liyu","Xiaowang",
    "Taizong","Guanjia","Hezhizhang","Gongsun","Duguoyin",
    "Gao tai","Cuiying","Xiao ying"]
def is_monster(desc, name, mid):
    for line in desc.split("\n"):
        line = line.strip()
        if "(" not in line or ")" not in line: continue
        if any(k in line for k in known): continue
        if name and name in line:
            m = re.search(r'\(([^)]+)\)', line)
            return True, m.group(1).strip() if m else mid
        if mid and mid.lower() in line.lower():
            m = re.search(r'\(([^)]+)\)', line)
            return True, m.group(1).strip() if m else mid
    return False, None
def fight(s, kid):
    ids = [kid]
    if " " in kid: ids.append(kid.split()[-1])
    ids.extend(["jing","guai"])
    ids = list(dict.fromkeys(ids))
    for tid in ids:
        r = go(s, f"kill {tid}")
        if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
            print(f"  >> ENGAGED: kill {tid}"); break
    else:
        print(f"  !! Can't engage: {ids}"); return False
    for j in range(50):
        time.sleep(3)
        b = drain(s, quiet=2.0, maxt=5.0)
        if b:
            r = clean(b)
            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                show("**** VICTORY! ****", b); return True
            elif "承让" in r: print("  >> LOST"); return False
            elif "找机会逃跑" in r: print("  >> FLED"); return False
            elif "清醒" in r: print("  >> KO'd"); return False
            elif j % 5 == 0:
                lines = [l for l in r.split("\n") if l.strip() and ">" not in l]
                if lines: print(f"  [{j}] {lines[-1].strip()[:70]}")
    return False

print("Round 38: SPRINT TO 高老庄!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0); send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
if "y/n" in clean(b): send(s, b"y\r\n", quiet=4.0)
send(s, b"set wimpy 15\r\n", quiet=1.0)

# Should still be near shizikou from last round. Get there fast.
desc, _ = look(s)
print(f"  At: {desc[:40]}")
for _ in range(15):
    desc, _ = look(s)
    if "十字街头" in desc: print("  >> HUB!"); break
    if "朱雀" in desc: go(s,"north"); continue
    if "白虎" in desc: go(s,"east"); continue
    if "青龙" in desc: go(s,"west"); continue
    if "客栈" in desc: go(s,"west"); go(s,"north"); continue
    if "当铺" in desc: go(s,"east"); go(s,"north"); continue
    if "背阴" in desc or "民居" in desc: go(s,"north"); continue
    if "南城口" in desc: go(s,"north"); go(s,"north"); go(s,"north"); go(s,"north"); continue
    go(s,"north")

# Route: shizikou → south x13 → west x4 → 高老庄
print("\n  Traveling to 高老庄: south x13 + west x4...")
for i in range(13):
    go(s, "south")
    if i % 4 == 0:
        d, _ = look(s)
        print(f"  south [{i+1}] {d[:30]}")

for i in range(4):
    go(s, "west")
d, b = look(s)
show("AT GAO?", b)

# Search 高老庄 area for 白猫精
print("\n========== SEARCHING 高老庄 ==========")
# gao area rooms: lu1, lu2, streets, houses
search = [
    "west","west","west",  # further into gao
    "east","east","east",  # back
    "north","north","north",  # north streets
    "east","west",
    "south","south","south",  # back
    "south","south",  # south streets
    "east","west",
    "north","north",
    "west","west",
    "north","south",
    "east","east",
    "enter","out",  # try entering buildings
    "south","south",
    "east","west",
    "north","north","north",
]

found = False
for i, d in enumerate(search):
    go(s, d)
    desc, b = look(s)
    f, kid = is_monster(desc, "白猫精", "Baimao jing")
    if f:
        print(f"\n  ** FOUND 白猫精! ID: {kid} step {i} **")
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
        found = True; break

if not found:
    print(f"\n  !! 白猫精 not found ({len(search)} rooms)")

print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0); show("HP", b)
b = send(s, b"score\r\n", quiet=3.0); show("SCORE", b)
print("\n*** Round 38 - NO QUIT ***")
time.sleep(1); s.close()
