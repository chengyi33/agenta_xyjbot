"""
Multi-kill bot: get 4 kills without reporting back to yuan between kills.
1. Setup: buy fork + armor if missing, refill food/water if below 50%
2. Loop 4 times: ask yuan → hunt → kill → repeat immediately
"""
import socket, time, re, sys, os, random as _rnd
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8")

TARGET_KILLS = 4
LOG = os.path.join(os.environ.get("TEMP","C:/Users/ying/AppData/Local/Temp"), "multikill.log")
MFILE = os.path.join(os.environ.get("TEMP","C:/Users/ying/AppData/Local/Temp"), "yxcdrg_mission.txt")

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
def show(label,b): t=clean(b); print(f"\n--- {label} ---"); print(t[-1500:])
def m(s,d,q=1.0):
    r=clean(send(s,d.encode()+b"\r\n",quiet=q))
    with open(LOG,"a",encoding="utf-8") as f: f.write(f">> {d}\n{r}\n")
    return r
def look(s):
    drain(s,quiet=0.5,maxt=2.0)
    b=send(s,b"look\r\n",quiet=2.0); return clean(b),b

def firstline(desc):
    for line in desc.split("\n")[:5]:
        line=line.strip()
        if line and not line.startswith(">"): return line
    return ""

def get_exits(desc):
    """Parse exits from room desc. Check compound dirs before simple to avoid substring match."""
    exits=set()
    dl=desc.lower()
    # Check compound first, then simple — prevents "west" matching inside "southwest"
    for en in ["northeast","northwest","southeast","southwest","eastup","westdown","northup","southdown"]:
        if en in dl: exits.add(en)
    # Simple dirs: only add if they appear standalone (not solely as part of a compound already matched)
    for simple, compounds in [("north",["northeast","northwest","northup"]),
                               ("south",["southeast","southwest","southdown"]),
                               ("east", ["northeast","southeast","eastup"]),
                               ("west", ["northwest","southwest","westdown"])]:
        if simple in dl:
            # strip all matched compounds from string, see if simple still appears
            stripped=dl
            for c in compounds:
                stripped=stripped.replace(c,"")
            if simple in stripped: exits.add(simple)
    # "up"/"down" also need compound stripping (eastup/northup contain "up"; southdown/westdown contain "down")
    stripped_up=dl.replace("eastup","").replace("northup","")
    if "up" in stripped_up: exits.add("up")
    stripped_down=dl.replace("southdown","").replace("westdown","")
    if "down" in stripped_down: exits.add("down")
    for en in ["enter","out"]:
        if en in dl: exits.add(en)
    return exits

REVERSE={"east":"west","west":"east","north":"south","south":"north",
         "northeast":"southwest","southwest":"northeast",
         "northwest":"southeast","southeast":"northwest",
         "up":"down","down":"up"}

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
           ("小岛","island"),("袁氏草堂","caotang"),("西门","ximen"),
           ("二楼雅座","erlouya"),("系统公告室","gonggao"),
           ("背阴巷","beiyin"),("官道","guandao"),("乐游原","guandao"),
           ("进士场","jinshi"),("曲江","qujiang"),("小雁塔","xiaoyanta"),
           # Underworld — multiple room names possible
           ("阴阳界","hell"),("黄泉","hell"),("地府","hell"),("奈何桥","hell"),
           # Huaguoshan (Flower-Fruit Mountain) and Aolai Kingdom
           ("仙石","huaguo"),("花果山","huaguo"),("水帘洞","huaguo"),
           ("傲来国","aolai"),("北城门","aolai"),("北老街","aolai"),("南城门","aolai"),
           ("东城门","aolai"),("西城门","aolai"),("张家","aolai"),
           # Dragon Palace — match "海底 -" not "海底" to avoid kelp forest (海底莽林) matching
           ("海底 -","haidi"),("龙宫大门","longmen"),("广场","guangchang"),
           ("紫云宫","ziyungong"),("花园","huayuan"),("绣房","xiufang"),
           ("沁玉殿","taizi1"),("过道","taizi2"),("练功堂","taizi4"),
           ("玉阶","yujie")]
    for kw,name in rooms:
        if kw in fl: return name
    for kw,name in rooms:
        if kw in desc[:200]: return name
    kw2=["杨记","春醇","七里","兰亭","西湖路","东湖路","钱庄","万寿","宁心",
         "静心","清心","三心","禹王","古亭","酒楼","盔甲","兵器场","水陆"]
    if any(k in fl for k in kw2): return "kaifeng_other"
    return "unknown"

