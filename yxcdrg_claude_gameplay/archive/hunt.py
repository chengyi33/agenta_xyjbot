"""
Focused hunt script per user instructions:
1. Get to kezhan
2. buy gourou + jiudai, eat/drink to full
3. Wield blade + wear shield
4. Ask yuan for mission
5. Go hunt and kill
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
def show(label,b): t=clean(b); print(f"\n--- {label} ---"); print(t[-2500:] if len(t)>2500 else t)
def c(s,d,q=1.5): return clean(send(s,d.encode()+b"\r\n",quiet=q))

def look(s):
    b=send(s,b"look\r\n",quiet=1.5)
    t=clean(b)
    # Only use first 3 lines for room ID to avoid buffer contamination
    first_lines = "\n".join(t.split("\n")[:4])
    rooms = [("南城客栈","kezhan"),("十字街头","hub"),("天监台","yuan_room"),
             ("兵器铺","shop"),("青龙大街","qinglong"),("玄武大街","xuanwu"),
             ("白虎大街","baihu"),("长安武馆","wuguan"),("朱雀大街","zhuque"),
             ("董记当铺","dangpu"),("南城口","nanchengkou"),
             ("大官道","daguandao"),("终南","zhongnan"),("南岳","nanyue"),
             ("泾水","jingshui"),("土路","gao_road"),("街道","gao_street"),
             ("高家大门","gao_gate"),("正院","gao_yard"),("偏房","pianfang"),
             ("汴京铁塔","tieta"),("天蓬","tianpeng"),("帅府","shuaifu"),
             ("舜王街","shunwang"),("尧王街","yaowang"),
             ("南海之滨","seashore"),("小岛","island"),("山路","shanlu"),("山门","shanmen")]
    for kw,name in rooms:
        if kw in first_lines: return name, t, b
    # Fallback: check full text
    for kw,name in rooms:
        if kw in t: return name, t, b
    return "unknown", t, b

def go_to_hub(s, max_steps=30):
    """Navigate to 十字街头."""
    dirs_from = {
        "kezhan": ["west","north"], "zhuque": ["north"], "qinglong": ["west"],
        "xuanwu": ["south"], "baihu": ["east"], "yuan_room": ["east","south"],
        "shop": ["north","west"], "wuguan": ["south","west"],
        "dangpu": ["east","north"], "nanchengkou": ["north","north","north","north"],
        "daguandao": ["west"], "zhongnan": ["north"], "nanyue": ["north"],
        "jingshui": ["north"], "seashore": ["north"],
        "island": ["swim"], "shanlu": ["south"], "shanmen": ["southdown"],
        "gao_road": ["east"], "gao_street": ["east"], "gao_gate": ["south"],
        "gao_yard": ["south"], "pianfang": ["west"],
        "tieta": ["west"], "tianpeng": ["west"], "shuaifu": ["west"],
        "shunwang": ["south","southeast"], "yaowang": ["south","southwest"],
    }
    for step in range(max_steps):
        room, desc, _ = look(s)
        if room == "hub":
            print(f"  >> HUB! ({step} steps)")
            return True
        dirs = dirs_from.get(room, ["north"])
        # Special: daguandao — context matters
        if room == "daguandao":
            if "平原" in desc or "由东西" in desc or "长安以东" in desc:
                dirs = ["west"]
            else:
                dirs = ["north"]
        for d in dirs:
            r = c(s, d)
            if "什么" not in r and "不能" not in r:
                break
        if step % 5 == 0: print(f"  navigating... {step} steps, room={room}")
    print(f"  !! Failed to reach hub after {max_steps} steps")
    return False

def find_monster(desc, name):
    """Find monster NPC line in look output."""
    known = {"Board","paizi","Agenta","Snoopl","Snoopy","Xiao er","Da ye","Qianli",
        "Fan luping","Wuguan dizi","Xiao xiao","Yuan tiangang","Li bai","Zhang guolao",
        "Jieding","Xiucai","Wei shi","Xiao bing","Laitou","Zodiac","Yang zhong",
        "Monk","Heshang","Faming","Dong push","Kong fang","Tie suanpan","Kuli",
        "Jia er","Horse","Maguan","People","Zhike","Luren","Youke","Sengren","Bing",
        "Dai","Girl","Hai","Chen","Xu","Ye","Yin","Zu","Xgong","Yahuan","Yang",
        "Chaniang","Hu","Xiaotong","Gongwei","Siguan","Wu jiang","Zhubing",
        "Reporting","Lao tou","Xiao liumang","Biao","Xiao pizi","Lao wei",
        "Xiao wang","Gui tong","Dahan","Haoke","Tiejiang","Huangbiao","Feng",
        "Jin","Huian","Nuocha","Zhangmen","Shizhe","Sanhua","Xiao liu","Boy",
        "Rat","Qiong han","Oldman","Oldwoman","Keeper","Eryi","Woman","Youxia",
        "Bookseller","You ke","Xiao maolu","Qianke","Guitong","Jixian","Pablo",
        "Laosun","Shouchen","Xianglan","Wei","Daozhang","Libai","Teawaiter",
        "Taizong","Hezhizhang","Gongsun","Gao tai","Cuiying","Xiao ying","Xiushi"}
    for line in desc.split("\n"):
        line = line.strip()
        if "(" not in line or ")" not in line: continue
        if any(k in line for k in known): continue
        if name and name in line: return True
    return False

def do_fight(s):
    """Try to kill the monster. Returns True if killed."""
    for tid in ["jing","guai"]:
        r = c(s, f"kill {tid}")
        if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
            print(f"  >> ENGAGED with kill {tid}!")
            break
    else:
        print(f"  !! Can't engage"); return False

    for j in range(60):
        time.sleep(3)
        b = drain(s, quiet=2.0, maxt=5.0)
        if b:
            r = clean(b)
            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                show("**** KILL! ****", b); return True
            elif "承让" in r: print("  >> Lost"); return False
            elif "找机会逃跑" in r:
                print("  >> Fled — re-engaging")
                time.sleep(2); drain(s,quiet=1.0,maxt=2.0)
                for tid2 in ["jing","guai"]:
                    r2 = c(s,f"kill {tid2}")
                    if any(w in r2 for w in ["喝道","想杀","领教","奉陪"]): break
            elif "清醒" in r: print("  >> KO'd"); return False
            elif j%5==0:
                lines=[l for l in r.split("\n") if l.strip() and ">"not in l]
                if lines: print(f"  [{j}] {lines[-1].strip()[:70]}")
    return False

def get_travel(loc):
    if not loc: return []
    if "高老庄" in loc: return ["south"]*13+["west"]*4
    if "开封" in loc:
        if "尧" in loc: return ["east"]*13+["northeast"]
        return ["east"]*13+["northwest"]
    if "普陀" in loc: return ["south"]*16+["swim","north","north","northup","northup"]
    if "望南" in loc: return ["east"]*3+["south"]
    return []

def get_search(loc):
    if not loc: return []
    if "高老庄" in loc:
        return ["east"]*5+["north","east","west","west","east",
                "north","east","west","west","east","north","east","west","west",
                "north","east","south","south","south","south","south",
                "west","south","west","south","south","south","east","west","south"]
    if "开封" in loc and "尧" in loc:
        return ["north","east","west","north","east","west","north","north",
                "east","west","south","south","south","south","southwest"]
    if "开封" in loc:
        return ["north"]*4+["west","east"]+["south"]*4
    if "普陀" in loc:
        return ["north"]*5+["east","west"]+["south"]*5
    if "望南" in loc:
        return ["southwest","south","west","southwest","northeast","east","north","northeast","east","west"]
    # City — comprehensive
    return ["south","east","west","west","east","south","east","west",
            "south","east","west","south","west","northwest","east","west","west","south","north",
            "north","south","east","southeast","south","north","east","north","north","north","north",
            "east","north","south","east","north","south","west","west","west","south","north",
            "west","south","north","east","east","north","east","west","south"]

# ========================================
print("=== HUNT SCRIPT ===")
s = socket.create_connection(("146.190.143.182",6666),timeout=15)
drain(s,quiet=3.0,maxt=12.0)
c(s,"gb"); c(s,"no"); c(s,"yxcdrg")
r = c(s,"198633",q=4.0)
if "y/n" in r: c(s,"y",quiet=4.0)
c(s,"set wimpy 5")

# Check where we are
room,desc,b = look(s)
print(f"Starting at: {room}")
show("START",b)

# ========================================
# STEP 1: Get to kezhan and load up
# ========================================
print("\n=== STEP 1: GET TO KEZHAN ===")
go_to_hub(s)
# hub -> south -> east -> kezhan
c(s,"south"); c(s,"east")
room,desc,_ = look(s)
print(f"At: {room}")

if "南城客栈" in desc:
    print("BUYING FOOD...")
    for _ in range(5): c(s,"buy gourou from xiao er",q=0.5)
    for _ in range(3): c(s,"buy jiudai from xiao er",q=0.5)
    for _ in range(8): c(s,"eat gourou",q=0.3)
    for _ in range(5): c(s,"drink jiudai",q=0.3)
    b2=send(s,b"hp\r\n",quiet=2.0); show("HP AFTER FOOD",b2)

# ========================================
# STEP 2: Weapon up
# ========================================
print("\n=== STEP 2: WEAPON UP ===")
inv = c(s,"i")
if "钢刀" not in inv:
    # go to weapon shop: west -> north -> east -> south
    c(s,"west"); c(s,"north"); c(s,"east"); c(s,"south")
    room2,_,_ = look(s)
    if "兵器铺" in room2:
        c(s,"buy blade from xiao xiao"); c(s,"wield blade")
        c(s,"buy shield from xiao xiao"); c(s,"wear shield")
        print("  Gear bought!")
    # back: north -> west -> south -> east (kezhan)
    c(s,"north"); c(s,"west"); c(s,"south"); c(s,"east")
else:
    c(s,"wield blade"); c(s,"wear shield")
    print("  Gear already in inventory!")

b3=send(s,b"score\r\n",quiet=3.0); show("SCORE",b3)

# ========================================
# STEP 3: Ask Yuan
# ========================================
print("\n=== STEP 3: ASK YUAN ===")
# kezhan -> west -> north -> north -> west
c(s,"west"); c(s,"north"); c(s,"north"); c(s,"west")
room3,_,_ = look(s)
print(f"At: {room3}")

if "天监台" not in room3:
    print("!! Not at yuan, trying again")
    go_to_hub(s)
    c(s,"north"); c(s,"west")

b4=send(s,b"ask yuan about kill\r\n",quiet=3.0)
yuan=clean(b4)
show("YUAN",b4)

monster_name=None; monster_loc=None
m=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan)
if m:
    monster_name=m.group(1); monster_loc=m.group(3)
    print(f"  >> MISSION: {monster_name} @ {monster_loc}")
elif "除尽" in yuan:
    b5=send(s,b"ask yuan about kill\r\n",quiet=3.0)
    yuan=clean(b5); show("NEW MISSION",b5)
    m=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan)
    if m: monster_name=m.group(1); monster_loc=m.group(3)
elif "收服" in yuan:
    m2=re.search(r'收服(.+?)吗',yuan)
    if m2: monster_name=m2.group(1); monster_loc="unknown"
    print(f"  >> OLD MISSION: {monster_name}")

# ========================================
# STEP 4: Hunt!
# ========================================
if not monster_name:
    print("!! No mission!");
else:
    print(f"\n=== STEP 4: HUNT {monster_name} @ {monster_loc} ===")
    # Back to hub first
    c(s,"east"); c(s,"south")  # tianjiantai -> xuanwu -> hub
    go_to_hub(s)

    travel = get_travel(monster_loc)
    search = get_search(monster_loc)

    # Travel to area
    if travel:
        print(f"  Traveling ({len(travel)} moves)...")
        for d in travel:
            r = c(s,d)
            # Check for monster every step during travel
            room_t,desc_t,_ = look(s)
            if find_monster(desc_t, monster_name):
                print(f"  >> Found during travel!")
                if do_fight(s):
                    print("\n  *** FIRST KILL! ***"); monster_name=None
                break

    # Search area
    if monster_name:
        print(f"  Searching ({len(search)} rooms)...")
        for i,d in enumerate(search):
            c(s,d)
            room_s,desc_s,_ = look(s)
            if find_monster(desc_s, monster_name):
                print(f"  >> Found at step {i}!")
                if do_fight(s):
                    print("\n  *** FIRST KILL! ***"); monster_name=None
                break
            if i%10==0: print(f"  searching {i}/{len(search)}: {room_s}")

# ========================================
# DONE
# ========================================
print("\n=== FINAL ===")
b6=send(s,b"hp\r\n",quiet=2.0); show("HP",b6)
b7=send(s,b"score\r\n",quiet=3.0); show("SCORE",b7)
print("\n*** NO QUIT ***")
time.sleep(1); s.close()
