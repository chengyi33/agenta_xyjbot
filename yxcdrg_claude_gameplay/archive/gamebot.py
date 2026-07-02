"""
Persistent MUD game bot for yxcdrg.
Stays connected. Makes ONE decision per tick. Verifies each step.
"""
import socket, time, re, sys, json
sys.stdout.reconfigure(line_buffering=True)

# === NETWORK ===
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
    b = send(s, c.encode()+b"\r\n", quiet=quiet)
    return clean(b)

# === ROOM DETECTION ===
ROOM_KEYWORDS = {
    "hub": "十字街头", "kezhan": "南城客栈", "yuan": "天监台",
    "weaponshop": "兵器铺", "zhuque": "朱雀大街", "qinglong": "青龙大街",
    "xuanwu": "玄武大街", "baihu": "白虎大街", "wuguan": "长安武馆",
    "dangpu": "董记当铺", "nanchengkou": "南城口",
    "daguandao": "大官道", "zhongnan": "终南", "nanyue": "南岳",
    "jingshui": "泾水", "seashore": "南海之滨",
    "island": "小岛", "tingjing": "听经", "shanlu": "山路",
    "shanmen": "山门", "putuo": "普陀",
    "gao_tulu": "土路", "gao_jiedao": "街道", "gao_gate": "高家大门",
    "gao_yard": "正院", "gao_pianfang": "偏房",
    "gao_zhengting": "正厅", "gao_houyuan": "后院",
    "kaifeng": "开封", "chenlong": "辰龙", "tieta": "汴京铁塔",
    "machang": "马场", "shunwang": "舜王", "yaowang": "尧王",
    "yaopu": "药铺", "lefang": "乐坊",
}
def identify_room(desc):
    for rid, kw in ROOM_KEYWORDS.items():
        if kw in desc:
            return rid
    return "unknown"

# === NEXT STEP TO HUB ===
def step_toward_hub(room_id, desc):
    """Returns direction(s) to move one step closer to hub."""
    m = {
        "kezhan": ["west"],
        "zhuque": ["north"],
        "qinglong": ["west"],
        "xuanwu": ["south"],
        "baihu": ["east"],
        "yuan": ["east"],
        "weaponshop": ["north"],
        "wuguan": ["south"],
        "dangpu": ["east"],
        "nanchengkou": ["north"],
        "daguandao": ["north"], "zhongnan": ["north"], "nanyue": ["north"],
        "jingshui": ["north"],
        "seashore": ["north"],
        "island": ["swim"],  # special
        "tingjing": ["south"],
        "shanlu": ["south", "southdown"],  # try both
        "shanmen": ["southdown"],
        "putuo": ["south"],
        "gao_tulu": ["east"], "gao_jiedao": ["east"], "gao_gate": ["south"],
        "gao_yard": ["south"], "gao_pianfang": ["west"], "gao_zhengting": ["south"],
        "gao_houyuan": ["south"],
        "kaifeng": ["west"], "chenlong": ["west"], "tieta": ["west"],
        "machang": ["north"], "shunwang": ["south"], "yaowang": ["south"],
        "yaopu": ["west"], "lefang": ["east"],
    }
    if room_id in m: return m[room_id]
    # Substrings for partial matches
    if "朝阳门" in desc: return ["south"]
    if "国子监" in desc: return ["west"]
    if "化生寺" in desc or "方丈" in desc or "大雄" in desc: return ["north"]
    if "书局" in desc or "钱庄" in desc: return ["south"]
    if "背阴" in desc or "民居" in desc or "粮" in desc or "小酒馆" in desc: return ["north"]
    if "杂货" in desc or "毛货" in desc or "鞋帽" in desc: return ["north"]
    if "御相" in desc: return ["east"]
    if "东门" in desc: return ["west"]
    return ["north"]  # fallback