def beiyin_escape(s, desc):
    if "朱雀大街" in desc or "杂货铺" in desc: m(s,"east"); return
    if "粮店" in desc: m(s,"southeast"); return
    if "帮会" in desc: m(s,"south"); return
    ex=get_exits(desc)
    if "west" in ex and "south" in ex: m(s,"east"); return
    m(s,"north")

def goto_hub(s, max_steps=50):
    last_dir=None; bug_streak=0
    for step in range(max_steps):
        desc,_=look(s); rid=roomid(desc)
        if "系统" in desc and ("BUG" in desc.upper() or "ＢＵＧ" in desc):
            bug_streak+=1
            if bug_streak>=3: time.sleep(5); drain(s,quiet=1.0,maxt=3.0); bug_streak=0
            else: time.sleep(1.5)
            continue
        bug_streak=0
        if rid=="hub": return True
        if rid=="hell":
            # Escape underworld — try open coffin first, then wander exits
            r_hell=m(s,"open guancai",q=3.0)
            if "什么" in r_hell or "没有" in r_hell:
                # No coffin here; try wandering to find one
                ex_h=get_exits(desc)
                for dh in ["north","south","east","west","northup","southdown","eastup","westdown","out","down","up"]:
                    if dh in ex_h: m(s,dh,q=1.5); break
            time.sleep(1)
            continue
        if rid in ("huaguo","aolai"):
            # Check for raft first (escape Aolai island)
            if "木筏" in desc or "mufa" in desc.lower():
                r_zuo=m(s,"zuo mufa",q=2.0)
                if "什么" not in r_zuo:
                    time.sleep(1.0)
                    r_enter=m(s,"enter",q=4.0)  # start journey
                    if "孤筏" in r_enter or "木筏" in r_enter or "海中" in r_enter:
                        # On the raft — wait up to 60s for it to hit land
                        print("  [RAFT] crossing sea...")
                        arrived=False
                        for _ in range(12):  # 12×5s = 60s max
                            time.sleep(5.0)
                            chunk=clean(drain(s,quiet=0.5,maxt=1.0))
                            if chunk: print(f"  [RAFT] {chunk[:80]}")
                            if "撞" in chunk or "陆地" in chunk or "大陆" in chunk or "岸边" in chunk:
                                arrived=True; break
                        if arrived or True:  # try out regardless after waiting
                            m(s,"out",q=3.0)
                    continue
                # If zuo mufa fails, try enter directly
                m(s,"enter",q=2.0)
            if rid=="huaguo":
                # Navigate DOWN off Flower-Fruit Mountain
                ex=get_exits(desc)
                for dh in ["south","southdown","westdown","down","east","west","north","eastup","northup"]:
                    if dh in ex and dh!=last_dir: m(s,dh); last_dir=dh; break
                else:
                    for dh in ["south","southdown","westdown","down","east","west","north","eastup","northup"]:
                        if dh in ex: m(s,dh); last_dir=dh; break
            else:
                # In Aolai: head west (sea/raft) or south; avoid going east (toward Huaguoshan)
                ex=get_exits(desc)
                for dh in ["west","south","southwest","southeast","north","east"]:
                    if dh in ex and dh!=last_dir: m(s,dh); last_dir=dh; break
                else:
                    for dh in ["west","south","southwest","southeast","north","east"]:
                        if dh in ex: m(s,dh); last_dir=dh; break
            continue
        if rid=="beiyin": beiyin_escape(s,desc); continue
        if rid=="haidi":
            # Navigate toward under1 (only room with "up" exit).
            # under4: exits east+southwest; under3: west+ne+sw; under2: west+east; under1: east+up
            ex=get_exits(desc)
            if "up" in ex: m(s,"up",q=1.5)
            elif "southwest" in ex: m(s,"southwest")  # under4→under3 (check before west)
            elif "west" in ex: m(s,"west")            # under2/3→under1
            else: m(s,"east")                          # gate→under4 fallback
            continue
        nav={"kezhan":["west","north"],"zhuque":["north"],"qinglong":["west"],
             "xuanwu":["south"],"baihu":["east"],"yuan_room":["east","south"],
             "shop":["north","west"],"wuguan":["south","west"],"dangpu":["east","north"],
             "nancheng":["north","north","north","north"],
             "daguandao":["west" if ("平原" in desc or "由东西" in desc or "长安以东" in desc) else "north"],
             "zhongnan":["north"],"nanyue":["north"],"jingshui":["north"],
             "seashore":["north"],"eastsea":["west","north"],"seashore_e":["west"],
             "island":["swim"],"caotang":["south","east","east","east"],"ximen":["east"],
             "erlouya":["down"],"gonggao":["west"],
             "guandao":["northwest"],"jinshi":["northwest"],"qujiang":["north"],
             "xiaoyanta":["down"],
             "gao":["east"],"tieta":["west"],"tianpeng":["west"],"shuaifu":["west"],
             "shunwang":["south","southeast"],"yaowang":["south","southwest"],
             # Dragon Palace exit path → surface
             "haidi":["up"],"longmen":["west"],"guangchang":["west"],
             "ziyungong":["northwest"],"huayuan":["northwest"],
             "xiufang":["west"],"taizi1":["southwest"],"taizi2":["southwest"],
             "taizi4":["south"],"yujie":["westdown"]}
        if rid in ("unknown","kaifeng_other"):
            if step%4==0: print(f"  nav {step}: {rid.upper()} [{firstline(desc)[:30]}]")
            ex=get_exits(desc); avoid=REVERSE.get(last_dir); moved=False
            for d in ["west","north","northwest","south","east","northeast","southwest","southeast",
                      "northup","southdown","eastup","westdown","up","down","out"]:
                if d in ex and d!=avoid: m(s,d); last_dir=d; moved=True; break
            if not moved:
                for d in ["west","north","east","south","northup","southdown","eastup","westdown"]:
                    if d in ex: m(s,d); last_dir=d; moved=True; break
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
    "Taizong","Hezhizhang","Gongsun","Gao tai","Cuiying","Xiao ying","Xiushi",
    # Dragon Palace NPCs
    "Long nu","Long wang","Long po","Long shao","Gong nu","Qiu po","Haima",
    "Long1","Long2","Long3","Long4","Long5","Long6","Long7","Long8","Long9",
    "Soldier1","Soldier2","Yecha","Kid1","Kid2","Kid3","Wushi","Lishi",
    "Biantidu","Biaodi","Gonge","Gui","Jing","Beinu","Beisao","Beast",
    "Shark","Zhangmen","Zitaiwei","Qingdusi","Lizongbing"}

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
    time.sleep(0.3)
    for tid in ["guai","jing"]:
        rf=m(s,f"follow {tid}",q=1.0); time.sleep(0.3)
        if any(w in rf for w in ["跟随","跟着","follow","跟"]): print(f"  >> following {tid}"); break
    for chase in range(3):
        for tid in ["guai","jing"]:
            r=m(s,f"kill {tid}",q=1.5); time.sleep(0.3)
            if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
                print(f"  >> ENGAGED: kill {tid}"); engaged=True; break
        if engaged: break
        desc,_=look(s)
        ex=list(get_exits(desc))[:3]; found_adj=False
        for d in ex:
            m(s,d); time.sleep(0.3)
            d2,_=look(s)
            if has_monster(d2,name): print(f"  >> chased to {d}"); found_adj=True; break
            m(s,REVERSE.get(d,"look")); time.sleep(0.3)
        if not found_adj: print("  !! Lost monster"); return False
    if not engaged: print("  !! Can't engage"); return False
    for j in range(70):
        time.sleep(3)
        b=drain(s,quiet=2.0,maxt=5.0)
        if b:
            r=clean(b)
            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                show("VICTORY",b); return True
            elif "承让" in r: print("  LOST"); return False
            elif "找机会逃跑" in r:
                time.sleep(2); drain(s,quiet=1.0,maxt=2.0)
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
        if has_monster(desc,name): print(f"\n  ** FOUND {name} step {i}! **"); return fight(s,name)
        if i%15==14: print(f"  search {i+1}/{len(moves)}")
    return False

