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
def vgo(s, d, expect):
    go(s, d); desc, b = look(s)
    ok = expect in desc; room = desc.split("\n")[0].strip()[:30]
    print(f"  {d:12s} -> [{('OK' if ok else '??')}] {room}")
    return ok, desc, b

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
    "Taizong","Guanjia","Hezhizhang","Gongsun","Duguoyin"]

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
    # Try: full id, suffix (jing/guai), then generic
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

def goto_hub(s):
    for _ in range(25):
        desc, _ = look(s)
        if "十字街头" in desc: return True
        if "南城客栈" in desc: go(s,"west"); go(s,"north"); continue
        if "朱雀" in desc and "客栈" in desc: go(s,"north"); continue
        if "朱雀" in desc: go(s,"north"); continue
        if "白虎" in desc: go(s,"east"); continue
        if "青龙" in desc: go(s,"west"); continue
        if "玄武" in desc: go(s,"south"); continue
        if "天监" in desc: go(s,"east"); go(s,"south"); continue
        if "当铺" in desc: go(s,"east"); go(s,"north"); continue
        if "武馆" in desc: go(s,"south"); go(s,"west"); continue
        if "兵器" in desc: go(s,"north"); go(s,"west"); continue
        if "南城口" in desc: go(s,"north"); go(s,"north"); go(s,"north"); go(s,"north"); continue
        if "背阴" in desc or "民居" in desc or "粮" in desc or "小酒馆" in desc: go(s,"north"); continue
        if "药铺" in desc or "乐坊" in desc or "毛货" in desc or "鞋帽" in desc or "杂货" in desc: go(s,"north"); continue
        if "朝阳门" in desc: go(s,"south"); continue
        if "国子监" in desc: go(s,"west"); go(s,"south"); continue
        if "化生" in desc or "书局" in desc or "钱庄" in desc: go(s,"south"); go(s,"east"); continue
        if "方丈" in desc or "大雄" in desc: go(s,"north"); go(s,"east"); continue
        if "东门" in desc: go(s,"west"); continue
        # Kaifeng escape
        if "马场" in desc: go(s,"north"); continue  # machang→chen2
        if "辰龙" in desc or "开封" in desc or "城门" in desc: go(s,"west"); continue
        if "铁塔" in desc or "汴京" in desc: go(s,"west"); continue
        if "舜王" in desc or "古亭" in desc: go(s,"south"); continue
        if "尧王" in desc: go(s,"south"); continue
        if "御相" in desc: go(s,"east"); continue
        if "禹王" in desc: go(s,"northwest"); continue
        if "天蓬" in desc or "帅府" in desc or "七里" in desc or "兰亭" in desc or "翠兰" in desc or "玉兰" in desc or "香兰" in desc: go(s,"west"); continue
        if "当铺" in desc: go(s,"west"); continue  # kaifeng dangpu
        if "春醇" in desc or "杨记" in desc: go(s,"east"); continue
        # Putuo escape
        if "山門" in desc or "山门" in desc: go(s,"southdown"); continue
        if "山路" in desc: go(s,"south"); go(s,"southdown"); continue
        if "听经" in desc or "小岛" in desc: go(s,"south"); continue
        if "南海之滨" in desc:
            for _ in range(16): go(s,"north")
            continue
        if "竹林" in desc or "落伽" in desc or "广场" in desc or "禅房" in desc: go(s,"south"); continue
        # South of city
        if "大官道" in desc or "终南" in desc or "南岳" in desc or "泾水" in desc: go(s,"north"); continue
        go(s,"north")
    return False

# ============================================
print("Round 37: FULL CHECKLIST EXECUTION")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0); send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
if "y/n" in clean(b): send(s, b"y\r\n", quiet=4.0)
send(s, b"set wimpy 15\r\n", quiet=1.0)

# STEP 1: Get to hub
print("\n[1] GET TO HUB")
goto_hub(s)
desc, _ = look(s)
print(f"  At: {desc[:30]}")

# STEP 2: Check gear
print("\n[2] CHECK GEAR")
b = send(s, b"score\r\n", quiet=3.0)
sc = clean(b)
if "兵器伤害力：[0]" in sc or "盔甲保护力：[1]" in sc.replace("16",""):
    print("  Need gear!")
    vgo(s,"east","青龙"); vgo(s,"south","兵器")
    send(s, b"buy blade from xiao xiao\r\n", quiet=1.5)
    send(s, b"wield blade\r\n", quiet=1.5)
    if "盔甲保护力：[1]" in sc:
        send(s, b"buy shield from xiao xiao\r\n", quiet=1.5)
        send(s, b"wear shield\r\n", quiet=1.5)
    vgo(s,"north","青龙"); vgo(s,"west","十字")
