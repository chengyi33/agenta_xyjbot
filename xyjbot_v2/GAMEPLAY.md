# XYJBOT v2 — Game Execution Rules

> Authoritative reference for how the bot plays XYJ2000 MUD (146.190.143.182:6666).
> Code implements these rules. When in doubt, this doc wins.

---

## 1. Character

- **Name:** honua | **Password:** 198633
- **Server:** 146.190.143.182:6666
- **Wimpy:** 10 (auto-flee at 10% HP)
- **Long-term goal:** Join 龙宫 (East Sea Dragon Palace) — need 避水咒 → `dive`

---

## 2. The Four Senses (Self-Awareness)

The bot always knows its state via four commands:

| Command | Shows | Used For |
|---------|-------|----------|
| `look` | Room name, description, exits | Position identification |
| `hp` | 气血, 精神, 食物, 饮水 | Health + food/water levels |
| `i` | Carried items (inventory) | Weapon in bag? Food in bag? Jiudai? |
| `score` | Equipped stats (dmg, armor), money on hand | Weapon wielded? Armor worn? Cash? |

**Key distinction:** `i` = what you *carry*. `score` = what you have *equipped*.
A weapon can be in your bag but not wielded — always check `i` before going to the shop.

---

## 3. Startup Sequence

```
gb → no → honua → 198633 → (maybe y to confirm) → set wimpy 10
→ look → score → hp → i
→ self_check():
    1. Position: identify room, set current_rid + current_region
    2. HP: if 气血 < 80% → rest to full
    3. Food/water: if < 150 → smart_eat_drink()
    4. Weapon: if dmg=0 → check i → wield from bag, or gear_up()
    5. Armor: if arm < 10 → check i → wear from bag, or gear_up()
    6. Money: note from score
→ ask yuan about kill
```

**CRITICAL:** Do NOT assume a fresh login = kezhan. Short disconnects respawn you at your
last position (items kept). Only `quit` respawns at startroom (items LOST). Always `look`
and identify on reconnect.

---

## 4. Quit vs. Disconnect

| Action | Position After | Items |
|--------|---------------|-------|
| Socket close (normal end of session) | **Last position** (stays where you were) | **Kept** (short disconnect keeps items) |
| `quit` command + relog | **Startroom** (usually kezhan) | **LOST — everything gone** |

**Rules:**
- **Never `quit` casually.** Close the socket instead.
- **Only `quit` to unstick:** when truly lost and can't navigate back to hub after ~10 min.
- **Never `quit` with good gear** (dmg>25 or arm>16) — irreplaceable.
- If `quit` respawns at `d/ourhome/kedian` (荒郊小店) instead of kezhan: enter the room,
  let 店小二 greet you — his code auto-resets startroom → kezhan. Then `quit` again.
  `d/ourhome/kedian` has no map path to the main world — escape via `recall` / `go east` /
  `go longmen`, or die and respawn at the now-fixed kezhan.

---

## 5. Gear Management

### Priority Order (check before shopping)
1. **Check `i`** — weapon in bag? → `wield all`
2. **Check `i`** — armor in bag? → `wear all`
3. **Check yuan's floor** — `look` at 天监台, dropped gear? → `get all`
4. **Buy from shop** — only if nothing useful in inventory

### Gear Value Classification

| Type | Stats | Replacement Cost | Quit+Relog OK? |
|------|-------|-----------------|----------------|
| Basic (钢刀+牛皮盾) | dmg≤25, arm≤16 | ~15两 | ✅ Yes |
| Good (gifted/special) | dmg>25 or arm>16 | Irreplaceable | ❌ Never |

### Shop Gear
- **兵器铺** (d/city/bingqipu, NPC 萧萧): `buy blade from xiao xiao` (5两), `buy shield from xiao xiao` (10两)
- **当铺** (d/city/dangpu, NPC 董朴升): rotates stock, often has strong items — check whenever passing through

