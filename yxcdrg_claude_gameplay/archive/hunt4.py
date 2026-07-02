"""
Hunt v4: Focused on getting a KILL.
- Decode yuan's location to check REACHABILITY up front
- Only hunt reachable areas; wait out unreachable ones
- Multiple search passes per area (monster wanders via random_move)
- Persistent mission file survives between runs
"""
import socket, time, re, sys
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8")

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
def show(label,b): t=clean(b); print(f"\n--- {label} ---"); print(t[-1800:] if len(t)>1800 else t)
def m(s,d,q=1.0): return clean(send(s,d.encode()+b"\r\n",quiet=q))
def look(s):
    drain(s,quiet=0.5,maxt=2.0)
    b=send(s,b"look\r\n",quiet=2.0); return clean(b),b

def firstline(desc):
    for line in desc.split("\n")[:5]:
        line=line.strip()
        if line and not line.startswith(">"): return line
    return ""

def get_exits(desc):
    """Parse '这里明显的出口是 X、Y 和 Z' → set of directions (english)."""
    cn2en={"东":"east","南":"south","西":"west","北":"north",
           "东北":"northeast","东南":"southeast","西北":"northwest","西南":"southwest",
           "上":"up","下":"down"}
    exits=set()
    mexit=re.search(r'出口是\s*(.+?)。', desc)
    seg=mexit.group(1) if mexit else desc
    # English exits sometimes shown directly
    for en in ["northeast","northwest","southeast","southwest","north","south",
               "east","west","up","down","southdown","northup","enter","out"]:
        if en in desc.lower(): exits.add(en)
    return exits

def beiyin_escape(s, desc):
    """Route any 背阴巷 room toward beiyin5→east→zhuque, using landmarks."""
    if "朱雀大街" in desc or "杂货铺" in desc:  # beiyin5
        m(s,"east"); return
    if "粮店" in desc:  # beiyin4
        m(s,"southeast"); return
    if "帮会" in desc:  # beiyin2
        m(s,"south"); return
    ex=get_exits(desc)
    if "west" in ex and "south" in ex:  # beiyin3
        m(s,"east"); return
    # beiyin1 (north→baihu escape)
    m(s,"north")

def roomid(desc):
    fl=firstline(desc)
    rooms=[("南城客栈","kezhan"),("十字街头","hub"),("天监台","yuan_room"),
           ("兵器铺","shop"),("长安武馆","wuguan"),("青龙大街","qinglong"),
           ("玄武大街","xuanwu"),("白虎大街","baihu"),("朱雀大街","zhuque"),
           ("董记当铺","dangpu"),("南城口","nancheng"),("大官道","daguandao"),
           ("终南","zhongnan"),("南岳","nanyue"),("泾水","jingshui"),
           ("土路","gao"),("高家","gao"),("汴京铁塔","tieta"),("天蓬","tianpeng"),
           ("帅府","shuaifu"),("舜王街","shunwang"),("尧王街","yaowang"),
           ("南海之滨","seashore"),("东海之滨","eastsea"),("海滨","seashore_e"),
           ("小岛","island"),("听经","tingjing"),("山路","shanlu"),("山门","shanmen"),
           ("长安城东门","dongmen"),("东门","dongmen"),("国子监","guozijian"),
           ("辰龙","chenlong"),("开封","kaifeng"),("朝阳门","chaoyangmen"),
           ("皇宫","palace"),("三联书局","bookshop"),("相记钱庄","bank"),
           ("化生寺","huasheng"),("方丈室","fangzhang"),("大雄宝殿","temple"),
           ("背阴巷","beiyin"),("民居","minju"),("小酒馆","jiuguan"),
           ("粮仓","liangcang"),("药铺","yaotang"),("回春药铺","yaotang"),
           ("乐坊","lefang"),("毛货","maohuo"),("鞋帽","xiemao"),
           ("袁氏草堂","caotang"),("西门","ximen"),
           ("二楼雅座","erlouya"),("系统公告室","gonggao"),
           ("三花堂密室","sanhua_mishi"),("三花堂","sanhua"),("杂货铺","zahuopu"),
           ("望南街","wangnan"),("大雁塔","dayanta"),("慈恩寺","cien"),
           ("官道","guandao"),("乐游原","guandao"),("进士场","jinshi"),("曲江","qujiang"),
           ("碑林","beilin"),("货行","huohang"),("小雁塔","xiaoyanta")]
    for kw,name in rooms:
        if kw in fl: return name
    for kw,name in rooms:
        if kw in desc[:200]: return name
    kw2=["杨记","春醇","七里","兰亭","西湖路","东湖路","钱庄","万寿","宁心",
         "静心","清心","三心","禹王","古亭","酒楼","盔甲","兵器场","水陆"]
    if any(k in fl for k in kw2): return "kaifeng_other"
    return "unknown"

