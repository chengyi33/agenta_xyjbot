"""
Hunt v3: Persistent single session. Get mission, travel, search, kill.
If old mission (no location) → wait for expiry → get new mission with location → kill.
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
def show(label,b): t=clean(b); print(f"\n--- {label} ---"); print(t[-2000:] if len(t)>2000 else t)
def m(s,d,q=1.0): return clean(send(s,d.encode()+b"\r\n",quiet=q))
def look(s):
    drain(s,quiet=0.5,maxt=2.0)  # clear buffer more aggressively
    b=send(s,b"look\r\n",quiet=2.0)
    return clean(b),b

# Room keywords for navigation — check FIRST 3 LINES ONLY to avoid buffer contamination
def roomid(desc):
    # Only use the room title line (first non-empty line)
    firstline = ""
    for line in desc.split("\n")[:5]:
        line = line.strip()
        if line and not line.startswith(">"):
            firstline = line
            break
    rooms=[("南城客栈","kezhan"),("十字街头","hub"),("天监台","yuan_room"),
           ("兵器铺","shop"),("长安武馆","wuguan"),
           ("青龙大街","qinglong"),("玄武大街","xuanwu"),("白虎大街","baihu"),
           ("朱雀大街","zhuque"),("董记当铺","dangpu"),("南城口","nancheng"),
           ("大官道","daguandao"),("终南","zhongnan"),("南岳","nanyue"),
           ("泾水","jingshui"),("土路","gao"),("高家","gao"),
           ("汴京铁塔","tieta"),("天蓬","tianpeng"),("帅府","shuaifu"),
           ("舜王街","shunwang"),("尧王街","yaowang"),
           ("南海之滨","seashore"),("小岛","island"),("山路","shanlu"),("山门","shanmen"),
           ("长安城东门","dongmen"),("国子监","guozijian"),("东门","dongmen"),
           ("辰龙","chenlong"),("开封","kaifeng"),("朝阳门","chaoyangmen"),
           ("皇宫","palace"),("三联书局","bookshop"),("相记钱庄","bank"),
           ("化生寺","huasheng"),("方丈室","fangzhang"),("大雄宝殿","temple"),
           ("背阴巷","beiyin"),("民居","minju"),("小酒馆","jiuguan"),
           ("粮仓","liangcang"),("药铺","yaotang"),("回春药铺","yaotang"),
           ("乐坊","lefang"),("毛货","maohuo"),("鞋帽","xiemao")]
    # Check firstline first (most reliable), then full desc
    for kw,name in rooms:
        if kw in firstline: return name
    for kw,name in rooms:
        if kw in desc[:200]: return name
    # Kaifeng catch-all
    kw2=["杨记","春醇","七里","兰亭","西湖路","东湖路","钱庄","万寿","宁心",
         "静心","清心","三心","禹王","古亭","酒楼","盔甲","兵器场","水陆"]
    if any(k in firstline for k in kw2): return "kaifeng_other"
    return "unknown"

def goto_hub(s, max_steps=40):
    for step in range(max_steps):
        desc,_=look(s)
        rid=roomid(desc)
        if rid=="hub": print(f"  HUB ({step}steps)"); return True
        nav={
            "kezhan":["west","north"],"zhuque":["north"],"qinglong":["west"],
            "xuanwu":["south"],"baihu":["east"],"yuan_room":["east","south"],
            "shop":["north","west"],"wuguan":["south","west"],"dangpu":["east","north"],
            "nancheng":["north","north","north","north"],
            "daguandao":["west" if ("平原" in desc or "由东西" in desc or "长安以东" in desc) else "north"],
            "zhongnan":["north"],"nanyue":["north"],"jingshui":["north"],
            "chaoyangmen":["south"],"palace":["south"],
            "bookshop":["south","east"],"bank":["north","east"],
            "huasheng":["north","east"],"fangzhang":["west","north","east"],
            "temple":["north","north","east"],
            "beiyin":["north"],"minju":["north"],"jiuguan":["south","east","north"],
            "liangcang":["west","north"],"yaotang":["west","north"],
            "lefang":["east"],"maohuo":["north"],"xiemao":["north"],
            "seashore":["north"],"island":["swim"],"shanlu":["south"],"shanmen":["southdown"],
            "gao":["east"],"tieta":["west"],"tianpeng":["west"],"shuaifu":["west"],
            "shunwang":["south","southeast"],"yaowang":["south","southwest"],
            "dongmen":["west"],"chenlong":["west"],"kaifeng":["west"],
            "kaifeng_other":["west"],"guozijian":["west"],
        }
        dirs=nav.get(rid,["north"])
        for d in dirs: m(s,d)
        if step%8==7: print(f"  nav step {step}: {rid}")
    return False

KNOWN={"Board","paizi","Agenta","Snoopl","Snoopy","Xiao er","Da ye","Qianli",
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

def has_monster(desc,name):
    for line in desc.split("\n"):
        line=line.strip()
        if "(" not in line or ")" not in line: continue
        if any(k in line for k in KNOWN): continue
        if name and name in line: return True
    return False

def engage_and_fight(s, name):
    print(f"  >> ENGAGING {name}!")
    for tid in ["jing","guai"]:
        r=m(s,f"kill {tid}",q=2.0)
        if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
            print(f"  >> ENGAGED: kill {tid}"); break
    else:
        print(f"  !! Can't engage"); return False
    for j in range(60):
        time.sleep(3)
        b=drain(s,quiet=2.0,maxt=5.0)
        if b:
            r=clean(b)
            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                show("**** VICTORY! ****",b); return True
            elif "承让" in r: print("  LOST"); return False
            elif "找机会逃跑" in r:
                print("  FLED — re-engaging")
                time.sleep(2); drain(s,quiet=1.0,maxt=2.0)
                desc2,_=look(s)
                if has_monster(desc2,name):
                    for tid2 in ["jing","guai"]:
                        r2=m(s,f"kill {tid2}",q=2.0)
                        if any(w in r2 for w in ["喝道","想杀","领教","奉陪"]): break
            elif "清醒" in r: print("  KO'd"); return False
            elif j%5==0:
                lines=[l for l in r.split("\n") if l.strip() and ">"not in l]
                if lines: print(f"  [{j}] {lines[-1].strip()[:70]}")
    return False

def search_area(s, name, moves):
    """Search rooms by following move list. Return True if kill."""
    for i,d in enumerate(moves):
        m(s,d)
        desc,_=look(s)
        if has_monster(desc,name):
            print(f"\n  ** FOUND {name} at step {i}! **")
            show("MONSTER",send(s,b"look\r\n",quiet=1.5))
            return engage_and_fight(s,name)
        if i%15==14: print(f"  search {i+1}/{len(moves)}")
    return False

MISSION_FILE = "/tmp/yxcdrg_mission.txt"

def save_mission(name, loc):
    try:
        with open(MISSION_FILE, "w") as f:
            f.write(f"{name}|{loc or ''}")
    except: pass

def load_mission():
    try:
        with open(MISSION_FILE) as f:
            parts = f.read().strip().split("|", 1)
            return parts[0], parts[1] if len(parts)>1 else None
    except: return None, None

def parse_yuan(text):
    """Parse yuan's response. Returns (name, id_hint, location) or (name, None, None) for reminder."""
    m1=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',text)
    if m1: return m1.group(1), m1.group(2).strip(), m1.group(3)
    m2=re.search(r'收服(.+?)吗',text)
    if m2: return m2.group(1), None, None
    if "除尽" in text: return None, None, "done"
    return None, None, None

