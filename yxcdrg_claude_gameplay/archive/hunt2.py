"""
Hunt v2: hardcoded path, drain buffer between moves, simple and reliable.
"""
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

def send(s,d,quiet=2.0): s.sendall(d); return drain(s,quiet=quiet)

def clean(b):
    for enc in ["utf-8","gbk"]:
        try: t=b.replace(b"\x00",b"").decode(enc); return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]","",t)
        except: pass
    return b.replace(b"\x00",b"").decode("gbk",errors="replace")

def show(label,b):
    t=clean(b); print(f"\n--- {label} ---"); print(t[-2500:] if len(t)>2500 else t)

def move(s, d):
    """Move and drain buffer cleanly."""
    r = clean(send(s, d.encode()+b"\r\n", quiet=1.0))
    drain(s, quiet=0.3, maxt=1.0)  # clear any extra output
    return r

def look(s):
    drain(s, quiet=0.3, maxt=1.0)  # clear buffer first
    b = send(s, b"look\r\n", quiet=1.5)
    return clean(b), b

def check_room(s, keyword):
    desc, _ = look(s)
    return keyword in desc, desc

def go_to_kezhan_from_hub(s):
    move(s,"south"); move(s,"east")
    ok, desc = check_room(s, "南城客栈")
    if not ok: print(f"  !! Not at kezhan: {desc[:40]}")
    return ok

def go_to_hub_from_kezhan(s):
    move(s,"west"); move(s,"north")
    ok, desc = check_room(s, "十字街头")
    if not ok: print(f"  !! Not at hub: {desc[:40]}")
    return ok

def go_to_hub_from_zhuque(s):
    move(s,"north")
    ok, desc = check_room(s, "十字街头")
    if not ok: print(f"  !! Not at hub: {desc[:40]}")
    return ok

KNOWN = {"Board","paizi","Agenta","Snoopl","Snoopy","Xiao er","Da ye","Qianli",
    "Fan luping","Wuguan dizi","Xiao xiao","Yuan tiangang","Li bai","Zhang guolao",
    "Jieding","Xiucai","Wei shi","Xiao bing","Laitou","Zodiac","Yang zhong",
    "Monk","Heshang","Faming","Dong push","Kong fang","Tie suanpan","Kuli",
    "Jia er","Horse","Maguan","People","Zhike","Luren","Youke","Sengren","Bing",
    "Dai","Girl","Hai","Chen","Xu","Ye","Yin","Zu","Xgong","Yahuan","Yang",
    "Chaniang","Hu","Xiaotong","Gongwei","Siguan","Wu jiang","Zhubing","Reporting",
    "Lao tou","Xiao liumang","Biao","Xiao pizi","Lao wei","Xiao wang","Gui tong",
    "Dahan","Haoke","Tiejiang","Huangbiao","Feng","Jin","Huian","Nuocha","Zhangmen",
    "Shizhe","Sanhua","Xiao liu","Boy","Rat","Qiong han","Oldman","Oldwoman",
    "Keeper","Eryi","Woman","Youxia","Bookseller","You ke","Xiao maolu","Qianke",
    "Guitong","Jixian","Pablo","Laosun","Shouchen","Xianglan","Wei","Daozhang",
    "Libai","Teawaiter","Taizong","Hezhizhang","Gongsun","Gao tai","Cuiying",
    "Xiao ying","Xiushi"}

def find_monster(desc, name):
    for line in desc.split("\n"):
        line=line.strip()
        if "(" not in line or ")" not in line: continue
        if any(k in line for k in KNOWN): continue
        if name and name in line: return True
    return False

