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
    "Gao tai","Cuiying","Xiao ying","Lao liu","Tiejiang"]
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

print("Round 39: TARGETED SEARCH — 偏房 in 高老庄!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0); send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
if "y/n" in clean(b): send(s, b"y\r\n", quiet=4.0)
send(s, b"set wimpy 15\r\n", quiet=1.0)

desc, _ = look(s)
print(f"  At: {desc[:40]}")

# Get to shizikou first, then travel to gao
# From wherever I am, go north until shizikou
for _ in range(20):
    desc, _ = look(s)
    if "十字街头" in desc: print("  >> HUB!"); break
    if "客栈" in desc: go(s,"west"); go(s,"north"); continue
    if "朱雀" in desc: go(s,"north"); continue
    if "白虎" in desc: go(s,"east"); continue
    if "青龙" in desc: go(s,"west"); continue
    if "玄武" in desc: go(s,"south"); continue
    if "天监" in desc: go(s,"east"); go(s,"south"); continue
    if "当铺" in desc: go(s,"east"); go(s,"north"); continue
    if "南城口" in desc: go(s,"north"); go(s,"north"); go(s,"north"); go(s,"north"); continue
    if "土路" in desc or "高" in desc or "街道" in desc: go(s,"east"); continue  # go east toward changan
    if "大官道" in desc or "终南" in desc or "南岳" in desc or "泾水" in desc: go(s,"north"); continue
    if "背阴" in desc or "民居" in desc: go(s,"north"); continue
    go(s,"north")

desc, _ = look(s)
if "十字街头" not in desc:
    print(f"  !! Not at hub: {desc[:30]}")

# Travel to 高老庄: south x13 + west x4
print("\n  Sprinting to 高老庄...")
for _ in range(13): go(s,"south")
for _ in range(4): go(s,"west")
desc, _ = look(s)
print(f"  At gao area: {desc[:40]}")

# TARGETED SEARCH based on map:
# From 土路(lu1), go east to 街道, east to 高家大门, then search compound
# Map: 土路─土路─街道─街道─高家大门─街道─土路─青石路
#                              |
#                   帐房─正院─偏房  ← TARGET
#                              |
#                   偏厅─正厅─饭厅
#                              |
#                        闺阁─后院─洗衣房
#                              |
#                        雅室  花园
print("\n========== TARGETED SEARCH ==========")
# Go east along the main road to find 高家大门
search = [
    # Main road: lu1 → streets → gate → compound
    ("east", "lu2/street"),
    ("east", "street/gate area"),
    ("east", "more street"),
    ("east", "高家大门?"),
    ("enter", "try enter"),
    ("north", "正院?"),
    ("east", "偏房? TARGET!"),
    ("west", "back to 正院"),
    ("west", "帐房?"),
    ("east", "back to 正院"),
    ("north", "正厅?"),
    ("east", "饭厅?"),
    ("west", "back to 正厅"),
    ("west", "偏厅?"),
    ("east", "back to 正厅"),
    ("north", "后院?"),
    ("east", "洗衣房?"),
    ("west", "back to 后院"),
    ("west", "闺阁?"),
    ("north", "雅室?"),
    ("south", "back"),
    ("east", "back to 后院"),
    ("east", "花园?"),
    ("west", "back"),
    ("south", "正厅"),
    ("south", "正院"),
    ("south", "高家大门"),
    # Also check streets east and west of gate
    ("east", "street east of gate"),
    ("east", "more"),
    ("west", "back"),
    ("west", "gate"),
    ("west", "street west"),
    ("west", "more west"),
    ("south", "maybe 铁铺/酒馆"),
    ("north", "back"),
    ("west", "lu area"),
    ("south", "稻田"),
    ("south", "more"),
    ("south", "村口?"),
    ("east", "农舍?"),
    ("west", "back"),
    ("south", "书堂?"),
]

found = False
for i, (d, label) in enumerate(search):
    go(s, d)
    desc, b = look(s)
    room = desc.split("\n")[0].strip()[:20]
    f, kid = is_monster(desc, "白猫精", "Baimao jing")
    if f:
        print(f"\n  ** FOUND 白猫精 at [{label}]! ID: {kid} **")
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
    elif i % 5 == 0:
        print(f"  [{i}] {d:8s} -> {room}")

if not found:
    print(f"\n  !! 白猫精 not found ({len(search)} rooms in 高老庄)")

print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0); show("HP", b)
b = send(s, b"score\r\n", quiet=3.0); show("SCORE", b)
print("\n*** Round 39 - NO QUIT ***")
time.sleep(1); s.close()