else:
    print("  Gear OK!")

# STEP 3: Buy food
print("\n[3] FOOD")
vgo(s,"south","朱雀"); vgo(s,"east","客栈")
for _ in range(3): send(s, b"buy jitui from xiao er\r\n", quiet=0.8)
send(s, b"buy jiudai from xiao er\r\n", quiet=0.8)
for _ in range(3): send(s, b"eat jitui\r\n", quiet=0.5)
send(s, b"drink jiudai\r\n", quiet=0.5)

b = send(s, b"score\r\n", quiet=3.0)
show("READY", b)

# STEP 4: Ask yuan
print("\n[4] YUAN MISSION")
vgo(s,"west","朱雀"); vgo(s,"north","十字"); vgo(s,"north","玄武"); vgo(s,"west","天监")
b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
yuan = clean(b); show("MISSION", b)

mn = None; mid = None; loc = None
m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
if m: mn=m.group(1); mid=m.group(2).strip(); loc=m.group(3)
elif "除尽" in yuan:
    b = send(s, b"ask yuan about kill\r\n", quiet=3.0); yuan=clean(b); show("NEW",b)
    m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', yuan)
    if m: mn=m.group(1); mid=m.group(2).strip(); loc=m.group(3)
elif "收服" in yuan:
    m2 = re.search(r'收服(.+?)吗', yuan)
    if m2: mn=m2.group(1); mid="guai"
print(f"\n  TARGET: {mn} ({mid}) @ {loc}")

# STEP 5: Travel + Search + Kill
if mn:
    print(f"\n[5] HUNT {mn}")
    vgo(s,"east","玄武"); vgo(s,"south","十字")
    l = loc or ""

    if "普陀" in l:
        print("  PUTUO route")
        for _ in range(16): go(s,"south")
        go(s,"swim"); go(s,"north"); go(s,"north"); go(s,"northup"); go(s,"northup")
        srch = ["north"]*5+["east","west"]+["south"]*5+["west"]*2+["east"]*3+["south"]*3+["enter","out"]
    elif "开封" in l:
        print("  KAIFENG route")
        for _ in range(13): go(s,"east")
        if "尧" in l:
            go(s,"northeast")  # tieta→yao5
            srch = ["north","east","west","north","east","west","north","north",
                    "east","west","south","south","south","south","southwest",
                    "northwest","north","north","west","east","north","north",
                    "south","south","south","south","southeast"]
        elif "舜" in l or "御相" in l:
            go(s,"northwest")  # tieta→shun5
            srch = ["north","north","west","east","north","north",
                    "south","south","south","south","southeast"]
        else:
            go(s,"northeast")
            srch = ["north"]*4+["south"]*4+["southwest","northwest"]+["north"]*4+["south"]*4+["southeast"]
    elif "望南" in l:
        print("  WANGNAN route")
        for _ in range(3): go(s,"east")
        go(s,"south")
        srch = ["southwest","south","west","southwest","northeast","east","north","northeast","east","west"]
    elif "粮" in l:
        print("  LIANGCANG route")
        go(s,"south"); go(s,"south"); go(s,"south"); go(s,"south")
        go(s,"west"); go(s,"northwest"); go(s,"east")
        srch = ["west","west","south","north","north","south","east","southeast","south","north","east","north","north","north","north"]
    else:
        print(f"  CITY search: '{l}'")
        srch = ["south","east","west","west","east",
                "south","east","west","south","east","west","south",
                "west","northwest","east","west","west","south","north",
                "north","south","east","southeast","south","north",
                "east","north","north","north","north",
                "east","north","south","east","north","south",
                "west","west","west","south","north",
                "west","south","north","east","east",
                "north","east","west","south"]

    found = False
    for i, d in enumerate(srch):
        go(s, d)
        desc, b = look(s)
        f, kid = is_monster(desc, mn, mid)
        if f:
            print(f"\n  ** FOUND {mn}! ID: {kid} step {i} **")
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
                goto_hub(s); vgo(s,"north","玄武"); vgo(s,"west","天监")
                b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
                show("YUAN REPORT", b)
            found = True; break
    if not found:
        print(f"\n  !! {mn} not found ({len(srch)} rooms)")

print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0); show("HP", b)
b = send(s, b"score\r\n", quiet=3.0); show("SCORE", b)
print("\n*** Round 37 - NO QUIT ***")
time.sleep(1); s.close()