# === KNOWN NPCs (not monsters) ===
KNOWN = ["Board","paizi","Agenta","Snoopl","Snoopy","Xiao er","Da ye",
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

def find_monster(desc, monster_name):
    for line in desc.split("\n"):
        line = line.strip()
        if "(" not in line or ")" not in line: continue
        if any(k in line for k in KNOWN): continue
        if monster_name and monster_name in line:
            m = re.search(r'\(([^)]+)\)', line)
            return m.group(1).strip() if m else None
    return None

# === LOCATION MATCHING ===
def yuan_area_matches_room(location, room_id, desc):
    """Check if yuan's target area matches current room area."""
    if not location: return False
    if "长安" in location and room_id in ["hub","kezhan","zhuque","qinglong","xuanwu","baihu","weaponshop","wuguan","dangpu","yuan"]: return True
    if "高老庄" in location and "gao" in room_id: return True
    if "开封" in location and room_id in ["kaifeng","chenlong","tieta","machang","shunwang","yaowang"]: return True
    if "普陀" in location and room_id in ["shanmen","shanlu","tingjing","putuo","island"]: return True
    if "望南" in location and "wangnan" in desc.lower(): return True
    return False

# === TRAVEL ROUTES FROM HUB ===
def get_travel_route(location):
    """Get the sequence of moves from hub to target area."""
    if not location: return []
    if "高老庄" in location: return ["south"]*13 + ["west"]*4
    if "开封" in location:
        if "尧" in location: return ["east"]*13 + ["northeast"]
        if "舜" in location or "御相" in location: return ["east"]*13 + ["northwest"]
        return ["east"]*13 + ["northeast"]  # default to yao
    if "普陀" in location: return ["south"]*16 + ["swim","north","north","northup","northup"]
    if "望南" in location: return ["east"]*3 + ["south"]
    if "长安城西" in location: return ["west"]*5
    # City — no travel needed, just search from hub
    return []

# === SEARCH PATTERNS ===
def get_search_pattern(location):
    """Get room-by-room search pattern for target area."""
    if not location: return []
    if "高老庄" in location:
        return ["east","east","east","east",  # lu→streets→gate
                "north","east","west",  # yard→pianfang→back
                "west","east",  # zhangfang→back
                "north","east","west",  # zhengting→fanting→back
                "west","east",  # pianting→back
                "north","east","west",  # houyuan→laundry→back
                "west","north","south","east",  # guige→yashi→back→houyuan
                "east","west",  # garden
                "south","south","south","south",  # back to gate
                "east","west",  # street east
                "west","south","north",  # street west→blacksmith
                "west","south","south",  # lu→field→lu
                "south","east","west",  # village→farmhouse
                "south",  # academy
                ]
    if "开封" in location and "尧" in location:
        return ["north","east","west","north","east","west","north","north",
                "east","west","south","south","south","south"]
    if "开封" in location:
        return ["north"]*4+["west","east"]+["south"]*4+["southeast"]+\
               ["northeast"]+["north"]*4+["south"]*4+["southwest"]+["northwest"]+\
               ["north"]*4+["south"]*4
    if "普陀" in location:
        return ["north"]*5+["east","west"]+["south"]*5+["west"]*2+["east"]*3+\
               ["south"]*3+["enter","out"]
    if "望南" in location:
        return ["southwest","south","west","southwest","northeast","east",
                "north","northeast","east","west"]
    # City search
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
# MAIN BOT LOOP
# ============================================
print("=== PERSISTENT GAME BOT ===")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
cmd(s, "gb"); cmd(s, "no"); cmd(s, "yxcdrg")
r = cmd(s, "198633", quiet=4.0)
if "y/n" in r: cmd(s, "y", quiet=4.0)
cmd(s, "set wimpy 15")

# State
state = "CHECK"
monster_name = None
monster_id = None
monster_location = None
travel_route = []
search_route = []
travel_idx = 0
search_idx = 0
tick = 0
max_ticks = 200
killed = False

while tick < max_ticks and not killed:
    tick += 1
    desc = cmd(s, "look")
    room = identify_room(desc)

    # Always check: is the monster RIGHT HERE?
    if monster_name:
        kid = find_monster(desc, monster_name)
        if kid:
            print(f"\n  !! MONSTER FOUND: {monster_name} (id: {kid}) at tick {tick}")
            # FIGHT!
            for tid in [kid, kid.split()[-1] if " " in kid else kid, "jing", "guai"]:
                r = cmd(s, f"kill {tid}")
                if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
                    print(f"  >> ENGAGED: kill {tid}")
                    state = "FIGHTING"
                    break

    if state == "FIGHTING":
        for j in range(50):
            time.sleep(3)
            b = drain(s, quiet=2.0, maxt=5.0)
            if b:
                r = clean(b)
                if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                    print(f"\n  ********************************************")
                    print(f"  ***    FIRST KILL!!!                     ***")
                    print(f"  ***    YUAN MISSION COMPLETE!!!          ***")
                    print(f"  ********************************************")
                    print(f"  {r[:200]}")
                    killed = True; break
                elif "承让" in r: print("  >> LOST"); state = "CHECK"; break
                elif "找机会逃跑" in r: print("  >> FLED"); state = "CHECK"; break
                elif "清醒" in r: print("  >> KO'd"); state = "CHECK"; break
                elif j % 5 == 0:
                    lines = [l for l in r.split("\n") if l.strip() and ">" not in l]
                    if lines: print(f"  [{j}] {lines[-1].strip()[:70]}")
        if state == "FIGHTING": state = "CHECK"  # combat timed out
        continue

    if state == "CHECK":
        # Check food
        hp_r = cmd(s, "hp")
        food_m = re.search(r"食物：\s*(\d+)", hp_r)
        food = int(food_m.group(1)) if food_m else 999
        score_r = cmd(s, "score")
        weapon_m = re.search(r"兵器伤害力：\[(\d+)\]", score_r)
        weapon = int(weapon_m.group(1)) if weapon_m else 0
        armor_m = re.search(r"盔甲保护力：\[(\d+)\]", score_r)
        armor = int(armor_m.group(1)) if armor_m else 0

        print(f"\n  [tick {tick}] room={room} food={food} wpn={weapon} arm={armor} state→", end="")

        if food < 50:
            print("NEED_FOOD")
            state = "GOTO_HUB"; next_dest = "kezhan"
        elif weapon == 0:
            print("NEED_GEAR")
            state = "GOTO_HUB"; next_dest = "weaponshop"
        elif armor < 10:
            print("NEED_SHIELD")
            state = "GOTO_HUB"; next_dest = "weaponshop"
        elif monster_name is None:
            print("NEED_MISSION")
            state = "GOTO_HUB"; next_dest = "yuan"
        else:
            print("READY_TO_HUNT")
            # Check if already in target area
            if yuan_area_matches_room(monster_location, room, desc):
                state = "SEARCHING"
                search_route = get_search_pattern(monster_location)
                search_idx = 0
            else:
                state = "GOTO_HUB"; next_dest = "travel"
        continue

    if state == "GOTO_HUB":
        if room == "hub":
            print(f"  [tick {tick}] AT HUB → ", end="")
            if next_dest == "kezhan":
                state = "GOTO_KEZHAN"
            elif next_dest == "weaponshop":
                state = "GOTO_SHOP"
            elif next_dest == "yuan":
                state = "GOTO_YUAN"
            elif next_dest == "travel":
                state = "TRAVELING"
                travel_route = get_travel_route(monster_location)
                travel_idx = 0
            print(state)
        else:
            dirs = step_toward_hub(room, desc)
            for d in dirs:
                cmd(s, d)
            # Don't print every step — just every 5th tick
            if tick % 5 == 0: print(f"  [tick {tick}] navigating to hub from {room}...")
        continue

    if state == "GOTO_KEZHAN":
        cmd(s, "south"); cmd(s, "east")
        desc2 = cmd(s, "look")
        if "南城客栈" in desc2:
            for _ in range(3): cmd(s, "buy jitui from xiao er", quiet=0.8)
            cmd(s, "buy jiudai from xiao er", quiet=0.8)
            for _ in range(3): cmd(s, "eat jitui", quiet=0.5)
            cmd(s, "drink jiudai", quiet=0.5)
            print(f"  [tick {tick}] FED!")
            cmd(s, "west"); cmd(s, "north")  # back to hub
        state = "CHECK"
        continue

    if state == "GOTO_SHOP":
        cmd(s, "east"); cmd(s, "south")
        desc2 = cmd(s, "look")
        if "兵器铺" in desc2:
            cmd(s, "buy blade from xiao xiao")
            cmd(s, "wield blade")
            cmd(s, "buy shield from xiao xiao")
            cmd(s, "wear shield")
            print(f"  [tick {tick}] GEARED!")
            cmd(s, "north"); cmd(s, "west")  # back to hub
        state = "CHECK"
        continue

    if state == "GOTO_YUAN":
        cmd(s, "north"); cmd(s, "west")
        desc2 = cmd(s, "look")
        if "天监台" in desc2:
            r = cmd(s, "ask yuan about kill", quiet=3.0)
            print(f"\n  [tick {tick}] YUAN: {r[:150]}")
            m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', r)
            if m:
                monster_name = m.group(1)
                monster_id = m.group(2).strip()
                monster_location = m.group(3)
                print(f"  >> NEW MISSION: {monster_name} @ {monster_location}")
            elif "除尽" in r:
                r2 = cmd(s, "ask yuan about kill", quiet=3.0)
                m = re.search(r'近有(.+?)\((\w[^)]*)\)在(.+?)出没', r2)
                if m:
                    monster_name = m.group(1); monster_id = m.group(2).strip(); monster_location = m.group(3)
                    print(f"  >> NEW MISSION: {monster_name} @ {monster_location}")
            elif "收服" in r:
                m2 = re.search(r'收服(.+?)吗', r)
                if m2:
                    monster_name = m2.group(1); monster_id = "guai"
                    print(f"  >> OLD MISSION: {monster_name}")
            cmd(s, "east"); cmd(s, "south")  # back to hub
        state = "CHECK"
        continue

    if state == "TRAVELING":
        if travel_idx >= len(travel_route):
            print(f"  [tick {tick}] ARRIVED at target area!")
            state = "SEARCHING"
            search_route = get_search_pattern(monster_location)
            search_idx = 0
        else:
            d = travel_route[travel_idx]
            cmd(s, d)
            travel_idx += 1
            if travel_idx % 5 == 0:
                print(f"  [tick {tick}] traveling... step {travel_idx}/{len(travel_route)}")
        continue

    if state == "SEARCHING":
        if search_idx >= len(search_route):
            print(f"  [tick {tick}] Search complete — monster not found")
            monster_name = None  # get new mission
            state = "CHECK"
        else:
            d = search_route[search_idx]
            cmd(s, d)
            search_idx += 1
            if search_idx % 5 == 0:
                print(f"  [tick {tick}] searching... room {search_idx}/{len(search_route)}")
        continue

# === DONE ===
print(f"\n=== BOT ENDED after {tick} ticks ===")
if killed:
    print("*** MISSION ACCOMPLISHED! ***")
    # Report to yuan
    for _ in range(30):
        desc = cmd(s, "look")
        if "十字街头" in desc: break
        room = identify_room(desc)
        dirs = step_toward_hub(room, desc)
        for d in dirs: cmd(s, d)
    cmd(s, "north"); cmd(s, "west")
    r = cmd(s, "ask yuan about kill", quiet=3.0)
    print(f"  YUAN: {r[:200]}")

r = cmd(s, "hp"); print(f"\n  HP: {r[:100]}")
r = cmd(s, "score"); print(f"  SCORE: {r[:200]}")
print("\n*** NO QUIT ***")
time.sleep(1); s.close()
