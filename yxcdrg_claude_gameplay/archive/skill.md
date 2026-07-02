# YXJ2000 Gameplay Knowledge Base

## ARCHITECTURE: Persistent Game Bot

### Problem with one-shot scripts:
- Each script connects, does everything, disconnects — losing weapon/state
- Can't adapt to unexpected locations or situations
- Tries to handle ALL scenarios in one run, fails on edge cases

### Solution: Persistent loop with state machine
```
Connect → Login → LOOP {
  1. look → parse current room
  2. Decide action based on STATE + ROOM
  3. Execute ONE action
  4. Read response → update STATE
  5. Repeat
}
```

### States:
- `NEED_FOOD` — food < 50, go buy food at kezhan
- `NEED_GEAR` — weapon 0 or armor < 2, go buy at weaponshop  
- `NEED_MISSION` — no active mission, go to yuan
- `TRAVELING` — moving toward target area
- `SEARCHING` — in target area, looking for monster room by room
- `FIGHTING` — engaged in combat, wait for result
- `RETURNING` — going back to yuan to report kill

### Room identification:
Use keywords from `look` output to identify current room. Don't parse room names — just check if keywords exist in full description.

### Navigation:
Instead of hardcoded paths, use a STEP-BY-STEP approach:
1. `look` → identify where I am
2. Consult route table → what's the NEXT direction to go
3. Move ONE step
4. `look` → verify I moved correctly
5. Repeat until at destination

---

## ROUTES (verified from source code)

### City landmarks → keyword to detect:
| Room | Keyword | File |
|------|---------|------|
| 十字街头 | "十字街头" | center.c |
| 南城客栈 | "南城客栈" | kezhan.c |
| 天监台 | "天监台" | tianjiantai.c |
| 兵器铺 | "兵器铺" | bingqipu.c |
| 朱雀大街 | "朱雀大街" | zhuque-s1..s4 |
| 青龙大街 | "青龙大街" | qinglong-e1..e3 |
| 玄武大街 | "玄武大街" | xuanwu-n1.c |
| 白虎大街 | "白虎大街" | baihu-w1..w3 |
| 武馆 | "长安武馆" | wuguan.c |
| 当铺 | "董记当铺" | dangpu.c |

### Route table: "from → to → direction"
All routes go through 十字街头 (hub). Two-phase: get to hub, then go to destination.

**Phase 1: Get to hub (十字街头)**

| If `look` contains | Go | Notes |
|----|---|---|
| 十字街头 | DONE | Already there |
| 南城客栈 | west, north | |
| 朱雀大街 + 客栈 | north | s1 level |
| 朱雀大街 (no 客栈) | north | May need multiple |
| 白虎大街 | east | May need multiple |
| 青龙大街 | west | |
| 玄武大街 | south | |
| 天监台 | east, south | |
| 兵器铺 | north, west | |
| 武馆 | south, west | |
| 当铺 | east, north | |
| 南城口 | north x4 | 4 norths! |
| 大官道/终南/南岳/泾水 | north | Keep going |
| 土路 (高老庄) | east | Keep going until 青石路, then east more |
| 街道 (高老庄) | east | |
| 高家 | south, east | Get to street first |
| 开封/辰龙/汴京 | west | Keep going |
| 舜王/尧王 | south then west | |
| 铁塔 | west | |
| 马场 | north then west | machang → chen2 |
| 山门/山路 | south/southdown | Try both |
| 听经/小岛 | south | |
| 南海之滨 | north | Keep going (16 times) |

**Phase 2: Hub to destination**

| Destination | From hub | Moves |
|-------------|----------|-------|
| 客栈 (food) | south, east | 2 |
| 兵器铺 (gear) | east, south | 2 |
| 天监台 (yuan) | north, west | 2 |
| 武馆 (learn) | east, north | 2 |
| 高老庄 | south x13, west x4 | 17 |
| 开封 | east x13 | 13 (+northeast for yao, +northwest for shun) |
| 望南街 | east x3, south | 4 |
| 普陀山 | south x16, swim, north, north, northup, northup | 21 |

---

## YUAN MISSION SYSTEM

### Flow:
1. `ask yuan about kill` → spawns monster, tells location
2. Monster lives 30 minutes (`time() + 1800`)
3. After killing: `ask yuan about kill` → yuan says "除尽" (cleared), then gives new mission
4. If failed (30 min): yuan gives new mission on next ask

### Response parsing:
| Yuan says | Meaning |
|-----------|---------|
| "近有XXX(Yyy)在ZZZ出没" | NEW mission — monster just spawned |
| "不是请您去收服XXX吗" | OLD mission still active — monster still alive |
| "妖魔已经除尽了" | Previous mission COMPLETE — ask again for new |

### Monster IDs:
- Set as: `({id+" jing", "jing"})` or `({id+" guai", "guai"})`
- **Kill with: `kill jing` or `kill guai`** — NOT the first word!
- Monster has `random_move` — wanders between rooms