REVERSE={"east":"west","west":"east","north":"south","south":"north",
         "northeast":"southwest","southwest":"northeast",
         "northwest":"southeast","southeast":"northwest",
         "up":"down","down":"up"}
def goto_hub(s, max_steps=40):
    last_dir=None
    bug_streak=0
    for step in range(max_steps):
        desc,_=look(s); rid=roomid(desc)
        if "系统" in desc and ("BUG" in desc.upper() or "ＢＵＧ" in desc):
            bug_streak+=1
            print(f"  !! server desync (BUG msg) streak={bug_streak}")
            if bug_streak>=3:
                time.sleep(5); drain(s,quiet=1.0,maxt=3.0)
                bug_streak=0
            else:
                time.sleep(1.5)
            continue
        bug_streak=0
        if rid=="hub": return True
        if rid=="beiyin":  # maze — use dedicated escape
            beiyin_escape(s, desc)
            if step%10==9: print(f"  nav {step}: beiyin-escape")
            continue
        nav={"kezhan":["west","north"],"zhuque":["north"],"qinglong":["west"],
            "xuanwu":["south"],"baihu":["east"],"yuan_room":["east","south"],
            "shop":["north","west"],"wuguan":["south","west"],"dangpu":["east","north"],
            "nancheng":["north","north","north","north"],
            "daguandao":["west" if ("平原" in desc or "由东西" in desc or "长安以东" in desc) else "north"],
            "zhongnan":["north"],"nanyue":["north"],"jingshui":["north"],
            "seashore":["north"],"eastsea":["west","north"],"seashore_e":["west"],
            "island":["swim"],"tingjing":["south"],
            "shanlu":["south","southdown"],"shanmen":["southdown"],
            "gao":["east"],"tieta":["west"],"tianpeng":["west"],"shuaifu":["west"],
            "shunwang":["south","southeast"],"yaowang":["south","southwest"],
            "dongmen":["west"],"chenlong":["west"],"kaifeng":["west"],
            "kaifeng_other":["west"],"guozijian":["west"],"chaoyangmen":["south"],
            "palace":["south"],"bookshop":["south","east"],"bank":["north","east"],
            "huasheng":["north","east"],"fangzhang":["west","north","east"],
            "temple":["north","north","east"],"minju":["north","east"],
            "jiuguan":["south"],"liangcang":["west"],
            "yaotang":["west","north"],"lefang":["east"],"maohuo":["north"],
            "xiemao":["north"],"caotang":["south","east"],"ximen":["east"],
            "sanhua_mishi":["east"],"sanhua":["east"],"zahuopu":["east"],
            "erlouya":["down"],"gonggao":["west"],
            "wangnan":["north"],  # wangnan1→qinglong-e3; others funnel
            "huohang":["west"],"dayanta":["west"],"cien":["west"],
            "guandao":["northwest"],"jinshi":["northwest"],"qujiang":["north"],
            "beilin":["west"],"xiaoyanta":["north"]}
        if rid=="unknown":
            # Unmapped room — print it and try parsed exits, avoiding backtrack
            if step%4==0: print(f"  nav {step}: UNKNOWN [{firstline(desc)[:30]}]")
            ex=get_exits(desc)
            avoid=REVERSE.get(last_dir)
            moved=False
            _dir_pref=["west","north","northwest","south","east","northeast","southwest","southeast","up","down","out"]
            for d in _dir_pref:
                if d in ex and d!=avoid:
                    m(s,d); last_dir=d; moved=True; break
            if not moved:
                # only reverse exit available — take it
                for d in _dir_pref:
                    if d in ex:
                        m(s,d); last_dir=d; moved=True; break
            if not moved: m(s,"look")
            continue
        dirs=nav.get(rid,["north"])
        for d in dirs: m(s,d)
        last_dir=dirs[-1] if dirs else None
        if step%10==9: print(f"  nav {step}: {rid}")
    return False