def wander_search(s,name,steps):
    last=None
    for i in range(steps):
        desc,_=look(s)
        if has_monster(desc,name): print(f"\n  ** FOUND {name} wander {i}! **"); return fight(s,name)
        if "系统" in desc and ("BUG" in desc.upper() or "ＢＵＧ" in desc):
            time.sleep(5); drain(s,quiet=1.0,maxt=3.0); continue
        ex=list(get_exits(desc))
        if not ex: m(s,"look"); continue
        avoid=REVERSE.get(last)
        choices=[d for d in ex if d!=avoid] or ex
        d=_rnd.choice(choices)
        m(s,d); time.sleep(0.2); last=d
        if i%15==14: print(f"  wander {i+1}/{steps}")
    return False

# Location hints for areas we don't have mapped routes to yet
AREA_HINTS={
    "方寸": ["方寸","灵台","松树林","仙桃"],
    "斜月": ["斜月","三星"],
    "天竺": ["天竺","西域"],
}

def explore_for(s, name, loc, max_steps=60):
    """Quick explore from hub looking for monster in an unmapped area.
    Uses move responses (not separate look) for speed. Max 60 steps."""
    hints=[]
    for key,vals in AREA_HINTS.items():
        if key in loc: hints=vals; break
    if not hints and loc:
        hints=[loc[:2]] if len(loc)>=2 else []
    print(f"  [EXPLORE] hub→explore for {name} | hints={hints}")
    goto_hub(s)
    visited=set()
    last=None; same_room_count=0; last_fl=""
    for i in range(max_steps):
        # Quick look — short quiet time to not block on system msgs
        drain(s,quiet=0.3,maxt=1.0)
        raw=send(s,b"look\r\n",quiet=1.0)
        desc=clean(raw); fl=firstline(desc)
        # Stuck detector: if same room 4+ times in a row, escape to hub
        if fl==last_fl: same_room_count+=1
        else: same_room_count=0; last_fl=fl
        if same_room_count>=4:
            print(f"  [EXPLORE] stuck at {fl[:30]} — returning to hub")
            goto_hub(s); last=None; same_room_count=0; continue
        if hints and any(h in desc for h in hints):
            print(f"  [EXPLORE] found target area at step {i}: {fl}")
            if has_monster(desc,name): return fight(s,name)
            return wander_search(s,name,60)
        if has_monster(desc,name):
            print(f"\n  ** FOUND {name} explore step {i}! **"); return fight(s,name)
        ex=list(get_exits(desc))
        if not ex: continue
        avoid=REVERSE.get(last)
        unvisited=[d for d in ex if d!=avoid and f"{fl}:{d}" not in visited]
        choices=unvisited if unvisited else [d for d in ex if d!=avoid]
        if not choices: choices=ex
        d=_rnd.choice(choices)
        visited.add(f"{fl}:{d}")
        # Move: use short quiet time (move response = next room desc)
        send(s,(d+"\r\n").encode(),quiet=0.8)
        last=d
        if i%10==9: print(f"  [EXPLORE] step {i+1}/{max_steps} at {fl[:40]}")
    return False