def get_route_and_search(loc):
    """Return (travel_moves, search_moves) based on location."""
    # City areas
    if "长安城" in loc and "西" not in loc and "东" not in loc:
        return [], ["south","east","west","west","east","south","east","west",
                   "south","east","west","south","west","northwest","east","west",
                   "west","south","north","north","south","east","southeast","south",
                   "north","east","north","north","north","north",
                   "east","north","south","west","west","west","south","north",
                   "west","south","north","east","east","north","east","west","south"]
    if "长安城西" in loc or "westway" in loc.lower():
        return ["west"]*5, ["west"]*4+["east"]*4+["south","north"]*3+["west","east","south"]*2
    if "望南" in loc:
        return ["east"]*3+["south"], ["southwest","south","west","southwest","northeast","east","north","northeast","east","west"]
    if "高老庄" in loc:
        return ["south"]*13+["west"]*4, (
            ["east"]*5+["north","east","west","west","east"]*3+
            ["south"]*5+["west","south"]*3+["east","west","south"])
    if "普陀" in loc:
        return ["south"]*16+["swim","north","north","northup","northup"], (
            ["north"]*5+["east","west"]+["south"]*5)
    if "开封" in loc:
        # Kaifeng comprehensive search
        travel = ["east"]*13+["northeast"]  # tieta → yao5
        search = (["north","east","west"]*3+["north"]+  # yao1-5 + side rooms
                  ["northwest","west","west","east","east","north","south",  # guting → 西湖路
                   "northwest","west","east","south","south","south","south","south",  # 西湖路 area
                   "southwest",  # back to tieta
                   "northwest"]+  # tieta → shun5
                  ["north","west","east"]*4+  # shun streets
                  ["south","south","south","south","south","southeast"])  # back to tieta
        return travel, search
    # Default city search
    return [], ["south","east","west","west","east","south","east","west",
               "south","east","west","south","west","northwest","east","west",
               "west","south","north","north","south","east","southeast",
               "north","east","north","north","north","north",
               "east","north","south","west","west","west","south","north"]