def fight(s):
    for tid in ["jing","guai"]:
        r = clean(send(s, f"kill {tid}\r\n".encode(), quiet=2.0))
        if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
            print(f"  >> ENGAGED: kill {tid}!")
            break
    else:
        print(f"  !! Can't engage"); return False

    for j in range(60):
        time.sleep(3)
        b = drain(s, quiet=2.0, maxt=5.0)
        if b:
            r=clean(b)
            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                show("**** KILL! ****", b); return True
            elif "承让" in r: print("  >> Lost"); return False
            elif "找机会逃跑" in r:
                print("  >> Fled — re-engaging")
                time.sleep(2); drain(s,quiet=1.0,maxt=2.0)
                desc2,_=look(s)
                # Try to re-engage if monster still here
                for tid2 in ["jing","guai"]:
                    r2=clean(send(s,f"kill {tid2}\r\n".encode(),quiet=2.0))
                    if any(w in r2 for w in ["喝道","想杀","领教","奉陪"]):
                        print("  >> Re-engaged!"); break
            elif "清醒" in r: print("  >> KO'd"); return False
            elif j%5==0:
                lines=[l for l in r.split("\n") if l.strip() and ">"not in l]
                if lines: print(f"  [{j}] {lines[-1].strip()[:70]}")
    return False

def search_and_kill(s, monster_name, search_dirs):
    for i, d in enumerate(search_dirs):
        move(s, d)
        desc, _ = look(s)
        if find_monster(desc, monster_name):
            print(f"\n  ** FOUND {monster_name} at step {i}! **")
            show("MONSTER", send(s, b"look\r\n", quiet=1.5))
            return fight(s)
        if i%10==0: print(f"  searching {i}/{len(search_dirs)}...")
    return False

# ============================================
print("=== HUNT v2 ===")
s = socket.create_connection(("146.190.143.182",6666),timeout=15)
drain(s,quiet=3.0,maxt=12.0)
move(s,"gb"); move(s,"no"); move(s,"yxcdrg")
r = clean(send(s,b"198633\r\n",quiet=4.0))
if "y/n" in r: move(s,"y")

move(s,"set wimpy 5")
desc,_ = look(s)
print(f"Start: {desc[:40]}")

# ============================================
# Navigate to shizikou (hub) from wherever
# ============================================
print("\n[1] GET TO HUB")
# Try navigating — do it step by step with verification
for attempt in range(35):
    desc, _ = look(s)
    if "十字街头" in desc: print("  AT HUB!"); break
    if "南城客栈" in desc: move(s,"west"); move(s,"north"); continue
    if "朱雀大街" in desc:
        if "客栈" in desc: move(s,"north")
        else: move(s,"north")
        continue
    if "白虎大街" in desc: move(s,"east"); continue
    if "青龙大街" in desc: move(s,"west"); continue
    if "玄武大街" in desc: move(s,"south"); continue
    if "天监台" in desc: move(s,"east"); move(s,"south"); continue
    if "武馆" in desc: move(s,"south"); move(s,"west"); continue
    if "兵器铺" in desc: move(s,"north"); move(s,"west"); continue
    if "当铺" in desc: move(s,"east"); move(s,"north"); continue
    if "南城口" in desc:
        for _ in range(4): move(s,"north")
        continue
    if "大官道" in desc:
        if "平原" in desc or "由东西" in desc or "长安以东" in desc: move(s,"west")
        else: move(s,"north")
        continue
    if "终南" in desc or "南岳" in desc or "泾水" in desc: move(s,"north"); continue
    if "背阴" in desc or "民居" in desc or "粮" in desc: move(s,"north"); continue
    if "汴京铁塔" in desc: move(s,"west"); continue
    if "天蓬" in desc or "帅府" in desc: move(s,"west"); continue
    if "舜王街" in desc: move(s,"south"); move(s,"southeast"); continue  # shun→south or shun5→tieta
    if "尧王街" in desc: move(s,"south"); move(s,"southwest"); continue  # yao→south or yao5→tieta
    if "辰龙" in desc or "开封城门" in desc: move(s,"west"); continue
    if "东门" in desc or "长安城东门" in desc: move(s,"west"); continue  # dongmen → qinglong
    if "国子监" in desc: move(s,"west"); continue  # guozijian → xuanwu
    # Kaifeng catch-all: any Kaifeng room → go west to get back to Chang'an
    kaifeng_kw = ["杨记","春醇","七里","兰亭","翠兰","玉兰","香兰","钱庄",
                  "万寿","宁心","静心","清心","三心","禹王","古亭",
                  "酒楼","盔甲","兵器场","帅府","天蓬","西湖路","东湖路"]
    if any(k in desc for k in kaifeng_kw): move(s,"west"); continue
    if "山路" in desc: move(s,"south"); continue
    if "听经" in desc or "小岛" in desc: move(s,"south"); continue
    if "南海之滨" in desc:
        for _ in range(16): move(s,"north")
        continue
    move(s,"north")