def decode(loc):
    if not loc: return ("UNREACHABLE-unknown",None,None)
    if "长安城西" in loc:
        return ("westway", ["west"]*5,
                ["west","west","northwest",
                 "southeast","east","east","east",
                 "west","west","west","northwest",
                 "southeast","east","east",
                 "south","north","west","east"]*2)
    if "高老庄" in loc:
        return ("gao", ["south"]*13+["west"]*4,
                ["east"]*5+["north","east","west","west","east"]*3+["south"]*5+
                ["west","south"]*3+["east","west","south"])
    if "普陀" in loc:
        if "紫竹" in loc or "竹林" in loc:
            srch=(["north","north","east","north","north"]+
                  ["north","east","south","west","northeast","northwest",
                   "southeast","southwest"]*5+["north","east","west"]*3)
        else:
            srch=(["north","north"]+["west","east","south","enter","out"]*2+
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
    if "长安城" in loc or "粮仓" in loc:
        return ("city", [],
            ["south","east","west","west","east","south","east","west",
             "south","east","west","south","west","northwest","east","west",
             "west","south","north","north","south","east","southeast","south",
             "north","east","north","north","north","north",
             "east","north","south","west","west","west","south","north",
             "west","south","north","east","east","north","east","west","south"])
    return ("UNREACHABLE-"+loc[:6], None, None)

def save_m(n,l):
    try: open(MFILE,"w",encoding="utf-8").write(f"{n}|{l or ''}")
    except: pass
def load_m():
    try:
        p=open(MFILE,encoding="utf-8").read().strip().split("|",1)
        return p[0],(p[1] if len(p)>1 else None)
    except: return None,None

def ask_yuan(s):
    """Ask yuan for kill mission. Returns (name, loc) or (None, None)."""
    goto_hub(s)
    m(s,"north"); m(s,"west")
    d,_=look(s)
    if "天监台" not in d:
        goto_hub(s); m(s,"north"); m(s,"west")
    b=send(s,b"ask yuan about kill\r\n",quiet=3.0)
    yuan=clean(b); show(f"YUAN",b)
    name=None; loc=None
    mm=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan)
    if mm: name=mm.group(1); loc=mm.group(3); save_m(name,loc)
    elif "除尽" in yuan:
        b=send(s,b"ask yuan about kill\r\n",quiet=3.0); yuan=clean(b)
        mm=re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没',yuan)
        if mm: name=mm.group(1); loc=mm.group(3); save_m(name,loc)
    elif "收服" in yuan:
        mm=re.search(r'收服(.+?)吗',yuan)
        if mm: name=mm.group(1); _,loc=load_m()
    return name,loc