KNOWN={"Board","paizi","Agenta","Snoopl","Snoopy","Xiao er","Da ye","Qianli",
    "Fan luping","Wuguan dizi","Xiao xiao","Yuan tiangang","Yuan shoucheng",
    "Li bai","Zhang guolao","Jieding","Xiucai","Wei shi","Xiao bing","Laitou",
    "Zodiac","Yang zhong","Monk","Heshang","Faming","Dong push","Kong fang",
    "Tie suanpan","Kuli","Jia er","Horse","Maguan","People","Zhike","Luren",
    "Youke","Sengren","Bing","Dai","Girl","Hai","Chen","Xu","Ye","Yin","Zu",
    "Xgong","Yahuan","Yang","Chaniang","Hu","Xiaotong","Gongwei","Siguan",
    "Wu jiang","Zhubing","Reporting","Lao tou","Xiao liumang","Biao","Xiao pizi",
    "Lao wei","Xiao wang","Gui tong","Dahan","Haoke","Tiejiang","Huangbiao",
    "Feng","Jin","Huian","Nuocha","Zhangmen","Shizhe","Sanhua","Xiao liu","Boy",
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

def fight(s,name):
    print(f"  >> ENGAGING {name}!")
    engaged=False
    # Step 1: follow the monster so we track it even if it moves (once is enough)
    time.sleep(0.3)
    for tid in ["guai","jing"]:
        rf=m(s,f"follow {tid}",q=1.0); time.sleep(0.3)
        if any(w in rf for w in ["跟随","跟着","follow","跟"]):
            print(f"  >> following {tid}"); break
    # Try to engage; if monster slipped to an adjacent room, chase it (it wanders).
    for chase in range(3):
        for tid in ["guai","jing"]:
            r=m(s,f"kill {tid}",q=1.5); time.sleep(0.3)
            if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
                print(f"  >> ENGAGED: kill {tid}"); engaged=True; break
        if engaged: break
        # not here — check if it's in an adjacent room (limit to 3 exits to avoid command flood)
        desc,_=look(s)
        ex=list(get_exits(desc))[:3]
        found_adj=False
        for d in ex:
            m(s,d); time.sleep(0.3)
            d2,_=look(s)
            if has_monster(d2,name):
                print(f"  >> chased {name} to {d}"); found_adj=True; break
            m(s,REVERSE.get(d,"look")); time.sleep(0.3)  # come back
        if not found_adj:
            print("  !! Lost the monster"); return False
    if not engaged:
        print("  !! Can't engage"); return False
    for j in range(70):
        time.sleep(3)
        b=drain(s,quiet=2.0,maxt=5.0)
        if b:
            r=clean(b)
            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                show("**** VICTORY! ****",b); return True
            elif "承让" in r: print("  LOST"); return False
            elif "找机会逃跑" in r:
                print("  FLED — re-engaging"); time.sleep(2); drain(s,quiet=1.0,maxt=2.0)
                d2,_=look(s)
                if has_monster(d2,name):
                    for t2 in ["jing","guai"]:
                        r2=m(s,f"kill {t2}",q=2.0)
                        if any(w in r2 for w in ["喝道","想杀","领教","奉陪"]): break
            elif "清醒" in r: print("  KO'd"); return False
            elif j%5==0:
                lines=[l for l in r.split("\n") if l.strip() and ">"not in l]
                if lines: print(f"  [{j}] {lines[-1].strip()[:65]}")
    return False

def search(s,name,moves):
    for i,d in enumerate(moves):
        m(s,d); time.sleep(0.2)
        desc,_=look(s)
        if has_monster(desc,name):
            print(f"\n  ** FOUND {name} step {i}! **")
            return fight(s,name)  # fight() handles follow
        if i%15==14: print(f"  search {i+1}/{len(moves)}")
    return False

import random as _rnd
def wander_search(s,name,steps):
    """Exit-aware random walk — follows REAL exits. Best for random mazes (紫竹林)."""
    last=None
    for i in range(steps):
        desc,_=look(s)
        if has_monster(desc,name):
            print(f"\n  ** FOUND {name} (wander step {i})! **")
            return fight(s,name)  # fight() handles follow
        if "系统" in desc and ("BUG" in desc.upper() or "ＢＵＧ" in desc):
            print(f"  !! server desync mid-wander, pausing 5s"); time.sleep(5)
            drain(s,quiet=1.0,maxt=3.0); continue
        ex=list(get_exits(desc))
        if not ex:
            m(s,"look"); continue
        # prefer not backtracking; pick random valid exit
        avoid=REVERSE.get(last)
        choices=[d for d in ex if d!=avoid] or ex
        d=_rnd.choice(choices)
        m(s,d); time.sleep(0.2); last=d
        if i%15==14: print(f"  wander {i+1}/{steps}")
    return False

# Decode yuan's location → (area, travel_moves, search_moves)
# ONLY hunt if location names a REACHABLE OUTER area. Everything else = wait.
def decode(loc):
    if not loc: return ("UNREACHABLE-unknown",None,None)
    # REACHABLE areas — must contain explicit outer-area name
    if "长安城西" in loc:  # check before 长安城
        return ("westway", ["west"]*5,
                # west1→west2→west3→jincheng(金城郡南)→back, plus dadao branch
                ["west","west","northwest",            # → 金城郡南
                 "southeast","east","east","east",     # back to west1
                 "west","west","west","northwest",     # another pass
                 "southeast","east","east",            # back
                 "south","north","west","east"]*2)
    if "高老庄" in loc:
        return ("gao", ["south"]*13+["west"]*4,
                ["east"]*5+["north","east","west","west","east"]*3+["south"]*5+
                ["west","south"]*3+["east","west","south"])
    if "普陀" in loc:
        # arrive at 山门(gate). Navigate to zhulin then wander the bamboo maze.
        # gate→N→xiaoyuan→N→guangchang→E→road1→...→zhulin (mostly random exits)
        if "紫竹" in loc or "竹林" in loc:
            srch=(["north","north","east","north","north"]+  # gate→zhulin area
                  ["north","east","south","west","northeast","northwest",
                   "southeast","southwest"]*5+  # wander bamboo ~40 rooms
                  ["north","east","west"]*3)
        else:
            srch=(["north","north"]+  # gate→guangchang
                  ["west","east","south","enter","out"]*2+  # courtyard/cave/halls
                  ["east","north","west","south"]*4)
        return ("putuo", ["south"]*16+["swim","north","north","northup","northup"], srch)
    if "开封" in loc:
        return ("kaifeng", ["east"]*13+["northeast"],
                ["north","east","west"]*3+["north"]+
                ["northwest","west","west","east","east","north","south",
                 "northwest","west","east","south","south","south","south","south","southwest",
                 "northwest"]+["north","west","east"]*4+
                ["south","south","south","south","south","southeast"])
    if "望南" in loc:
        return ("eastway", ["east"]*3+["south"],
                ["southwest","south","west","southwest","northeast","east","north","northeast","east","west"])
    if "长安城" in loc or "粮仓" in loc:  # generic city
        return ("city", [],
            ["south","east","west","west","east","south","east","west",
             "south","east","west","south","west","northwest","east","west",
             "west","south","north","north","south","east","southeast","south",
             "north","east","north","north","north","north",
             "east","north","south","west","west","west","south","north",
             "west","south","north","east","east","north","east","west","south"])
    # Bare sub-location with no reachable outer area = UNREACHABLE
    # (玉女峰/绣房/海底/湖底/稻香村/方寸 etc. — moon/sea/dream/lingtai)
    return ("UNREACHABLE-"+loc[:6], None, None)

import os
MFILE=os.path.join(os.environ.get("TEMP","C:/Users/ying/AppData/Local/Temp"),"yxcdrg_mission.txt")
def save_m(n,l):
    try: open(MFILE,"w",encoding="utf-8").write(f"{n}|{l or ''}")
    except: pass
def load_m():
    try:
        p=open(MFILE,encoding="utf-8").read().strip().split("|",1)
        return p[0],(p[1] if len(p)>1 else None)
    except: return None,None

# ============================================
print("=== HUNT v4 — focused kill ===")
s=socket.create_connection(("146.190.143.182",6666),timeout=15)
drain(s,quiet=3.0,maxt=12.0)
m(s,"gb"); m(s,"no"); m(s,"yxcdrg")
r=clean(send(s,b"198633\r\n",quiet=4.0))
if "y/n" in r: m(s,"y",q=4.0)
m(s,"set wimpy 5")

# SETUP — check current state, only act on what's needed
print("\n[SETUP] checking state...")
goto_hub(s)
hp_r=clean(send(s,b"hp\r\n",quiet=2.0))
sc_r=clean(send(s,b"score\r\n",quiet=2.5))

# Parse gear
dmg_m=re.search(r'兵器伤害力：\[\s*(\d+)\s*\]',sc_r)
arm_m=re.search(r'盔甲保护力：\[\s*(\d+)\s*\]',sc_r)
have_dmg=int(dmg_m.group(1)) if dmg_m else 0
have_arm=int(arm_m.group(1)) if arm_m else 0

# Parse food/water from hp output
food_m=re.search(r'食物：\s*(\d+)\s*/\s*(\d+)',hp_r)
water_m=re.search(r'饮水：\s*(\d+)\s*/\s*(\d+)',hp_r)
food_cur=int(food_m.group(1)) if food_m else 0
food_max=int(food_m.group(2)) if food_m else 360
water_cur=int(water_m.group(1)) if water_m else 0
water_max=int(water_m.group(2)) if water_m else 360
print(f"  gear: dmg={have_dmg} armor={have_arm} | food={food_cur}/{food_max} water={water_cur}/{water_max}")

# Buy gear only if missing
if have_dmg==0 or have_arm==0:
    m(s,"east"); m(s,"south")
    d,_=look(s)
    if "兵器铺" in d:
        if have_dmg==0: m(s,"buy blade from xiao xiao"); m(s,"wield blade")
        if have_arm==0: m(s,"buy shield from xiao xiao"); m(s,"wear shield")
        print("  Gear bought")
    m(s,"north"); m(s,"west")

# Buy food/water only if below 50%
if food_cur < food_max*0.5 or water_cur < water_max*0.5:
    m(s,"south"); m(s,"east")  # kezhan
    d,_=look(s)
    if "南城客栈" in d:
        if food_cur < food_max*0.5:
            for _ in range(5): m(s,"buy gourou from xiao er",q=0.5)
            for _ in range(8): m(s,"eat gourou",q=0.3)
        if water_cur < water_max*0.5:
            for _ in range(3): m(s,"buy jiudai from xiao er",q=0.5)
            for _ in range(3): m(s,"fill jiudai",q=0.5)
            for _ in range(5): m(s,"drink jiudai",q=0.3)
        print("  Fed/watered")
    m(s,"west"); m(s,"north")
else:
    print("  Food/water OK, skipping kezhan")

show("READY", send(s,b"score\r\n",quiet=3.0))

# MISSION LOOP
killed=False
for attempt in range(12):
    print(f"\n[ATTEMPT {attempt+1}/12]")
    goto_hub(s)
    m(s,"north"); m(s,"west")  # yuan
    d,_=look(s)
    if "天监台" not in d:
        goto_hub(s); m(s,"north"); m(s,"west")
    b=send(s,b"ask yuan about kill\r\n",quiet=3.0)
    yuan=clean(b); show(f"YUAN {attempt+1}",b)

    name=None; loc=None
    mm=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan)
    if mm: name=mm.group(1); loc=mm.group(3); save_m(name,loc)
    elif "除尽" in yuan:
        b=send(s,b"ask yuan about kill\r\n",quiet=3.0); yuan=clean(b)
        mm=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan)
        if mm: name=mm.group(1); loc=mm.group(3); save_m(name,loc)
    elif "收服" in yuan:
        mm=re.search(r'收服(.+?)吗',yuan)
        if mm:
            name=mm.group(1)
            _,loc=load_m()  # recover saved location

    if not name:
        print("  No mission, wait 60s"); time.sleep(60); continue

    area, travel, srch = decode(loc)
    print(f"  Mission: {name} @ {loc} → {area}")

    if area.startswith("UNREACHABLE"):
        # Wait out the full 30-min timer. Re-ask every 5 min until mission CHANGES.
        print(f"  >> {area} — waiting for expiry (re-ask every 5min)")
        prev_name=name
        for wcycle in range(8):  # up to 40 min
            for _ in range(30): time.sleep(10); drain(s,quiet=0.4,maxt=0.8)  # 5 min
            goto_hub(s); m(s,"north"); m(s,"west")
            d,_=look(s)
            if "天监台" not in d:
                goto_hub(s); m(s,"north"); m(s,"west")
            b=send(s,b"ask yuan about kill\r\n",quiet=3.0); yy=clean(b)
            nm=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yy)
            if nm:
                name=nm.group(1); loc=nm.group(3); save_m(name,loc)
                print(f"  >> mission changed: {name} @ {loc}")
                break
            mr=re.search(r'收服(.+?)吗',yy)
            cur=mr.group(1) if mr else None
            if cur and cur!=prev_name:
                name=cur; _,loc=load_m()
                print(f"  >> reminder name changed: {name}")
                break
            print(f"  ...still {prev_name}, waited {(wcycle+1)*5}min")
        # re-decode the (possibly new) mission and fall through to hunt
        m(s,"east"); m(s,"south")
        area, travel, srch = decode(loc)
        if area.startswith("UNREACHABLE"):
            print(f"  Still unreachable after waiting, moving on")
            continue
        print(f"  Now hunting: {name} @ {loc} → {area}")

    m(s,"east"); m(s,"south")  # back to hub
    goto_hub(s)

    # Travel + check during travel
    for d2 in travel:
        m(s,d2)
        dt,_=look(s)
        if has_monster(dt,name):
            print("  >> Found during travel!")
            killed=fight(s,name)
            if killed: break

    # Search via exit-aware wander (covers far more than hand-built routes).
    # First a hand-route pass (targeted), then a long wander to catch wanderers.
    if not killed and srch:
        print(f"  Route pass ({len(srch)} rooms)")
        killed=search(s,name,srch)
    if not killed:
        steps=200 if area=="putuo" else (130 if area in ("kaifeng","gao") else 80)
        print(f"  Wander-search — up to {steps} steps")
        killed=wander_search(s,name,steps)

    if killed:
        print("\n  ************************************")
        print("  ***   FIRST KILL ACHIEVED!!!    ***")
        print("  ************************************")
        time.sleep(3); drain(s,quiet=1.0,maxt=3.0)
        goto_hub(s); m(s,"north"); m(s,"west")
        b=send(s,b"ask yuan about kill\r\n",quiet=3.0); show("YUAN REPORT",b)
        break

print("\n=== FINAL ===")
b=send(s,b"hp\r\n",quiet=2.0); show("HP",b)
b=send(s,b"score\r\n",quiet=3.0); show("SCORE",b)
print(f"\n  killed={killed}")
print("*** NO QUIT ***")
time.sleep(1); s.close()