desc,_ = look(s)
if "十字街头" not in desc: print(f"!! Not at hub: {desc[:40]}")

# ============================================
# STEP 1: Kezhan — food
# ============================================
print("\n[2] FOOD AT KEZHAN")
move(s,"south"); move(s,"east")
ok, desc = check_room(s,"南城客栈")
print(f"  At kezhan: {ok}")
if ok:
    # Buy gourou (food) and jiudai (drink)
    for _ in range(5): move(s,"buy gourou from xiao er")
    for _ in range(3): move(s,"buy jiudai from xiao er")
    # Eat and drink to full
    for _ in range(8): move(s,"eat gourou")
    for _ in range(5): move(s,"drink jiudai")
    b=send(s,b"hp\r\n",quiet=2.0); show("HP",b)

# ============================================
# STEP 2: Weapon shop
# ============================================
print("\n[3] WEAPON SHOP")
move(s,"west"); move(s,"north")  # kezhan→朱雀→十字
move(s,"east"); move(s,"south")  # 十字→青龙→兵器铺
ok2, desc2 = check_room(s,"兵器铺")
print(f"  At shop: {ok2}")
if ok2:
    move(s,"buy blade from xiao xiao"); move(s,"wield blade")
    move(s,"buy shield from xiao xiao"); move(s,"wear shield")
    print("  Blade + Shield!")
else:
    print(f"  !! Not at shop: {desc2[:40]}")

b=send(s,b"score\r\n",quiet=3.0); show("SCORE",b)

# ============================================
# STEP 3: Yuan mission
# ============================================
print("\n[4] YUAN MISSION")
move(s,"north"); move(s,"west")  # 兵器铺→青龙→十字
move(s,"north"); move(s,"west")  # 十字→玄武→天监台
ok3, desc3 = check_room(s,"天监台")
print(f"  At yuan: {ok3}")

if not ok3:
    # Try alternate path: get to hub first
    print("  Retrying via hub...")
    move(s,"east"); move(s,"south")  # wherever→east/south
    desc_t,_ = look(s)
    if "十字" not in desc_t:
        for _ in range(5): move(s,"north")
    move(s,"north"); move(s,"west")
    ok3, desc3 = check_room(s,"天监台")

b4=send(s,b"ask yuan about kill\r\n",quiet=3.0)
yuan=clean(b4); show("YUAN",b4)

monster_name=None; monster_loc=None
m=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan)
if m:
    monster_name=m.group(1); monster_loc=m.group(3)
    print(f"  MISSION: {monster_name} @ {monster_loc}")
elif "除尽" in yuan:
    b5=send(s,b"ask yuan about kill\r\n",quiet=3.0)
    yuan=clean(b5); show("NEW",b5)
    m=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan)
    if m: monster_name=m.group(1); monster_loc=m.group(3)
elif "收服" in yuan:
    m2=re.search(r'收服(.+?)吗',yuan)
    if m2: monster_name=m2.group(1); monster_loc="search_all"
    print(f"  ACTIVE (no loc): {monster_name} — will search all areas")