# ============================================================
print("=== MULTI-KILL BOT ===")
with open(LOG,"w",encoding="utf-8") as f: f.write("=== MULTIKILL LOG ===\n")

s=socket.create_connection(("146.190.143.182",6666),timeout=15)
drain(s,quiet=3.0,maxt=12.0)
m(s,"gb"); m(s,"no"); m(s,"yxcdrg")
r=clean(send(s,b"198633\r\n",quiet=4.0))
if "y/n" in r: m(s,"y",q=4.0)
m(s,"set wimpy 5")

print("\n[SETUP] checking state...")
goto_hub(s)
hp_r=m(s,"hp",q=2.0)
sc_r=m(s,"score",q=2.5)

dmg_m=re.search(r'兵器伤害力：\[\s*(\d+)\s*\]',sc_r)
arm_m=re.search(r'盔甲保护力：\[\s*(\d+)\s*\]',sc_r)
have_dmg=int(dmg_m.group(1)) if dmg_m else 0
have_arm=int(arm_m.group(1)) if arm_m else 0
food_m=re.search(r'食物：\s*(\d+)\s*/\s*(\d+)',hp_r)
water_m=re.search(r'饮水：\s*(\d+)\s*/\s*(\d+)',hp_r)
food_cur=int(food_m.group(1)) if food_m else 0
food_max=int(food_m.group(2)) if food_m else 360
water_cur=int(water_m.group(1)) if water_m else 0
water_max=int(water_m.group(2)) if water_m else 360
print(f"  gear: dmg={have_dmg} armor={have_arm} | food={food_cur}/{food_max} water={water_cur}/{water_max}")

