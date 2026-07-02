# Game World Map — Verified Routes from Source Code

## Chang'an City (长安城)

### Core Grid (source: d/city/*.c)
```
                     朝阳门(皇宫) /d/huanggong/chaoyangmen
                         |north
天监台(tianjiantai)--玄武大街(xuanwu-n1)--国子监(guozijian)
  [YUAN TIANGANG]        |south
                    十字街头(center)  ← THIS IS THE HUB
              west/ |south  \east
    白虎大街(baihu-w1)  朱雀大街(zhuque-s1)  青龙大街(qinglong-e1)
        |west            |south              |east      |north
    白虎(baihu-w2)   朱雀(zhuque-s2)     青龙(qinglong-e2) 武馆(wuguan)
        |west        乐坊|     |药铺     |east     |south
    白虎(baihu-w3)   朱雀(zhuque-s3)     青龙(qinglong-e3) 兵器铺(bingqipu)
        |south       毛货|     |鞋帽     |east     
    背阴巷1(beiyin1) 朱雀(zhuque-s4)     东门(dongmen)→开封
                     |south              
                   南城口(nanchengkou)    
                     |south
                   泾水桥北
```

### Key Verified Paths from 十字街头 (center/shizikou):

| Destination | Path | Moves |
|-------------|------|-------|
| **南城客栈 (kezhan)** | south → east | `south east` |
| **天监台 (yuan)** | north → west | `north west` |
| **袁氏草堂 (Yuan Shoucheng)** | west x3 → north | `west west west north` |
| **武馆 (wuguan)** | east → north | `east north` |
| **兵器铺 (weaponshop)** | east → south | `east south` (bingqipu) |
| **国子监 (guozijian)** | north → east | `north east` |
| **当铺 (dangpu)** | south → west | `south west` |
| **东门 (to Kaifeng)** | east → east → east → east | `east east east east` |

### Return to 十字街头 from:

| From | Path |
|------|------|
| **kezhan** | west → north |
| **天监台** | east → south |
| **武馆** | south → west |
| **兵器铺** | north → west |
| **当铺** | east → north |
| **东门** | west → west → west → west |

---

## Route: Chang'an → Kaifeng (开封城)

### Verified from source code (d/kaifeng/*.c):
```
东门(dongmen) --east→ east1 --east→ east2 --east→ east3 --east→ east4
  --east→ east5 --east→ 开封城门(chengmen) --east→ 辰龙道(chen1)
  --east→ 辰龙道(chen2) --east→ 汴京铁塔(tieta)
  --northwest→ 舜王街(shun5) --north→ shun4 --north→ shun3
  --north→ shun2 --west→ 御相府(yuxiang)
```

### Full path from 十字街头 to 御相府:
```
east east east east    (shizikou → dongmen, 4 moves)
east                   (dongmen → east1, enters kaifeng road)
east east east east    (east1 → east5, 4 moves)
east                   (east5 → chengmen, kaifeng gate)
east east east         (chengmen → chen1 → chen2 → tieta, 3 moves)
northwest              (tieta → shun5)
north north north      (shun5 → shun2, 3 moves)
west                   (shun2 → yuxiang 御相府)
```
**Total: 19 moves from shizikou to 御相府**

### Return from 御相府 to 十字街头:
```
east                   (yuxiang → shun2)
south south south      (shun2 → shun5)
southeast              (shun5 → tieta)
west west west         (tieta → chengmen)
west                   (chengmen → east5)
west west west west    (east5 → east1)
west                   (east1 → dongmen)
west west west west    (dongmen → shizikou)
```
**Total: 19 moves back**

---

## Kaifeng City (开封城) Internal Map
```
         shun1(top)
           |north
   杨记钱庄-shun2-御相府(yuxiang) ← YUAN MISSION TARGET AREA
           |north
         shun3
           |north
         shun4
           |north
         shun5--古亭道(guting)--尧王(yao)streets
           |southeast                    |
         汴京铁塔(tieta)              天蓬府 area
           |west
         辰龙道(chen2)
           |west
         辰龙道(chen1)
           |west
         开封城门(chengmen)
           |west x5
         东门(dongmen) → back to 长安
```

---

## Route: Chang'an → Westway (长安城西)
```
十字街头 --west→ 白虎w1 --west→ 白虎w2 --west→ 白虎w3 --west→ 西门(ximen)
  --west→ west1(d/westway) --west→ west2 ...
```
**4 west from shizikou to 西门, then west to enter /d/westway**