# ============================================
# STEP 4: Hunt
# ============================================
killed = False
if monster_name and monster_loc and monster_loc not in ("old",):
    print(f"\n[5] HUNT {monster_name} @ {monster_loc}")
    # Back to hub
    move(s,"east"); move(s,"south")  # tianjiantai→xuanwu→hub
    desc_hub,_ = look(s)
    if "十字" not in desc_hub:
        # force hub
        for _ in range(3): move(s,"south")

    loc = monster_loc or ""

    if "长安城西" in loc or "westway" in loc.lower():
        print("  ROUTE: westway (west x5 from hub)")
        move(s,"west"); move(s,"west"); move(s,"west"); move(s,"west"); move(s,"west")
        search = (["west"]*5+["east"]*3+["south","north"]*3+
                  ["west"]*3+["east"]*3+["south"]*2+["north"]*2)
    elif "search_all" in loc:
        print("  ROUTE: search city + westway + kaifeng")
        # City search first
        search = (["south","east","west","west","east","south","east","west",
                  "south","east","west","south","west","northwest","east","west",
                  "west","south","north","north","south","east","southeast","south",
                  "north","east","north","north","north","north",
                  "east","north","south","west","west","west","south","north",
                  "west","south","north","east","east","north","east","west","south"]
                  # Westway: hub -> west x5
                  + ["east","north","west","west","west","west","west",
                     "east","east","south","north","west","east"]
                  # Kaifeng: hub -> east x13 -> northeast (yao) -> north x4 -> northwest (guting) -> 西湖路
                  + ["east"]*13 + ["northeast"]
                  + ["north","east","west","north","east","west","north","north",
                     "east","west","south",
                     # yao1 → northwest → guting3 → 西湖路 area
                     "northwest","west","west","east","east","north","south",
                     "northwest","west","east","south","south","south","south",
                     "southwest"]  # back to tieta
                  )
    elif "高老庄" in loc:
        print("  ROUTE: south x13 west x4")
        for _ in range(13): move(s,"south")
        for _ in range(4): move(s,"west")
        search = ["east"]*5+["north","east","west","west","east",
                  "north","east","west","west","east","north","east","west","west",
                  "north","east","south","south","south","south","south",
                  "west","south","west","south","south","south","east","west","south"]
    elif "开封" in loc:
        print("  ROUTE: east x13 → search all kaifeng")
        for _ in range(13): move(s,"east")
        desc_tieta,_=look(s)
        if "汴京铁塔" in desc_tieta:
            # Comprehensive Kaifeng search:
            # yao streets (northeast), shun streets (northwest), then 西湖路 (far northwest via yao1→guting)
            move(s,"northeast")  # tieta → yao5
        search = [
            # Yao streets: yao5 → yao1
            "north","east","west","north","east","west","north","north","east","west","north",
            # At yao1: northwest → guting3 → more northwest = 西湖路 area
            "northwest","west","west","east","east","north","south",
            "northwest","west","east","south",
            # Back down: south x4 → yao5 → southwest → tieta → northwest → shun streets
            "south","south","south","south","southwest",
            "northwest",  # tieta → shun5
            "north","west","east","north","west","east","north","north","west","east","south",
            # Shun2 → west → yuxiang (御相府)
            "south","west","east","south","southeast",
        ]
    elif "望南" in loc:
        print("  ROUTE: east x3 south")
        for _ in range(3): move(s,"east")
        move(s,"south")
        search = ["southwest","south","west","southwest","northeast","east",
                  "north","northeast","east","west"]
    elif "普陀" in loc:
        print("  ROUTE: south x16 swim north x4")
        for _ in range(16): move(s,"south")
        move(s,"swim")
        move(s,"north"); move(s,"north"); move(s,"northup"); move(s,"northup")
        search = ["north"]*5+["east","west"]+["south"]*5+["west","east","south"]*2
    else:
        print(f"  CITY SEARCH: '{loc}'")
        search = ["south","east","west","west","east",
                  "south","east","west","south","east","west","south",
                  "west","northwest","east","west","west","south","north",
                  "north","south","east","southeast","south","north",
                  "east","north","north","north","north",
                  "east","north","south","west","west","west",
                  "west","south","north","east","east","north","east","west","south"]

    # Also check during travel
    desc_t,_=look(s)
    if find_monster(desc_t,monster_name):
        print("  >> Found immediately!")
        killed = fight(s)

    if not killed:
        killed = search_and_kill(s, monster_name, search)

    if killed:
        print("\n  ============================================")
        print("  ***  FIRST KILL!!! YUAN MISSION DONE!  ***")
        print("  ============================================")
        # Report to yuan
        time.sleep(3); drain(s,quiet=1.0,maxt=3.0)