### Equipping New Gear
When already wearing something, equip new gear in order:
```
remove <old item>    (e.g. remove coarse — drop starting linen shirt)
drop <old item>
unwield all
wield all            (equips best weapon)
wear all             (equips best armor)
```

### Gifted Gear at Yuan's Location
yxc sometimes drops gear at 天监台 for the bot. Check `look` before heading to the shop.
If items are on the ground: `get all → unwield all → remove all → drop coarse → wield all → wear all`

---

## 6. Food & Water

### Threshold
Eat/drink when food OR water < **150** (out of ~360 max, ~40%). Don't wait until empty.

### Smart Eat/Drink Decision Tree
```
Food/water < 150?
├─ Check i (inventory):
│   ├─ Have 狗肉/鸡腿 in bag? → eat gou rou right now (no trip)
│   └─ Have 桂花酒袋 in bag? → drink jiudai right now (no trip)
├─ Still low after eating from bag?
│   └─ Go to kezhan (d/city/kezhan):
│       ├─ No jiudai in inventory? → buy jiudai from xiao er (1两)
│       │   └─ ⚠️ IMMEDIATELY: fill jiudai (replace alcohol with water!)
│       ├─ fill jiudai (refills existing bag with water — cheap)
│       ├─ Food still low? → buy gou rou from xiao er (8×)
│       └─ eat/drink to full
```

### ⚠️ Alcohol Danger
Freshly bought 桂花酒袋 contains **alcohol**. Drinking it causes drunkenness → pass out.
**Always `fill jiudai` immediately after buying** to replace alcohol with water.
`fill jiudai` also refills an existing empty bag cheaply — don't buy new ones unnecessarily.

### Food/Water Effect
Low food/water = slow HP regeneration = die quickly in fights. Keep both bars near full.
Commands: `eat gou rou` (红烧狗肉), `drink jiudai` (桂花酒袋).
Full messages: `饱了` / `不想喝` / `吃不下` / `喝不下`. Empty messages: `一滴也不剩` / `干干净净`.

---

## 7. Navigation

### Map
- **4,938 rooms** parsed from UTF-8 LPC source (xyj2000_snoop repo)
- **Graph:** adjacency list + 20 special verb edges (dive, swim, climb, jump)
- **53 regions** from find.map

### Hierarchical Region Awareness
The bot tracks its current region at all times — like Earth → USA → California:

```
World (4,938 rooms)
├── 长安城     d/city      (244 rooms) — hub, all shops, yuan, bank
├── 长安郊外   d/changan   (70 rooms)  — east shore (dive), south shore (swim)
├── 西行路     d/westway   (34 rooms)  — road to 高老庄
├── 东行路     d/eastway   (53 rooms)
├── 高老庄     d/gao       (76 rooms)  — common mission target
├── 取经路     d/qujing    (2,127 rooms) — main game content (mostly unreachable early)
├── 东海龙宫   d/sea       (152 rooms) — needs dive
├── 南海普陀   d/nanhai    (107 rooms) — needs swim
└── ...23 other regions
```

**Why it matters:** "街道" = 61 rooms globally, but only 0 in 长安城, 3 in 高老庄, 58 in 取经路.
Region scoping eliminates false matches before exits fingerprinting even runs.
Region transitions are logged; suspicious jumps (e.g. 长安城 → 地府) are flagged.

### Accessible Regions (Fresh Character, ~10% of map)
Without flying/diving/swimming skills: 长安城 + 长安郊外 + 西行路 + 东行路 + 高老庄 = ~477 rooms.

### Dead Reckoning
The bot doesn't `look` every step:
```
1. BFS path from current → goal
2. Step in first direction
3. Parse room short name from movement response (MUD shows it automatically)
4. Match to expected short name:
   ├─ Match → update position, continue (~0.8s/room, no look needed)
   └─ Mismatch → look, re-identify, fix map if needed (~2s/room)
```
~60% faster than look-every-step navigation.