### Location mapping (yuan response → area):
Yuan names a SUB-LOCATION in parens, e.g. "长安城（粮仓一带）". Match the OUTER area name.
| Yuan says (outer) | Area code | Reachable | Route |
|-----------|-----------|-----------|-------|
| 长安城 | /d/city | YES | search city from hub |
| 望南街 / (in 长安城) | /d/eastway | YES | east x3, south |
| 开封城 | /d/kaifeng | YES | east x13 |
| 高老庄 | /d/gao | YES | south x13, west x4 |
| 普陀山 | /d/nanhai | YES | south x16, swim |
| 长安城西 | /d/westway | YES | west x5 |
| 龙宫 / 绣房 / 海底 | /d/sea | YES (with 避水咒) | south x13, east x3, dive |
| 方寸山 | /d/lingtai | Unknown route | TBD |
| 月宫 / 湖底 | /d/moon | NO | need fly |
| 红楼一梦 / 稻香村 | /d/ourhome/honglou | NO | need sleep/dream |

### Sub-location → area decoder (from observed missions):
| Sub-location (in parens) | Actual area | File |
|--------------------------|-------------|------|
| 粮仓一带 | 长安城 beiyin | city/liangdian.c (beiyin4 → east) |
| 望南街一带 | 长安城 eastway | eastway/wangnan*.c |
| 偏房一带 | 高老庄 | gao compound |
| 大官道一带 | 开封城 | kaifeng east streets |
| 西湖路一带 / 东湖路 | 开封城 | kaifeng west/east lake |
| 御相府一带 | 开封城 舜王街 | kaifeng shun2 west |
| 尧王街一带 | 开封城 | kaifeng yao streets |
| 烽火台一带 | 长安城西 | westway |
| 酒泉郊外 | 长安城西 | westway |
| 山路一带 | 普陀山 | nanhai |
| 绣房 / 海底 | 龙宫 | sea/girl3.c — NEED 避水咒 |
| 湖底 | 月宫 | moon/hudi.c — NEED fly |
| 稻香村 | 红楼一梦 | dream world — NEED sleep |

### Area-specific search patterns:
**高老庄 (from map-gao):**
```
Enter from east: 土路→土路→街道→街道→高家大门
Compound: 大门→north→正院→east→偏房, west→帐房
          正院→north→正厅→east→饭厅, west→偏厅
          正厅→north→后院→east→洗衣房, west→闺阁
          后院→north→花园, 闺阁→north→雅室
Streets: south of 大门→小酒馆/铁铺
         west of streets→稻田→土路→村口→农舍/书堂
```

**开封 尧王街 (from source):**
- tieta → **northeast** → yao5 → north x4 → yao1
- Side rooms: qili(yao5→east), lanting(yao4→east), dangpu(yao3→east), tianpeng(yao1→east)

**开封 舜王街 (from source):**
- tieta → **northwest** → shun5 → north x4 → shun1
- 御相府: shun2→west

---

## COMBAT

### Equipment:
| Item | Stat | Cost | Buy command |
|------|------|------|-------------|
| 钢刀 | 25 damage | 5两 | buy blade from xiao xiao |
| 牛皮盾 | 15 armor | 10两 | buy shield from xiao xiao |
| Total | 25 dmg + 16 armor | 15两 | |

### Kill commands (order of try):
1. `kill jing` (for 精 monsters)
2. `kill guai` (for 怪 monsters)
3. `kill <full id>` e.g. `kill baimao jing`

### Victory detection:
Any of: 死了, 服了, 投降, 青烟, 原形, 领罪, 走开, 大赦

### Settings:
- `set wimpy 15` — auto-flee at 15% HP

---

## FOOD — SPAM TO FULL!

**Buy lots, eat/drink until MAXED. Money is plentiful. Don't conserve.**

| Item | Command | Cost |
|------|---------|------|
| 炸鸡腿 | buy jitui from xiao er | 80文 |
| 红烧狗肉 | buy gourou from xiao er | 1两 (more food) |
| 桂花酒袋 | buy jiudai from xiao er | 1两 |

Buy at 南城客栈. Buy 5-10x food + 5x drink. Eat/drink repeatedly until bars are full.
Threshold: if food OR water < 100, go buy and spam eat/drink.

---

## CRITICAL GAME MECHANICS

### Monster scaling:
- Monster's skills = YOUR **highest** skill × level_factor
- **Level all skills EVENLY** — if unarmed is 10 but dodge is 3, monster gets skill 8 but you can only dodge at 3
- Don't let any one skill get ahead of others

### Weapon importance:
- **Early game: weapon is EVERYTHING** — damage 0 vs damage 25 is the difference between losing and winning
- Later when skills are high, weapon still matters but less dominant
- Always have a weapon equipped before fighting

### Long-term plan: Dragon Palace (龙宫)
**Verified route (from source code):**
```
shizikou → south x13 → 南海之滨(southseashore)
→ east(seashore1) → east(seashore2) → east(eastseashore)
→ dive → under1 → east → under2 → east → under3 → northeast → under4 → east → 龙宫大门(gate)
```

**⚠️ Blocker to dive:** Need ONE of:
- **避水咒 (bishui zhou) scroll** in inventory (paper item)  
- **OR** be in "龙宫" or "东海龙宫" family already

