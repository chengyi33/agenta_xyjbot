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
        except: pass
    return b.replace(b"\x00", b"").decode("gbk", errors="replace")
def show(label, b):
    t = clean(b); print(f"\n--- {label} ---"); print(t[-3000:] if len(t) > 3000 else t)
def go(s, d):
    return clean(send(s, d.encode() + b"\r\n", quiet=1.0))
def look(s):
    b = send(s, b"look\r\n", quiet=1.5); return clean(b), b

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
    "Zhangmen","Shizhe","Sanhua","Xiao liu","Boy","Rat","Qiong han",
    "Oldman","Oldwoman","Keeper","Eryi","Woman","Youxia","Bookseller",
    "You ke","Xiao maolu","Qianke","Guitong","Jixian","Pablo",
    "Xiushi","Laosun","Shouchen","Xianglan","Xpo","Wei"]
def is_monster(desc, name, mid):
    for line in desc.split("\n"):
        line = line.strip()
        if "(" not in line or ")" not in line: continue
        if any(k in line for k in known_npcs): continue
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
    ids.extend(["guai","jing"])
    ids = list(dict.fromkeys(ids))
    for tid in ids:
        r = go(s, f"kill {tid}")
        if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
            print(f"  >> ENGAGED with 'kill {tid}'!"); break
    else:
        print(f"  !! Can't engage: {ids}"); return False
    print("  >> FIGHTING!")
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
                if lines: print(f"  [combat {j}] {lines[-1].strip()[:70]}")
    return False

print("Round 36: tieta → NORTHEAST → yao streets!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0); send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
if "y/n" in clean(b): send(s, b"y\r\n", quiet=4.0)
send(s, b"set wimpy 15\r\n", quiet=1.0)

# Get to tieta if not there
desc, _ = look(s)
print(f"  At: {desc[:50]}")

# Navigate to tieta from wherever in kaifeng
for _ in range(10):
    desc, _ = look(s)
    if "铁塔" in desc or "汴京" in desc: print("  >> AT TIETA!"); break
    if "舜王" in desc: go(s,"south"); continue
    if "古亭" in desc: go(s,"south"); continue
    if "御相" in desc: go(s,"east"); continue
    if "尧王" in desc:
        # Check room for monster before leaving!
        f, kid = is_monster(desc, "白狮怪", "Baishi guai")
        if f:
            print(f"  ** FOUND ON YAO STREET! ID: {kid} **")
            show("MONSTER!", send(s, b"look\r\n", quiet=1.5))
            killed = fight(s, kid)
            if killed:
                print("\n  *** FIRST KILL!!! ***")
            break
        go(s,"south"); continue
    if "辰龙" in desc: go(s,"east"); continue
    if "开封" in desc or "城门" in desc: go(s,"east"); continue
    go(s,"south")

desc, _ = look(s)
if "铁塔" in desc:
    # Search yao streets: northeast from tieta
    print("\n========== SEARCHING YAO STREETS ==========")
    # tieta -> northeast -> yao5
    # yao5 -> north -> yao4 -> north -> yao3 -> north -> yao2 -> north -> yao1
    # Plus side rooms: qili, lanting, dangpu, tianpeng
    search = [
        ("northeast", "yao5"),
        ("east", "qili"),
        ("west", "back to yao5"),
        ("north", "yao4"),
        ("east", "lanting"),
        ("east", "deeper lanting?"),
        ("west", "back"),
        ("west", "back to yao4"),
        ("north", "yao3"),
        ("east", "dangpu"),
        ("west", "back to yao3"),
        ("north", "yao2"),
        ("north", "yao1"),
        ("east", "tianpeng"),
        ("east", "deeper?"),
        ("west", "back"),
        ("west", "back to yao1"),
        ("northwest", "guting3"),
        ("south", "back?"),
        ("south", "yao2"),
        ("south", "yao3"),
        ("south", "yao4"),
        ("south", "yao5"),
        ("southwest", "tieta"),
        # Also search southeast from tieta (禹王道)
        ("southeast", "yuwang"),
        ("south", "yuwang2?"),
        ("north", "back"),
        ("northwest", "tieta"),
        # Search chen streets
        ("west", "chen2"),
        ("north", "machang?"),
        ("south", "chen2"),
        ("west", "chen1"),
        ("east", "chen2"),
    ]

    found = False
    for d, label in search:
        go(s, d)
        desc, b = look(s)
        f, kid = is_monster(desc, "白狮怪", "Baishi guai")
        if f:
            print(f"\n  ** FOUND 白狮怪 at {label}! ID: {kid} **")
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
        print(f"\n  !! 白狮怪 not found ({len(search)} rooms)")

print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0); show("HP", b)
b = send(s, b"score\r\n", quiet=3.0); show("SCORE", b)
print("\n*** Round 36 - NO QUIT ***")
time.sleep(1); s.close()
