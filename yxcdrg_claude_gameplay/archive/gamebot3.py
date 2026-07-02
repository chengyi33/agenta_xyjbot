"""
Game Bot v3 — fixes from v1/v2:
- Wimpy 5 (don't flee early)
- Spam food/water to FULL
- Debug print when stuck navigating
- WAITING state for stale old missions
- Re-engage after flee
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
def send(s, d, quiet=2.0): s.sendall(d); return drain(s, quiet=quiet)
def clean(b):
    for enc in ["utf-8", "gbk"]:
        try:
            t = b.replace(b"\x00", b"").decode(enc)
            return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", t)
        except: pass
    return b.replace(b"\x00", b"").decode("gbk", errors="replace")
def cmd(s, c, quiet=1.5):
    return clean(send(s, c.encode()+b"\r\n", quiet=quiet))

# Room detection
def identify_room(desc):
    # Order matters — more specific first
    checks = [
        ("hub", "十字街头"), ("kezhan", "南城客栈"), ("yuan", "天监台"),
        ("weaponshop", "兵器铺"), ("wuguan", "长安武馆"), ("dangpu", "董记当铺"),
        ("xuanwu", "玄武大街"), ("nanchengkou", "南城口"),
        ("gao_gate", "高家大门"), ("gao_yard", "正院"), ("gao_pianfang", "偏房"),
        ("gao_zhengting", "正厅"), ("gao_houyuan", "后院"),
        ("tianpeng", "天蓬"), ("shuaifu", "帅府"),
        ("tieta", "汴京铁塔"), ("machang", "马场"),
        ("shanmen", "山门"), ("seashore", "南海之滨"), ("island", "小岛"),
        ("tingjing", "听经"), ("shanlu", "山路"),
        # Generic last
        ("qinglong", "青龙大街"), ("baihu", "白虎大街"),
        ("zhuque", "朱雀大街"),
        ("gao_tulu", "土路"), ("gao_jiedao", "街道"),
        ("shunwang", "舜王街"), ("yaowang", "尧王街"),
        ("kaifeng", "开封"), ("chenlong", "辰龙"),
        ("kaifeng_other", "酒楼"), ("kaifeng_other", "盔甲场"),
        ("daguandao", "大官道"), ("zhongnan", "终南"), ("nanyue", "南岳"),
        ("jingshui", "泾水"), ("putuo", "普陀"),
    ]
    for rid, kw in checks:
        if kw in desc: return rid
    return "unknown"

def step_toward_hub(room, desc):
    m = {
        "kezhan": "west", "dangpu": "east",
        "weaponshop": "north", "wuguan": "south",
        "yuan": "east", "xuanwu": "south",
        "qinglong": "west", "baihu": "east",
        "nanchengkou": "north",
        "daguandao": "north", "zhongnan": "north", "nanyue": "north",
        "jingshui": "north", "seashore": "north",
        "island": "swim", "tingjing": "south", "shanmen": "southdown",
        "gao_tulu": "east", "gao_jiedao": "east", "gao_gate": "south",
        "gao_yard": "south", "gao_pianfang": "west", "gao_zhengting": "south",
        "gao_houyuan": "south",
        "kaifeng": "west", "chenlong": "west", "tieta": "west",
        "machang": "north", "shunwang": "south", "yaowang": "south",
        "tianpeng": "west", "shuaifu": "west", "kaifeng_other": "west",
    }
    # Return direction(s) — caller should try first, if fails try next
    if room in m: return m[room]
    if room == "shanlu": return "south"
    if room == "zhuque": return "north"
    if "朝阳门" in desc: return "south"
    if "国子监" in desc: return "west"
    if "化生" in desc or "方丈" in desc or "大雄" in desc: return "north"
    if "背阴" in desc or "民居" in desc or "粮" in desc or "小酒馆" in desc: return "north"
    if "药铺" in desc or "乐坊" in desc or "毛货" in desc or "鞋帽" in desc or "杂货" in desc: return "north"
    if "书局" in desc or "钱庄" in desc: return "south"
    if "御相" in desc: return "east"
    if "东门" in desc: return "west"
    # 大官道: if between cities (east of 长安), go west. If south of 长安, go north.
    if room == "daguandao":
        if "平原" in desc or "由东西" in desc or "长安以东" in desc: return "west"
        return "north"
    if "帅府" in desc or "天蓬" in desc: return "west"
    if "兰亭" in desc or "翠兰" in desc or "玉兰" in desc or "香兰" in desc: return "west"
    if "七里" in desc or "春醇" in desc or "杨记" in desc: return "west"
    # Catch-all: any Kaifeng-related room → go west (back toward Chang'an)
    kaifeng_kw = ["酒楼","盔甲","兵器场","中堂","府门","武将","水陆","赛场",
                  "观礼","药库","禹王","万寿","宁心","静心","三心","湖路","古亭"]
    if any(k in desc for k in kaifeng_kw): return "west"
    return "north"

KNOWN = set(["Board","paizi","Agenta","Snoopl","Snoopy","Xiao er","Da ye",
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
    "Gao tai","Cuiying","Xiao ying","Lao liu"])

def find_monster(desc, name):
    for line in desc.split("\n"):
        line = line.strip()
        if "(" not in line or ")" not in line: continue
        if any(k in line for k in KNOWN): continue
        if name and name in line:
            m = re.search(r'\(([^)]+)\)', line)
            return m.group(1).strip() if m else None
    return None

def get_travel(loc):
    if not loc: return []
    if "高老庄" in loc: return ["south"]*13+["west"]*4
    if "开封" in loc:
        if "尧" in loc: return ["east"]*13+["northeast"]
        if "舜" in loc or "御相" in loc: return ["east"]*13+["northwest"]
        return ["east"]*13+["northeast"]
    if "普陀" in loc: return ["south"]*16+["swim","north","north","northup","northup"]
    if "望南" in loc: return ["east"]*3+["south"]
    if "长安城西" in loc: return ["west"]*5
    return []  # city — search from hub

def get_search(loc):
    if not loc: return []
    if "高老庄" in loc:
        return ["east","east","east","east",  # road to gate
                "north","east","west","west","east",  # yard, pianfang, zhangfang
                "north","east","west","west","east",  # zhengting, fanting, pianting
                "north","east","west","west","north","south","east","east","west",  # houyuan
                "south","south","south","south",  # back to gate
                "west","south","north","west","south","south","south","east","west","south"]
    if "开封" in loc and "尧" in loc:
        return ["north","east","west","north","east","west","north","north",
                "east","west","south","south","south","south"]
    if "开封" in loc:
        return ["north"]*4+["west","east"]+["south"]*4+["southeast"]+\
               ["northeast"]+["north"]*4+["south"]*4
    if "普陀" in loc:
        return ["north"]*5+["east","west"]+["south"]*5+["west"]*2+["east"]*3+["south"]*3
    if "望南" in loc:
        return ["southwest","south","west","southwest","northeast","east",
                "north","northeast","east","west"]
    # City
    return ["south","east","west","west","east",
            "south","east","west","south","east","west","south",
            "west","northwest","east","west","west","south","north",
            "north","south","east","southeast","south","north",
            "east","north","north","north","north",
            "east","north","south","east","north","south",
            "west","west","west","south","north",
            "west","south","north","east","east",
            "north","east","west","south"]

# ============================================
print("=== GAME BOT v3 ===")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
cmd(s,"gb"); cmd(s,"no"); cmd(s,"yxcdrg")
r = cmd(s,"198633",quiet=4.0)
if "y/n" in r: cmd(s,"y",quiet=4.0)
cmd(s,"set wimpy 5")

state = "CHECK"
monster_name = None; monster_loc = None
travel_route = []; search_route = []
travel_i = 0; search_i = 0
old_mission_count = 0  # track how many times we see same old mission
last_room = ""; stuck_count = 0
next_dest = ""
tick = 0; killed = False

while tick < 300 and not killed:
    tick += 1
    desc = cmd(s, "look")
    room = identify_room(desc)

    # Stuck detection — if same room 10 times, debug print
    if room == last_room:
        stuck_count += 1
        if stuck_count >= 5:
            print(f"  !! STUCK at {room} for {stuck_count} ticks. Desc: {desc[:60]}")
            # Try directions based on context
            if any(k in desc for k in ["尧王","舜王","铁塔","辰龙","开封","天蓬","帅府","酒楼","盔甲","兵器场"]):
                dirs = ["southwest","southeast","west","south","north","northwest","northeast"]
            else:
                dirs = ["south","west","east","north","down","up","out"]
            for d in dirs:
                r = cmd(s, d)
                if "什么" not in r and "不能" not in r: break
            stuck_count = 0
    else:
        stuck_count = 0
    last_room = room

    # Monster check — always scan current room
    if monster_name:
        kid = find_monster(desc, monster_name)
        if kid:
            print(f"\n  !! MONSTER: {monster_name} tick {tick}!")
            # ALWAYS try jing/guai FIRST — parsed ID can be corrupted
            for tid in ["jing", "guai", kid.split()[0].lower() if kid else None]:
                if not tid: continue
                r = cmd(s, f"kill {tid}")
                if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
                    print(f"  >> ENGAGED: kill {tid}")
                    # FIGHT LOOP
                    for j in range(60):
                        time.sleep(3)
                        b = drain(s, quiet=2.0, maxt=5.0)
                        if b:
                            r = clean(b)
                            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                                print(f"\n  ******* VICTORY! *******")
                                print(f"  {r[:200]}")
                                killed = True; break
                            elif "承让" in r:
                                print("  >> LOST"); break
                            elif "找机会逃跑" in r:
                                print("  >> FLED — trying to re-engage!")
                                time.sleep(2)
                                # Look and try to kill again in same room
                                d2 = cmd(s,"look")
                                if monster_name in d2:
                                    cmd(s, f"kill {tid}")
                                    print("  >> RE-ENGAGED!")
                                else:
                                    print("  >> Monster gone after flee")
                                    break
                            elif "清醒" in r:
                                print("  >> KO'd — recovering")
                                break
                            elif j % 5 == 0:
                                lines = [l for l in r.split("\n") if l.strip() and ">" not in l]
                                if lines: print(f"  [{j}] {lines[-1].strip()[:70]}")
                    break
            if killed: break
            continue

    # STATE MACHINE
    if state == "CHECK":
        hp_r = cmd(s,"hp")
        food_m = re.search(r"食物：\s*(\d+)/\s*(\d+)", hp_r)
        water_m = re.search(r"饮水：\s*(\d+)/\s*(\d+)", hp_r)
        food = int(food_m.group(1)) if food_m else 999
        food_max = int(food_m.group(2)) if food_m else 999
        water = int(water_m.group(1)) if water_m else 999
        sc = cmd(s,"score")
        wpn = int(m.group(1)) if (m:=re.search(r"兵器伤害力：\[(\d+)\]",sc)) else 0
        arm = int(m.group(1)) if (m:=re.search(r"盔甲保护力：\[(\d+)\]",sc)) else 0

        print(f"\n  [{tick}] {room} food={food}/{food_max} water={water} wpn={wpn} arm={arm} →", end="")

        if food < 100 or water < 100:
            print("NEED_FOOD"); state="GOTO_HUB"; next_dest="kezhan"
        elif wpn == 0 or arm < 10:
            print("NEED_GEAR"); state="GOTO_HUB"; next_dest="weaponshop"
        elif monster_name is None:
            print("NEED_MISSION"); state="GOTO_HUB"; next_dest="yuan"
        else:
            print("HUNT")
            if any(k in desc for k in ["高老庄","高家","土路","街道","正院","偏房"]) and "高老庄" in (monster_loc or ""):
                state="SEARCHING"; search_route=get_search(monster_loc); search_i=0
            elif room=="hub" or (monster_loc and "长安" in monster_loc and room in ["hub","zhuque","qinglong","baihu"]):
                state="TRAVELING" if get_travel(monster_loc) else "SEARCHING"
                travel_route=get_travel(monster_loc); travel_i=0
                search_route=get_search(monster_loc); search_i=0
            else:
                state="GOTO_HUB"; next_dest="travel"

    elif state == "GOTO_HUB":
        if room == "hub":
            if next_dest=="kezhan": state="DO_FOOD"
            elif next_dest=="weaponshop": state="DO_GEAR"
            elif next_dest=="yuan": state="DO_YUAN"
            elif next_dest=="travel":
                travel_route=get_travel(monster_loc); travel_i=0
                search_route=get_search(monster_loc); search_i=0
                state = "TRAVELING" if travel_route else "SEARCHING"
            print(f"  [{tick}] HUB → {state}")
        else:
            d = step_toward_hub(room, desc)
            cmd(s, d)

    elif state == "DO_FOOD":
        cmd(s,"south"); cmd(s,"east")
        d2 = cmd(s,"look")
        if "南城客栈" in d2:
            # Spam buy and eat/drink until full
            for _ in range(8): cmd(s,"buy jitui from xiao er",quiet=0.5)
            for _ in range(3): cmd(s,"buy jiudai from xiao er",quiet=0.5)
            for _ in range(10): cmd(s,"eat jitui",quiet=0.3)
            for _ in range(5): cmd(s,"drink jiudai",quiet=0.3)
            hp2 = cmd(s,"hp")
            fm = re.search(r"食物：\s*(\d+)", hp2)
            wm = re.search(r"饮水：\s*(\d+)", hp2)
            print(f"  [{tick}] FED! food={fm.group(1) if fm else '?'} water={wm.group(1) if wm else '?'}")
        cmd(s,"west"); cmd(s,"north")  # back to hub
        state = "CHECK"

    elif state == "DO_GEAR":
        cmd(s,"east"); cmd(s,"south")
        d2 = cmd(s,"look")
        if "兵器铺" in d2:
            cmd(s,"buy blade from xiao xiao"); cmd(s,"wield blade")
            cmd(s,"buy shield from xiao xiao"); cmd(s,"wear shield")
            print(f"  [{tick}] GEARED!")
        cmd(s,"north"); cmd(s,"west")
        state = "CHECK"

    elif state == "DO_YUAN":
        cmd(s,"north"); cmd(s,"west")
        d2 = cmd(s,"look")
        if "天监台" in d2:
            r = cmd(s,"ask yuan about kill",quiet=3.0)
            print(f"  [{tick}] YUAN: {r.strip()[:120]}")
            m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', r)
            if m:
                monster_name=m.group(1); monster_loc=m.group(3)
                old_mission_count = 0
                print(f"  >> NEW: {monster_name} @ {monster_loc}")
            elif "除尽" in r:
                r2 = cmd(s,"ask yuan about kill",quiet=3.0)
                m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', r2)
                if m:
                    monster_name=m.group(1); monster_loc=m.group(3)
                    old_mission_count = 0
                    print(f"  >> NEW: {monster_name} @ {monster_loc}")
            elif "收服" in r:
                m2 = re.search(r'收服(.+?)吗', r)
                if m2:
                    monster_name = m2.group(1)
                    old_mission_count += 1
                    print(f"  >> OLD: {monster_name} (seen {old_mission_count}x)")
                    if old_mission_count >= 3:
                        print(f"  >> Stale mission, waiting 60s for expiry...")
                        state = "WAITING"
                        cmd(s,"east"); cmd(s,"south")  # back to hub
                        continue
        cmd(s,"east"); cmd(s,"south")  # back to hub
        state = "CHECK"

    elif state == "WAITING":
        # Wait for old mission to expire
        print(f"  [{tick}] Waiting 60s...")
        time.sleep(60)
        drain(s, quiet=1.0, maxt=2.0)  # clear buffer
        old_mission_count = 0
        monster_name = None
        state = "CHECK"

    elif state == "TRAVELING":
        if travel_i >= len(travel_route):
            state = "SEARCHING"; search_i = 0
            print(f"  [{tick}] ARRIVED → SEARCHING")
        else:
            cmd(s, travel_route[travel_i]); travel_i += 1
            if travel_i % 5 == 0: print(f"  [{tick}] traveling {travel_i}/{len(travel_route)}")

    elif state == "SEARCHING":
        if search_i >= len(search_route):
            print(f"  [{tick}] Search done — not found")
            monster_name = None; state = "CHECK"
        else:
            cmd(s, search_route[search_i]); search_i += 1
            if search_i % 5 == 0: print(f"  [{tick}] searching {search_i}/{len(search_route)}")

# === END ===
print(f"\n=== BOT v3 ENDED tick={tick} killed={killed} ===")
if killed:
    # Report to yuan
    print("  Reporting to yuan...")
    for _ in range(25):
        d = cmd(s,"look"); rm = identify_room(d)
        if rm == "hub": break
        cmd(s, step_toward_hub(rm, d))
    cmd(s,"north"); cmd(s,"west")
    r = cmd(s,"ask yuan about kill",quiet=3.0)
    print(f"  YUAN: {r[:200]}")

print(f"\n  HP: {cmd(s,'hp')[:100]}")
print(f"  SCORE: {cmd(s,'score')[:200]}")
print("\n*** NO QUIT ***")
s.close()