# Buy fork + shield if missing
if have_dmg==0 or have_arm==0:
    m(s,"east"); m(s,"south")  # shop
    d,_=look(s)
    if "兵器铺" in d:
        if have_dmg==0:
            m(s,"buy fork from xiao xiao",q=1.5)
            m(s,"wield fork")
            print("  Bought + wielded fork")
        if have_arm==0:
            m(s,"buy shield from xiao xiao",q=1.5)
            m(s,"wear shield")
            print("  Bought + wore shield")
    m(s,"north"); m(s,"west")
    # re-check
    sc2=m(s,"score",q=2.5)
    dmg_m2=re.search(r'兵器伤害力：\[\s*(\d+)\s*\]',sc2)
    arm_m2=re.search(r'盔甲保护力：\[\s*(\d+)\s*\]',sc2)
    have_dmg=int(dmg_m2.group(1)) if dmg_m2 else have_dmg
    have_arm=int(arm_m2.group(1)) if arm_m2 else have_arm
    print(f"  gear after buy: dmg={have_dmg} armor={have_arm}")

# Food/water if below 50%
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
    print("  Food/water OK")

show("READY", send(s,b"score\r\n",quiet=3.0))

# KILL LOOP — no report-back between kills
kill_count=0
for attempt in range(20):
    if kill_count>=TARGET_KILLS:
        print(f"\n  *** Reached {kill_count} kills — done! ***")
        break

    print(f"\n[ATTEMPT {attempt+1}] kills so far: {kill_count}/{TARGET_KILLS}")
    name,loc=ask_yuan(s)

    if not name:
        print("  No mission, wait 60s"); time.sleep(60); continue

    area, travel, srch = decode(loc)
    print(f"  Mission: {name} @ {loc} → {area}")

    if area.startswith("UNREACHABLE"):
        # Try a quick explore first, then fall back to waiting for Yuan's timer
        print(f"  >> {area} — quick explore for {name}")
        killed=explore_for(s, name, loc or "", max_steps=60)
        if killed:
            kill_count+=1
            print(f"\n  *** KILL #{kill_count} — {name} (explored) ***")
            time.sleep(2); drain(s,quiet=1.0,maxt=3.0)
            m(s,"get all",q=1.5)
        else:
            # Exploration failed — wait for Yuan's 30-min mission timer to expire
            print(f"  >> Could not find {loc}, waiting for Yuan timer (30s retry)")
            time.sleep(30); drain(s,quiet=0.4,maxt=1.0)
        continue

    goto_hub(s)
    m(s,"east"); m(s,"south")  # leave yuan area
    goto_hub(s)

    # Travel
    killed=False
    for d2 in travel:
        m(s,d2)
        dt,_=look(s)
        if has_monster(dt,name):
            print("  >> Found during travel!")
            killed=fight(s,name)
            if killed: break

    # Search
    if not killed and srch:
        print(f"  Route pass ({len(srch)} rooms)")
        killed=search(s,name,srch)
    if not killed:
        steps=200 if area=="putuo" else (130 if area in ("kaifeng","gao") else 80)
        print(f"  Wander {steps} steps")
        killed=wander_search(s,name,steps)

    if killed:
        kill_count+=1
        print(f"\n  *** KILL #{kill_count} — {name} ***")
        time.sleep(2); drain(s,quiet=1.0,maxt=3.0)
        m(s,"get all",q=1.5)  # collect any dropped money/items
        # No report-back — just go straight to next mission
    else:
        print(f"  !! Failed to kill {name}, trying next mission")

print(f"\n=== FINAL: {kill_count} kills ===")
show("HP", send(s,b"hp\r\n",quiet=2.0))
show("SCORE", send(s,b"score\r\n",quiet=3.0))
print("*** NO QUIT ***")
time.sleep(1); s.close()