elif monster_loc == "wait_expired":
    # Placeholder — won't be triggered anymore
    for retry in range(10):
        print(f"  Sleeping 3 min (retry {retry+1}/10)...")
        for _ in range(18): # 18 x 10s = 3 min
            time.sleep(10)
            drain(s, quiet=0.5, maxt=1.0)  # keep alive
        # Re-ask yuan
        drain(s, quiet=0.5, maxt=1.0)
        move(s,"north"); move(s,"west")  # to tianjiantai
        ok_y, desc_y = check_room(s,"天监台")
        if not ok_y:
            move(s,"east"); move(s,"south")
            for _ in range(3): move(s,"north")
            move(s,"north"); move(s,"west")
        b_y = send(s,b"ask yuan about kill\r\n",quiet=3.0)
        yuan2 = clean(b_y); show(f"YUAN retry {retry+1}", b_y)
        m2=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan2)
        if m2:
            monster_name=m2.group(1); monster_loc=m2.group(3)
            print(f"  >> NEW: {monster_name} @ {monster_loc}")
            move(s,"east"); move(s,"south")  # back to hub
            break
        elif "除尽" in yuan2:
            b_y2=send(s,b"ask yuan about kill\r\n",quiet=3.0)
            yuan2=clean(b_y2)
            m2=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan2)
            if m2:
                monster_name=m2.group(1); monster_loc=m2.group(3)
                print(f"  >> NEW: {monster_name} @ {monster_loc}")
                move(s,"east"); move(s,"south")
                break
        else:
            move(s,"east"); move(s,"south")  # back to hub
            print(f"  Still old mission, waiting more...")
    # If we found a new mission in the retry, hunt it now
    if monster_name and monster_loc and monster_loc != "old":
        print(f"\n[5-retry] HUNT {monster_name} @ {monster_loc}")
        loc2 = monster_loc or ""
        if "长安城西" in loc2 or "westway" in loc2.lower():
            print("  ROUTE: west x5 (into westway)")
            for _ in range(5): move(s,"west")
            search2 = ["west"]*5+["east"]*3+["south","north"]*3+["west"]*3+["east"]*3+["south"]*2+["north"]*2
        elif "高老庄" in loc2:
            print("  ROUTE: south x13 west x4")
            for _ in range(13): move(s,"south")
            for _ in range(4): move(s,"west")
            search2 = ["east"]*5+["north","east","west","west","east"]*3+["south"]*5
        elif "开封" in loc2:
            print("  ROUTE: east x13")
            for _ in range(13): move(s,"east")
            move(s,"northeast")
            search2 = ["north","east","west"]*4+["south"]*4+["southwest"]
        elif "长安" in loc2:
            print("  CITY SEARCH")
            search2 = ["south","east","west","west","east","south","east","west",
                      "south","east","west","south","west","northwest","east","west",
                      "west","south","north","north","south","east","southeast",
                      "south","north","east","north","north","north","north",
                      "east","north","south","west","west","west","south","north",
                      "west","south","north","east","east","north","east","west","south"]
        else:
            search2 = ["south","east","west"]*10+["north"]*5
        killed = search_and_kill(s, monster_name, search2)
        if killed:
            print("\n  *** FIRST KILL!!! ***")

print("\n=== FINAL ===")
b6=send(s,b"hp\r\n",quiet=2.0); show("HP",b6)
b7=send(s,b"score\r\n",quiet=3.0); show("SCORE",b7)
print(f"\n  killed={killed}")
print("*** NO QUIT ***")
time.sleep(1); s.close()