### Room Identification Priority
0. **Region-scoped** — search within current region first
1. **Adjacency from prev room** — "came from X going north → X's north neighbor"
2. **Confidence cache** — previously confirmed (short + exits → rid)
3. **Exits fingerprint** — exact match on direction set
4. **Subset/superset exits** — partial match
5. **Best Jaccard similarity** — closest exits overlap
6. **First candidate** — last resort

### Stuck Detection & Recovery
- **Stuck trigger:** >60s elapsed AND <50% of path completed
- **Try 1:** re-look, re-identify, re-BFS
- **Try 2:** wander a new direction, avoid backtracking
- **After 2 failures:** return `"stuck"` to caller

```
Stuck resolution (gear-aware):
├─ Basic gear (dmg≤25, arm≤16)? → quit + relog + re-gear + retry
├─ Good gear (dmg>25 or arm>16)? → NEVER quit
│   ├─ Try walk to hub
│   └─ Wait out mission timer (30 min)
└─ 5 consecutive stucks this session? → AUTO-ROLLBACK map overrides
```

---

## 8. Live Map Learning

The bot improves the map while playing. No upfront validation needed.

### What Triggers Learning
| Event | Action |
|-------|--------|
| Move succeeds, arrived at wrong room | Fix edge: mark old broken, add correct |
| Move succeeds, unknown room | Discover: add to pending |
| Move fails (blocked/locked) | Mark edge broken, re-BFS avoiding it |
| Room visited again (same short+exits) | Confirm pending → promote to live map |

### Map Poisoning Prevention
**Principle: optimistic discovery, pessimistic application.**

**Rooms** require 2 visits before affecting navigation:
```
1st sighting → pending (no routing effect)
2nd sighting (same short + exits) → confirmed → added to live map
```

**Edges** require round-trip or 2nd traversal:
```
1st traversal A→B → pending
B→A confirmed OR 2nd traversal A→B → confirmed → added to adjacency
```

**Broken edges** are graduated:
```
Failure #1/#2 → temporary (expires after 24h, bot retries)
Failure #3+ → permanent (never routed through again)
```

**Rollback safety:**
- `.bak` written before every save
- 5 consecutive stucks → auto-rollback to `.bak`
- Successful kill → stuck counter reset

All data persisted in `map_overrides.json` with confidence scores and timestamps.

---

## 9. Mission Loop

### Getting a Mission
```
ask yuan about kill
```

**Yuan's response forms:**
| Form | Meaning | Action |
|------|---------|--------|
| `近有X(id)在REGION（LANDMARK一带）出没` | New mission | Parse and go |
| `不是请您去收服X吗` | Existing mission reminder | Load from `/tmp/xyjbot_mission.txt` |
| `妖魔已经除尽了` | Previous kill confirmed (除尽) | Count kill, ask again |
| No mission | None available | Wait 20s, retry |

### Mission Resolution
```
Yuan says: "近有白马怪(baima guai)在高老庄（农舍一带）出没"
                 ↓
name=白马怪, ids=[baima, guai], region=高老庄, landmark=农舍
                 ↓
region → find.map → directory: 高老庄 → d/gao
landmark → search d/gao/* for short="农舍" → d/gao/house (anchor)
                 ↓
BFS from hub → d/gao/house: 27 steps (reachable ✓)
```

### Mission Lifetime
- Guai lives **30 minutes** (source: `yaoguai.c set("stay_time", time()+1800)`)
- After 30 min: guai schedules `_leave` when a player enters its room (+5 min)
- Hard destroy at +90 min
- Guai **random_moves** — drifts several rooms from spawn point over 30 min
- **If not found after 30 min:** mission over, ask Yuan for new one

### Search Policy
- **Small area** (≤45 rooms, e.g. 高老庄 ~76): full BFS sweep (guai wanders, must check all)
- **Large area** (>45 rooms): vicinity only (radius=3 from landmark)
- Not found twice on same target: wait 5 min for guai to expire

