"""
Dragon Palace Join Bot
1. Get 避水咒 from 袁守诚 (yuan shoucheng) at 袁氏草堂
2. Navigate to 东海之滨 (east seashore) and dive
3. Navigate to 龙女 in 绣房 (girl3) and 拜师
4. Grab optional free loot
"""
import socket, time, re, sys, os
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8")

LOG = os.path.join(os.environ.get("TEMP","C:/Users/ying/AppData/Local/Temp"), "dragon.log")

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
    t=clean(b); print(f"\n--- {label} ---"); print(t[-1800:] if len(t)>1800 else t)
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
    cn2en={"东":"east","南":"south","西":"west","北":"north",
           "东北":"northeast","东南":"southeast","西北":"northwest","西南":"southwest",
           "上":"up","下":"down"}
    exits=set()
    for en in ["northeast","northwest","southeast","southwest","north","south",
               "east","west","up","down","eastup","westdown","northup","southdown","enter","out"]:
        if en in desc.lower(): exits.add(en)
    return exits

REVERSE={"east":"west","west":"east","north":"south","south":"north",
         "northeast":"southwest","southwest":"northeast",
         "northwest":"southeast","southeast":"northwest",
         "up":"down","down":"up","eastup":"westdown","westdown":"eastup"}

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
           ("碑林","beilin"),("货行","huohang"),("小雁塔","xiaoyanta"),
           # Dragon Palace
           ("海底","haidi"),("龙宫大门","longmen"),("广场","guangchang"),
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
    if "朱雀大街" in desc or "杂货铺" in desc:
        m(s,"east"); return
    if "粮店" in desc:
        m(s,"southeast"); return
    if "帮会" in desc:
        m(s,"south"); return
    ex=get_exits(desc)
    if "west" in ex and "south" in ex:
        m(s,"east"); return
    m(s,"north")

def goto_hub(s, max_steps=50):
    last_dir=None; bug_streak=0
    for step in range(max_steps):
        desc,_=look(s); rid=roomid(desc)
        if "系统" in desc and ("BUG" in desc.upper() or "ＢＵＧ" in desc):
            bug_streak+=1
            print(f"  !! server desync streak={bug_streak}")
            if bug_streak>=3: time.sleep(5); drain(s,quiet=1.0,maxt=3.0); bug_streak=0
            else: time.sleep(1.5)
            continue
        bug_streak=0
        if rid=="hub": return True
        if rid=="beiyin": beiyin_escape(s,desc); continue
        nav={"kezhan":["west","north"],"zhuque":["north"],"qinglong":["west"],
             "xuanwu":["south"],"baihu":["east"],"yuan_room":["east","south"],
             "shop":["north","west"],"wuguan":["south","west"],"dangpu":["east","north"],
             "nancheng":["north","north","north","north"],
             "daguandao":["west" if ("平原" in desc or "由东西" in desc or "长安以东" in desc) else "north"],
             "zhongnan":["north"],"nanyue":["north"],"jingshui":["north"],
             "seashore":["north"],"eastsea":["west","north"],"seashore_e":["west"],
             "haidi":["up"],"longmen":["west"],"guangchang":["west"],
             "ziyungong":["northwest"],"huayuan":["northwest"],"xiufang":["west","northwest"],
             "taizi1":["southwest"],"taizi2":["southwest"],"taizi4":["south"],
             "yujie":["westdown"],
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
             "xiemao":["north"],"caotang":["south","east","east","east"],
             "ximen":["east"],"sanhua_mishi":["east"],"sanhua":["east"],"zahuopu":["east"],
             "erlouya":["down"],"gonggao":["west"],
             "wangnan":["north"],"huohang":["west"],"dayanta":["west"],"cien":["west"],
             "guandao":["northwest"],"jinshi":["northwest"],"qujiang":["north"],
             "beilin":["west"],"xiaoyanta":["north"]}
        if rid=="unknown":
            if step%4==0: print(f"  nav {step}: UNKNOWN [{firstline(desc)[:30]}]")
            ex=get_exits(desc); avoid=REVERSE.get(last_dir)
            moved=False
            for d in ["west","north","northwest","south","east","northeast","southwest","southeast","up","down","out"]:
                if d in ex and d!=avoid:
                    m(s,d); last_dir=d; moved=True; break
            if not moved:
                for d in ["west","north","east","south","up","down"]:
                    if d in ex: m(s,d); last_dir=d; moved=True; break
            if not moved: m(s,"look")
            continue
        dirs=nav.get(rid,["north"])
        for d in dirs: m(s,d)
        last_dir=dirs[-1] if dirs else None
        if step%10==9: print(f"  nav {step}: {rid}")
    return False