**How to get 避水咒 (FOUND FROM SOURCE CODE):**

**The 避水咒 is hidden inside 〖无字天书〗 (Book of No Words)!**
- `tear nowords` → reveals 避水咒 scroll from the back page
- The 无字天书 ALSO teaches `spells` skill (useful for Dragon Palace!)

**How to get 无字天书 (the book RESPAWNS — repeatable!):**
1. `buy jiudai from xiao er` at 南城客栈 (costs only 1两!)
2. Go to 袁氏草堂 (caotang): shizikou → west x3 → north
3. `give jiudai to yuan` → 袁守诚 (Yuan Shoucheng) gives you 〖无字天书〗
4. `study nowords` FIRST → trains spells skill (max 40), needs daoxing>=50
5. `tear nowords` → 避水咒 scroll appears from back page
6. **Repeat anytime** —袁守诚 respawns the book each time you give him a 桂花酒袋

**Complete 龙宫 entry sequence:**
```
buy jiudai from xiao er (kezhan)
→ west x3 → north (caotang, find yuan shoucheng)
→ give jiudai to yuan → get nowords book
→ study nowords (optional, for spells skill)
→ tear nowords → get bishui zhou scroll
→ back to hub → south x13 → east x3 (eastseashore)
→ dive → under1 → east → under2 → east → under3 → northeast → under4 → east → 龙宫大门
```

**Once inside 龙宫 (d/sea/gate.c):** Find 敖广 (Dragon King) / 龙宫掌门 to 拜师. Learn the PvP build:
- dragonfight (enables sheshen 3-hit burst)
- dragonforce (zhenshen buff, shield, roar)
- fengbo-cha (CC stun skill)
- seashentong (freeze spell)
- huntian-hammer (equipment destruction)

---

## KEY NPCs (verified from source)

| NPC | Location | Path | Use |
|-----|----------|------|-----|
| 袁天罡 (Yuan Tiangang) | 天监台 | hub→north→west | `ask yuan about kill` for missions |
| 袁守诚 (Yuan Shoucheng) | 袁氏草堂 | hub→west x3→north | `give jiudai` → 无字天书 (→避水咒) |
| 范芦平 (Fan Luping) | 长安武馆 | hub→east→north | learn unarmed/dodge/parry/force |
| 萧萧 (Xiao xiao) | 兵器铺 | hub→east→south | buy weapons + 牛皮盾 |
| 店小二 (Xiao er) | 南城客栈 | hub→south→east | buy jitui/gourou/jiudai |
| 萧萧/董朴升 | 当铺 | hub→south→west | pawn/buy items |
| 高秀才/胖秀才 | 国子监 | hub→north→east | literate (refused so far) |
| 神话 (Zodiac) | follows player | — | 东海龙宫弟子, gave gear before |

## WEAKEST MONSTERS (for combat XP, in city):
| Monster | combat_exp | Location | Path |
|---------|-----------|----------|------|
| 大老鼠 (rat) x3 | 20 | minju3 | beiyin3 → south |
| 女孩 (girl) | 70 | minju1 | beiyin1 → east |
| 男孩 (boy) | 100 | minju4 | beiyin5 → south |
NOTE: These are NOT yuan targets. Yuan monsters are scaled to YOUR level.

## SESSION FINDINGS (cumulative)

- **Sleep recovers sen** while staying connected (~42/min passive)
- **Disconnecting drops equipped items** — must re-buy weapon every fresh socket
- **gourou + jiudai** at kezhan fills food/water past max (400+/360)
- **Combat is survivable** with 钢刀(25) + 牛皮盾(16) — monster scaled to our level 3
- **KO ≠ death** — "你的眼前一黑" then "睁开眼睛清醒过来", lose nothing
- **30-min mission timer** — if target unreachable, wait for expiry then re-ask
- **Persistent mission file** (`/tmp/yxcdrg_mission.txt`) survives between script runs
- Bot architecture: state machine (CHECK→GOTO_HUB→food/gear/yuan→TRAVEL→SEARCH→FIGHT)

## COMMON MISTAKES (DO NOT REPEAT)

| Mistake | Fix |
|---------|-----|
| `kill heishi` (first word) | `kill jing` or `kill guai` |
| tieta → south | tieta has NO south! northeast=yao, northwest=shun |
| 3 norths from 南城口 | Need **4 norths** to reach s1 level |
| Escape to hub when already at target | Check if already in target area FIRST |
| One-shot script for everything | Use persistent loop with state machine |
| Blind random search | Use map from source code for targeted search |
| 山路 → southdown | shanglu2 uses `south`, shanglu uses `southdown` — try both |
| Yuan target in 绣房/海底/湖底 | Unreachable — wait for mission to expire |
| Buffer contamination in room ID | Use FIRST room-title line only, not full desc |
| Searching when target unreachable | Decode sub-location first; skip 龙宫/月宫/红楼 |
| Forgetting weapon drops on reconnect | Always re-check `score` 兵器伤害力 at session start |