### Mission Persistence
Saved to `/tmp/xyjbot_mission.txt`:
```
白马怪|baima guai|高老庄|农舍|<timestamp>
```
Survives restarts. Bot loads and continues existing mission on reconnect.

### Unreachable Missions
Some regions require fly/dive/special access. Bot detects no path in graph → waits for 30-min timer, then gets new mission. Never wastes time sweeping unreachable areas.

---

## 10. Combat

### Engagement
1. Find target in room (match name/IDs from mission)
2. `kill <id>` — use Yuan's id (e.g. `kill baima`); fallback `kill guai` / `kill jing` always works
3. Monitor for victory/death/flee signals
4. On victory: `get all` (loot), then proceed

### Combat Signals
- **Victory:** `死了`, `服了`, `投降`, `化做一道青光`, `原形`, `领罪`, `走开`, `大赦`
- **Death:** `你死了`, `你已经死亡`, `你在地狱`, `你升天了`
- **Monster fled:** `落荒而逃`, `仓皇逃走` — chase or mark `engaged_lost`
- **KO (passed out):** `清醒` — you passed out, mission guai GONE
- **Wimpy flee:** `逃跑` — you fled, guai still there

### ⚠️ Wimpy Flee vs KO — Critical Difference

| Outcome | Guai Status | What Bot Does |
|---------|------------|---------------|
| **Wimpy flee** (你逃跑) | **Still in room** — waiting | Rest to >80% HP, eat/drink, go back and finish |
| **KO / passed out** (清醒) | **Gone** — mission guai despawns | Wait for timer to expire, ask Yuan for new mission |

### 马盗 (Road Bandit)
Appears on roads during navigation. **Pay immediately** before doing anything else:
`give ma dao 10 silver`
Delay = combat starts = likely death.

### Combat Limits
- Wimpy = 10 (flee at 10% HP)
- Combat timeout = 210 seconds max per fight
- Dangerous areas (d/westway): skip if dmg=0 or money<10两

---

## 11. Economy

### Money
- 1 gold (黄金) = 100 两 (silver) = 1000 钱 (copper)
- `ask da ye about gold` at kezhan → one-time ~3 gold (300两) — first-run only
- Keep **50两 on hand**; deposit rest at bank
- Basic gear costs ~15两 (blade 5两 + shield 10两)

### Banking (相记钱庄, d/city/bank)
| Command | Effect |
|---------|--------|
| `account` | Check balance |
| `deposit gold` | Convert gold coins → account |
| `deposit N silver` | Deposit N 两 |
| `withdraw N silver` | Withdraw N 两 |

Always deposit before risky fights. After death with no money: bank → `account` → `withdraw N silver` → re-gear.

### Shops

| Shop | Location | NPC | Sells |
|------|----------|-----|-------|
| 兵器铺 | d/city/bingqipu | 萧萧 (xiao xiao) | blade, spear, sword, shield |
| 南城客栈 | d/city/kezhan | 小二 (xiao er) | gou rou (food), jiudai (water), jitui |
| 当铺 | d/city/dangpu | 董朴升 (dongpushen) | used gear — check often, stock rotates |

---

## 12. Recovery