# ============================================
print("=== HUNT v3 — PERSISTENT SESSION ===")
s=socket.create_connection(("146.190.143.182",6666),timeout=15)
drain(s,quiet=3.0,maxt=12.0)
m(s,"gb"); m(s,"no"); m(s,"yxcdrg")
r=clean(send(s,b"198633\r\n",quiet=4.0))
if "y/n" in r: m(s,"y",q=4.0)
m(s,"set wimpy 5")

# ============================================
# SETUP: Get to hub, gear up, feed
# ============================================
print("\n[SETUP]")
goto_hub(s)

# Gear
m(s,"east"); m(s,"south")  # shop
desc,_=look(s)
if "兵器铺" in desc:
    m(s,"buy blade from xiao xiao"); m(s,"wield blade")
    m(s,"buy shield from xiao xiao"); m(s,"wear shield")
    print("  Gear!")
m(s,"north"); m(s,"west")  # back to hub

# Food
m(s,"south"); m(s,"east")  # kezhan
desc,_=look(s)
if "南城客栈" in desc:
    for _ in range(5): m(s,"buy gourou from xiao er",q=0.5)
    for _ in range(3): m(s,"buy jiudai from xiao er",q=0.5)
    for _ in range(8): m(s,"eat gourou",q=0.3)
    for _ in range(5): m(s,"drink jiudai",q=0.3)
    print("  Fed!")
m(s,"west"); m(s,"north")  # back to hub

b=send(s,b"score\r\n",quiet=3.0); show("SETUP DONE",b)

# ============================================
# MISSION LOOP: Ask yuan, travel, search, kill
# Retry up to 15 times (waiting 3 min between)
# ============================================
killed=False
# Load saved mission from previous run
current_name, current_loc = load_mission()
if current_name: print(f"  Loaded saved mission: {current_name} @ {current_loc}")

for attempt in range(15):
    print(f"\n[MISSION ATTEMPT {attempt+1}/15]")

    # Go to yuan
    goto_hub(s)
    m(s,"north"); m(s,"west")  # hub→xuanwu→tianjiantai
    desc,_=look(s)
    if "天监台" not in desc:
        print(f"  !! Not at yuan: {desc[:40]}")
        goto_hub(s); m(s,"north"); m(s,"west")

    b=send(s,b"ask yuan about kill\r\n",quiet=3.0)
    yuan=clean(b); show(f"YUAN {attempt+1}",b)

    name,_, loc = parse_yuan(yuan)

    if loc == "done":
        # Mission complete! Ask for new one
        b=send(s,b"ask yuan about kill\r\n",quiet=3.0)
        yuan=clean(b)
        name,_,loc=parse_yuan(yuan)

    if name and loc and loc not in (None, "done"):
        print(f"\n  ** MISSION: {name} @ {loc} **")
        current_name=name; current_loc=loc
        save_mission(name, loc)  # persist for next run

        # Go back to hub and travel to area
        m(s,"east"); m(s,"south")
        goto_hub(s)

        travel,search=get_route_and_search(loc)

        # Travel
        print(f"  Travel: {len(travel)} moves")
        for d in travel:
            m(s,d)
            desc2,_=look(s)
            if has_monster(desc2,name):
                print(f"  >> Found during travel!")
                killed=engage_and_fight(s,name)
                if killed: break

        # Search
        if not killed:
            print(f"  Search: {len(search)} moves")
            killed=search_area(s,name,search)

        if killed:
            print("\n  ************************************")
            print("  ***   FIRST KILL ACHIEVED!!!    ***")
            print("  ***   YUAN MISSION COMPLETE!    ***")
            print("  ************************************")
            time.sleep(3); drain(s,quiet=1.0,maxt=3.0)
            # Report to yuan
            goto_hub(s); m(s,"north"); m(s,"west")
            b=send(s,b"ask yuan about kill\r\n",quiet=3.0)
            show("YUAN FINAL REPORT",b)
            break

    elif name and loc is None:
        # Old mission reminder — monster is still alive! Search again with stored location.
        if current_loc:
            print(f"  Old mission ({name}) — searching again @ {current_loc}!")
            m(s,"east"); m(s,"south")
            goto_hub(s)
            travel2, search2 = get_route_and_search(current_loc)
            for d in travel2: m(s,d)
            if not killed:
                killed = search_area(s, name, search2)
            if killed: break
            # After search, wait a bit before asking again
            goto_hub(s)
        else:
            print(f"  Old mission ({name}) no stored loc — waiting 2 min...")
            for _ in range(12): time.sleep(10); drain(s,quiet=0.5,maxt=1.0)
    else:
        print(f"  No mission parsed. Waiting 60s...")
        time.sleep(60)

# ============================================
print("\n=== FINAL ===")
b=send(s,b"hp\r\n",quiet=2.0); show("HP",b)
b=send(s,b"score\r\n",quiet=3.0); show("SCORE",b)
print(f"\n  killed={killed}")
print("*** NO QUIT ***")
time.sleep(1); s.close()