## Route: Chang'an → 普陀山 (Swimming Route!)
**Verified from source: d/changan/*.c + d/nanhai/*.c**
```
十字街头 → south x4 → 南城口(nanchengkou)
→ south → 泾水桥北(nbridge) → south → 泾水桥(bridge) → south → 泾水桥南(sbridge)
→ south → 大官道(broadway1) → south → 终南山(zhongnan) → south → 大官道(broadway2)
→ south → 南岳(nanyue) → south → 大官道(broadway3) → south → 大官道(broadway4)
→ south → 大官道(broadway5) → south → 南海之滨(southseashore)
→ **swim** → 小岛(island, /d/nanhai)
→ north → 听经石(tingjing) → north → 山路(shanglu2)
→ northup → 山路(shanglu) → northup → 山门(gate)
```
**~16 souths from shizikou + swim + 4 north/northups = ~21 moves total**
**Cost: 20 kee + 20 sen from swimming**

## Route: Chang'an → 龙宫 (Dragon Palace)

### Verified from source: d/changan/*.c + d/sea/*.c

**Step 1: Walk south (same as 普陀山 route)**
```
十字街头 → south x13 → 南海之滨(southseashore)
```
(Same 13 souths as going to 普陀山 — 南城口→bridge→sbridge→broadway1→zhongnan→broadway2→nanyue→broadway3→broadway4→broadway5→southseashore)

**Step 2: Go east to 东海之滨**
```
southseashore → east(seashore1) → east(seashore2) → east(eastseashore)
```

**Step 3: Dive underwater**
```
eastseashore → dive → under1 → east → under2 → east → under3 → northeast → under4 → east → 龙宫大门(gate)
```

**⚠️ REQUIREMENT:** Need `毕水咒` (bishui zhou) spell OR Dragon Palace family membership to `dive` without drowning. New players cannot dive yet.

**Alternative from southseashore:** `swim` → 小岛(island) → north → 普陀山 (same as before)

**Total from shizikou:** south x13 + east x3 + dive + east + east + northeast + east = ~21 moves

## 普陀山 (Mount Putuo) Internal Layout (from source)
```
山门(gate) --north--> 小院(xiaoyuan) --north--> 落迦岩(guangchang)
  gate also: southdown→上陆(shanglu, exit toward island)
  xiaoyuan: west→走廊(zoulang, has bear NPC), east→zoulang2, south→gate
  guangchang: west→road11, east→road1, enter→潮音洞(chaoyindong), south→xiaoyuan
  road1 → northdown → road2 → north → zhulin0 (紫竹林 entry)
```
**紫竹林 (zhulin1-17)** = maze with MOSTLY RANDOM exits. Fixed anchors:
- zhulin10 = hub: south→zhulin7, west→zhulin9, east→zhulin11, north→zhulin15
- zhulin15 = hub: west→zhulin16, east→zhulin17, north→池塘边(pool)
- zhulin16/17 → enter → 罗汉(luohan) area
**Search strategy:** wander randomly — both monster and player random-walk, collision eventually.

## Reachable Areas from Chang'an (by walking):
| Area | Reachable? | Route from shizikou |
|------|-----------|---------------------|
| /d/city | YES | Already here |
| /d/eastway | YES | east x3 → south (wangnan) |
| /d/kaifeng | YES | east x4 → east x9 → nw → n x3 → w |
| /d/westway | YES | west x5 (through ximen) |
| /d/gao | YES | west x5 → then via /d/changan/wroad3 |
| /d/lingtai | ? | Need to check |
| /d/moon | NO | Requires fly |
| /d/sea | YES (with 避水咒 scroll) | south x13 → east x3 → `dive` → east x2 → northeast → east |
| /d/nanhai | NO | Requires fly putuo |
| /d/ourhome/honglou | NO | Requires sleep/dream |

## Monster Spawn Areas (from yaoguai.c dirs1):
These are the areas yuan can assign monsters to:
- /d/city — 长安城内
- /d/westway — 长安城西
- /d/kaifeng — 开封城
- /d/lingtai — 方寸山
- /d/moon — 月宫
- /d/gao — 高老庄
- /d/sea — 龙宫
- /d/nanhai — 普陀山
- /d/eastway — 长安城东(望南街)
- /d/ourhome/honglou — 红楼一梦(dream world via sleep)