### Death
- Detect death signs → close socket (don't `quit`) → relog
- Self-check: re-gear from shop if basic gear (~15两 loss acceptable)
- Resume from wherever you spawned

### Disconnect / Lost
- Relog, run full self_check, load mission from file, continue

### Ourhome Escape (if spawned in d/ourhome/)
```
recall → go longmen → go east → go north
```
Until room ID no longer starts with `d/ourhome/`.

---

## 13. Special Routes (Verb-Based, Not in Walk Graph)

### 普陀山 — needs `swim`
```
hub → south ×13 → 南海之滨 → swim → 小岛 (d/nanhai/island)
→ north → north → northup → northup → 山门
```

### 龙宫 — needs 避水咒 + `dive`
```
hub → south ×13 → 南海之滨 → east × 3 → 东海之滨 (d/changan/eastseashore)
→ dive → under1 → east → under2 → east → under3 → northeast → under4 → east → 龙宫大门
```

**Getting 避水咒 (repeatable):**
```
1. buy jiudai from xiao er (kezhan)
2. Go to 袁氏草堂: hub → west×3 → north
3. give jiudai to yuan (袁守诚) → receive 〖无字天书〗
4. tear nowords → 避水咒 scroll
```
Book respawns each time you give a jiudai — repeatable.

**龙宫 free-loot run (fixes dmg=0, repeatable once diving):**
After diving at 东海之滨: follow path to pick up 长枪 (spear) + 藤甲 (armor). Loot respawns on reconnect.
`wield spear` / `wear tengjia` immediately.

### Unreachable on Foot (wait for mission reassign)
- **月宫** — needs fly
- **红楼一梦** (d/ourhome/honglou) — dream entry only
- **dntg / qujing dungeons** — special access required

---

## 14. Landmarks

| Name | Room ID | Description |
|------|---------|-------------|
| hub | d/city/center | 十字街头 — center of 长安城 |
| yuan | d/city/tianjiantai | 天监台 — 袁天罡 (mission giver) |
| kezhan | d/city/kezhan | 南城客栈 — food, water, rest |
| shop | d/city/bingqipu | 兵器铺 — 萧萧 (weapons/armor) |
| bank | d/city/bank | 相记钱庄 — deposit/withdraw |
| pawn | d/city/dangpu | 董记当铺 — 董朴升 (used gear) |
| wuguan | d/city/wuguan | 长安武馆 — 范芦平 (training) |
| caotang | d/city/yuancao | 袁氏草堂 — 袁守诚 (避水咒 source) |

---

## 15. Files Reference

| File | Purpose |
|------|---------|
| `config.py` | All constants: server, landmarks, regions, thresholds |
| `build_map.py` | One-time: parse LPC source → `xyj2000_map.json` |
| `map_engine.py` | Room graph, BFS, identification, live learning |
| `nav.py` | Dead reckoning navigator, stuck detection, region tracking |
| `net.py` | Socket I/O, text parsing, connect/disconnect |
| `combat.py` | Fight logic: engage, monitor, chase, flee handling |
| `economy.py` | Gear, food/water, banking |
| `mission.py` | Ask Yuan, resolve target, sweep vicinity |
| `bot.py` | Main loop, self-check, state machine |
| `xyj2000_map.json` | Static map (4,938 rooms, from LPC source) |
| `map_overrides.json` | Live learning: broken edges, discovered rooms/edges |
| `map_overrides.json.bak` | Rollback safety backup |
| `/tmp/xyjbot_mission.txt` | Active mission (survives restarts) |
| `/tmp/xyjbot.log` | Session log |
| `kill_tally.txt` | Lifetime kill count |

---

## 16. Safety Rules

1. **Never `quit` casually** — closes socket instead; `quit` = lose everything
2. **Never `quit` with good gear** — only if gear is basic (replaceable for ~15两)
3. **Always `fill jiudai` after buying** — fresh bag has alcohol, causes passout
4. **Check `i` before shopping** — wield/wear from inventory first
5. **Food/water threshold is 150**, not 0 — eat early, not desperately
6. **Pay 马盗 immediately** — `give ma dao 10 silver` before anything else
7. **Map updates are pessimistic** — pending discoveries don't route until confirmed (2 visits)
8. **5 consecutive stucks = rollback** — map overrides auto-reverted to `.bak`
9. **Wimpy flee ≠ KO** — fled → retry; KO → mission lost, wait for timer
10. **Guai random_moves** — if not at landmark, sweep whole area (small regions)