# ============================================================
print("=== DRAGON PALACE JOIN BOT ===")
with open(LOG,"w",encoding="utf-8") as f: f.write("=== DRAGON LOG ===\n")

s=socket.create_connection(("146.190.143.182",6666),timeout=15)
drain(s,quiet=3.0,maxt=12.0)
m(s,"gb"); m(s,"no"); m(s,"yxcdrg")
r=clean(send(s,b"198633\r\n",quiet=4.0))
if "y/n" in r: m(s,"y",q=4.0)
m(s,"set wimpy 5")
time.sleep(1)

print("\n[SETUP] checking state...")
goto_hub(s)
hp_r=m(s,"hp",q=2.0)
inv_r=m(s,"i",q=2.0)

# Check if already Dragon Palace member
sc_r=m(s,"score",q=2.5)
is_member = "东海龙宫" in sc_r or "水族" in sc_r or "龙宫" in sc_r
print(f"  Dragon Palace member: {is_member}")

# Check for 避水咒
have_bishui = "避水咒" in inv_r or "bishui" in inv_r.lower()
print(f"  Have 避水咒: {have_bishui}")

if is_member:
    print("  Already a Dragon Palace member! Just grabbing loot and logging off.")
else:
    # === STEP 1: Get 避水咒 ===
    if not have_bishui:
        # Check if have jiudai
        have_jiudai = "酒袋" in inv_r
        print(f"  Have jiudai: {have_jiudai}")

        if not have_jiudai:
            # Buy jiudai at kezhan
            print("\n[JIUDAI] buying at inn...")
            goto_hub(s)
            m(s,"south"); m(s,"east")  # kezhan
            d,_=look(s)
            if "南城客栈" in d:
                r_buy=m(s,"buy jiudai from xiao er",q=1.5)
                print(f"  Buy result: {r_buy[:80]}")
            else:
                print(f"  !! Not at kezhan: {firstline(d)}")
            m(s,"west"); m(s,"north")  # back to hub

        # Navigate to 袁守诚 at 袁氏草堂
        print("\n[YUAN SHOUCHENG] navigating to caotang...")
        goto_hub(s)
        # hub → west×3 → north → caotang
        for d in ["west","west","west","north"]:
            m(s,d)
        d,_=look(s)
        print(f"  Arrived at: {firstline(d)}")

        if "袁氏草堂" in d or "caotang" in roomid(d):
            r_give=m(s,"give jiudai to yuan shoucheng",q=3.0)
            print(f"  Give result: {r_give[:100]}")
            time.sleep(1)
            # tear the book
            r_tear=m(s,"tear shu",q=2.0)
            print(f"  Tear result: {r_tear[:120]}")
            time.sleep(0.5)
            # verify by inventory and tear result
            have_bishui = "小纸片" in r_tear or "避水咒" in r_tear
            if not have_bishui:
                inv2=m(s,"i",q=1.5)
                have_bishui = "避水咒" in inv2 or "小纸片" in inv2
            print(f"  Have 避水咒: {have_bishui}")
        else:
            print(f"  !! Wrong room: {firstline(d)}, aborting")
            print("*** NO QUIT ***"); s.close(); sys.exit(1)

        if not have_bishui:
            print("  !! Could not get 避水咒, aborting")
            print("*** NO QUIT ***"); s.close(); sys.exit(1)

    # === STEP 2: Navigate to east seashore ===
    print("\n[EASTSEASHORE] navigating south then east...")
    goto_hub(s)

    # South through city: hub → 朱雀 ×4 → 南城口 → bridges ×3 → broadway ×5 → 南海之滨
    SOUTH_ROUTE = ["south"]*16  # hub to 南海之滨
    EAST_ROUTE  = ["east"]*3    # 南海之滨 to 东海之滨

    for d in SOUTH_ROUTE:
        m(s,d,q=0.5)
        time.sleep(0.1)

    d,_=look(s)
    print(f"  After south route: {firstline(d)}")
    if "南海之滨" not in d:
        # We might be in a different spot — try looking and correcting
        print(f"  !! Expected 南海之滨, got: {firstline(d)}")
        # Try to continue south a few more times
        for _ in range(6):
            if "南海之滨" in firstline(d): break
            m(s,"south",q=0.5); time.sleep(0.3)
            d,_=look(s)

    # Go east to east seashore
    for d in EAST_ROUTE:
        m(s,d,q=0.5); time.sleep(0.2)

    d,_=look(s)
    print(f"  At: {firstline(d)}")
    if "东海之滨" not in d:
        print(f"  !! Not at east seashore: {firstline(d)}")
        print("*** NO QUIT ***"); s.close(); sys.exit(1)

    # === STEP 3: Dive ===
    print("\n[DIVE] diving into Dragon Palace...")
    r_dive=m(s,"dive",q=3.0)
    print(f"  Dive result: {r_dive[:150]}")
    time.sleep(1)

    d,_=look(s)
    if "海底" not in d and "龙宫" not in d and "under" not in roomid(d):
        print(f"  !! Dive failed: {firstline(d)}")
        print(f"  Full desc: {r_dive[:300]}")
        print("*** NO QUIT ***"); s.close(); sys.exit(1)
    print(f"  Underwater! {firstline(d)}")

    # === STEP 4: Navigate to 龙女 (girl3 = 绣房) ===
    # under1 → e → under2 → e → under3 → ne → under4 → e → gate → e → inside1 → se → girl1 → se → girl2 → e → girl3
    print("\n[NAVIGATE] going to 绣房 (龙女's room)...")
    PATH_TO_LONGNU = ["east","east","northeast","east","east","southeast","southeast","east"]
    for mv in PATH_TO_LONGNU:
        r_mv=m(s,mv,q=1.5); time.sleep(0.3)
        d,_=look(s)
        print(f"  {mv} → {firstline(d)[:30]}")

    d,_=look(s)
    rid=roomid(d)
    print(f"  Arrived: {firstline(d)} [roomid={rid}]")

    if "绣房" in d or "龙女" in d or rid=="xiufang":
        print("\n[BAITISHI] 拜龙女为师...")
        r_bai=m(s,"apprentice long nu",q=5.0)
        print(f"  Result: {r_bai[:300]}")
        time.sleep(1)
        # Check success
        if any(w in r_bai for w in ["师父","恭喜","弟子","拜师","龙宫"]):
            print("\n  ************************************")
            print("  ***  JOINED DRAGON PALACE!!!   ***")
            print("  ************************************")
        else:
            print("  !! 拜师 result unclear, checking score...")
            sc2=m(s,"score",q=3.0)
            if "东海龙宫" in sc2 or "水族" in sc2:
                print("  *** CONFIRMED: Dragon Palace member! ***")
            else:
                print(f"  !! Score: {sc2[:200]}")
    else:
        print(f"  !! Wrong room for 龙女: {firstline(d)}")
        print(f"  Full desc: {d[:300]}")

# === STEP 5: Optional free loot ===
# After joining, get free loot from the palace
# Members can access the loot areas
print("\n[LOOT] checking for free equipment...")
d,_=look(s)
rid=roomid(d)
inv_after=m(s,"i",q=2.0)
print(f"  Current inventory: {inv_after[:200]}")

# Final status
print("\n=== FINAL STATUS ===")
show("HP", send(s,b"hp\r\n",quiet=2.0))
show("SCORE", send(s,b"score\r\n",quiet=3.0))
print("\n*** NO QUIT ***")
time.sleep(1); s.close()
