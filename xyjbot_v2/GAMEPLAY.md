# XYJBOT v2 — Game Execution Rules

> How the bot plays XYJ2000 MUD. This is the authoritative reference for behavior.
> Code implements these rules; this document explains *why*.

---

## 1. Character

- **Name:** honua
- **Server:** 146.190.143.182:6666
- **Password:** 198633
- **Sect goal:** 龙宫 (East Sea Dragon Palace) — need 避水咒 to dive
- **Wimpy:** 10 (flee at 10% HP — low enough to commit to fights, high enough to survive)

---

## 2. The Four Senses (Self-Awareness)

The bot maintains constant awareness of its state using four commands:

| Command | What It Shows | Used For |
|---------|--------------|----------|
| `look` | Room name, description, exits | Position identification |
| `hp` | 气血, 精神, 食物, 饮水 | Health + food/water levels |
| `i` | Inventory (carried items) | Weapon in bag? Food in bag? |
| `score` | Equipped stats (dmg, armor), money | Weapon wielded? Armor worn? Cash? |

**Key distinction:** `i` shows what you *carry*. `score` shows what you *have equipped*. A weapon can be in your bag but not wielded — check `i` before shopping.

**When senses are used:**
- **Startup:** all four (full self-check)
- **Before every mission:** `score` + `hp` (quick condition check)
- **During navigation:** `look` only on mismatch (dead reckoning)
- **After combat:** `hp` (check if need to rest)

---

## 3. Startup Sequence

```
gb → no → honua → 198633 → (maybe y) → set wimpy 10
→ look → score → hp → i
→ self_check():
    1. Position: identify room, set current_rid + current_region
    2. HP: if 气血 < 80% → rest to full
    3. Food/water: if < 150 → smart_eat_drink()
    4. Weapon: if dmg=0 → check inventory → wield or gear_up()
    5. Armor: if arm < 10 → check inventory → wear or gear_up()
    6. Money: read from score
→ ask yuan about kill
```

---

## 4. Gear Management

### Gear Check Priority
1. **Check `i` (inventory)** — weapon in bag? → `wield all`
2. **Check `i`** — armor in bag? → `wear all`
3. **Check yuan's floor** — dropped gear from previous death? → `get all`
4. **Buy from shop** — only if nothing in inventory

### Gear Value Classification
| Gear | Stats | Value | Quit+Relog? |
|------|-------|-------|-------------|
| Basic (钢刀+牛皮盾) | dmg≤25, arm≤16 | ~15两 | ✅ Yes — cheap to replace |
| Good (gifted/special) | dmg>25 or arm>16 | Irreplaceable | ❌ Never quit |

### Gear Sources
- **兵器铺 (shop):** blade 5两, shield 10两 — baseline gear
- **当铺 (pawn):** check for upgrades (parse item IDs from `list`)
- **袁天罡 floor:** dropped gear from previous deaths (free recovery)
- **da ye gold:** one-time ~3 gold (300两) — first-run gear purchase

---

## 5. Food & Water

### Threshold
- **Eat/drink when:** food OR water < 150 (out of ~360 max, ~40%)
- This is earlier than the old threshold of 100 (~28%) — safer, less risk of running out mid-mission

### Smart Eat/Drink Decision Tree
```
Food/water < 150?
├─ Check inventory (i):
│   ├─ Have 狗肉? → eat gou rou (no trip needed)
│   └─ Have 桂花酒袋? → drink jiudai (no trip needed)
├─ Still low after eating from inventory?
│   └─ Go to kezhan:
│       ├─ No jiudai in inventory? → buy jiudai (1两)
│       │   └─ CRITICAL: fill jiudai immediately (replace alcohol with water!)
│       ├─ fill jiudai (refills bag with water — cheap)
│       ├─ buy gou rou from xiao er (if food still low)
│       └─ eat/drink to full
```

### ⚠️ Alcohol Danger
Freshly bought 桂花酒袋 contains **alcohol**. Drinking it causes drunkenness and passing out. **Always `fill jiudai` after buying** to replace alcohol with water. `fill jiudai` also refills an existing bag cheaply.

---

## 6. Navigation

### Map
- **Source:** 4,938 rooms parsed from LPC `.c` files (UTF-8 from xyj2000_snoop)
- **Graph:** adjacency list with directional edges + 20 special verb edges (dive, swim, climb, jump)
- **53 regions** from find.map

### Hierarchical Region Awareness
The bot tracks its current region at all times (like "Earth → USA → California"):

```
World (4,938 rooms)
└── 长安城 (d/city, 244 rooms)
    ├── d/city/center (十字街头 — hub)
    ├── d/city/tianjiantai (天监台 — Yuan)
    ├── d/city/kezhan (南城客栈 — food/sleep)
    ├── d/city/bingqipu (兵器铺 — shop)
    ├── d/city/bank (相记钱庄)
    └── ...
└── 高老庄 (d/gao, 76 rooms)
└── 取经路 (d/qujing, 2,127 rooms)
└── 东海龙宫 (d/sea, 152 rooms)
└── ...
```

**Benefit:** "街道" = 61 rooms globally, but 0 in 长安城, 3 in 高老庄, 58 in 取经路. Region scoping eliminates ambiguity before exits fingerprinting.

Region transitions are logged and sanity-checked against the neighbor map. Suspicious transitions (e.g. 长安城 → 地府) are flagged.

### Dead Reckoning
The bot doesn't `look` every step. Instead:

```
1. BFS path from current → goal
2. Step in first direction
3. Parse room short name from movement response (MUD shows it automatically)
4. Compare to expected short name:
   ├─ Match → update position, continue (no `look` needed) — ~0.8s/room
   └─ Mismatch → look, re-identify, re-BFS — ~2s/room (only on errors)
```

This cuts navigation time ~60% compared to look-every-step.

### Room Identification
Priority order:
0. **Region-scoped lookup** — search only within current region first
1. **Adjacency from previous room** — "I came from X going north, so I'm at X's north neighbor"
2. **Confidence cache** — previously verified (short + exits → rid) mappings
3. **Exits fingerprint** — short name + exit directions = usually unique within a region
4. **Subset/superset match** — exits partially match
5. **Best Jaccard similarity** — closest exits overlap
6. **First candidate** — last resort

### Stuck Detection
- **Trigger:** >60 seconds elapsed AND <50% of path completed
- **Try 1:** re-look, re-identify, re-BFS
- **Try 2:** wander in a new direction (avoid reverse)
- **After 2 failures:** return `"stuck"` to caller

### Stuck Recovery (Gear-Aware)
```
Stuck?
├─ Gear is basic (dmg≤25, arm≤16)?
│   └─ quit + relog to kezhan, re-gear, retry (~15两 cost)
├─ Gear is good (dmg>25 or arm>16)?
│   └─ DON'T quit — irreplaceable gear
│       ├─ Try walk to hub from current position
│       └─ Wait out mission timer (30 min)
└─ 5 consecutive stucks in one session?
    └─ AUTO-ROLLBACK map overrides to .bak (map may be poisoned)
```

---

## 7. Live Map Learning

The bot is a cartographer — it maps the world while playing. No upfront validation needed.

### Discovery Rules

| Event | Action | Effect on Map |
|-------|--------|---------------|
| Move succeeds, edge in graph | Confirm edge | None (already known) |
| Move succeeds, wrong room | Fix edge | Mark old broken, add correct |
| Move succeeds, unknown room | Discover room | Add to pending (no map effect) |
| Move fails (blocked) | Mark broken | Remove from adjacency, re-BFS |
| Hidden passage found | Record edge | Add to pending (no map effect) |

### Confidence System (Map Poisoning Prevention)

**Principle: optimistic discovery, pessimistic application.**

#### Rooms
```
1st sighting → pending (NOT in live map, NOT routable)
2nd sighting (same short + exits) → confirmed → added to live map
```

#### Edges
```
1st traversal A→B → pending (NOT in adjacency)
2nd traversal A→B OR reverse B→A confirmed → confirmed → added to adjacency
```

#### Broken Edges
```
Failure #1 → temporary (expires after 24h, bot will retry)
Failure #2 → temporary (still retrying)
Failure #3+ → permanent (never routed through again)
```

#### Rollback Safety
- `.bak` file written before every `map_overrides.json` save
- 5 consecutive stuck events in one session → auto-rollback to `.bak`
- Successful kill → stuck counter reset (navigation confirmed working)
- Manual `rollback_overrides()` available anytime

### Persistence
All overrides stored in `map_overrides.json`:
```json
{
  "broken_edges": {"from|to": {direction, failures, first_failed, permanent}},
  "discovered_rooms": {"rid": {short, exits, confidence, first_seen, last_confirmed}},
  "discovered_edges": {"from|to": {direction, confidence, confirmed}},
  "pending_rooms": {"rid": {short, exits, confirmations, first_seen}},
  "pending_edges": {"from|to": {direction, first_seen}}
}
```

---

## 8. Mission Loop

### Flow
```
1. Ask Yuan for mission: `ask yuan about kill`
2. Parse response: "近有白马怪(baima guai)在高老庄（农舍一带）出没"
   → name=白马怪, ids=[baima, guai], region=高老庄, landmark=农舍
3. Resolve target:
   - region → find.map → directory (d/gao)
   - landmark → search rooms in directory for short name match → d/gao/house
4. Check reachability: BFS from hub to anchor
5. Pre-mission self-check (gear, HP, food/water)
6. Navigate to anchor (dead reckoning)
7. Sweep vicinity (BFS from anchor, search each room for target)
8. Fight target when found
9. Return to Yuan, confirm kill (除尽)
10. Bank deposit, repeat
```

### Special Cases
- **"不是请您去收服X吗?"** — Yuan reminding about existing mission. Load from file.
- **"除尽"** — previous mission's monster died. Count as kill, ask again.
- **No mission** — wait 20 seconds, retry.
- **Mission expired** (>30 min) — re-ask Yuan.
- **Unreachable region** — wait for timer to expire.

### Mission Persistence
Mission saved to `/tmp/xyjbot_mission.txt`:
```
白马怪|baima guai|高老庄|农舍|<timestamp>
```
Survives restarts. On reconnect, bot loads and continues existing mission.

---

## 9. Combat

### Engagement
1. Find target in room (match name or IDs from mission)
2. `kill <target>` or `kill <id>`
3. Monitor combat:
   - Victory signs: "死了", "服了", "投降", "化做一道青光", "原形"
   - Death signs: "你死了", "你已经死亡"
   - Monster fled: "落荒而逃", "仓皇逃走" → chase or report engaged_lost
4. After victory: `get all` (loot), drain excess text

### Safety
- **Wimpy=10:** auto-flee at 10% HP
- **Combat timeout:** 210 seconds max per fight
- **Death recovery:** relog at kezhan, re-gear (if basic gear, acceptable loss)
- **Dangerous areas:** skip missions in `d/westway` if unprepared (low gear + no money)

---

## 10. Economy

### Money
- 1 gold (黄金) = 100 两 (silver) = 1000 钱 (copper)
- `da ye` gives ~3 gold (300两) — one-time per character
- Basic gear costs ~15两 (blade 5两 + shield 10两)
- Keep 50两 on hand for food/water; deposit rest at bank

### Banking
- Deposit: `deposit gold` (all gold) + `deposit N silver` (excess)
- Withdraw: `withdraw N silver` (when need cash for gear/food)
- Bank at 相记钱庄 (d/city/bank)

### Shopping
| Shop | Location | NPC | Sells |
|------|----------|-----|-------|
| 兵器铺 | d/city/bingqipu | 萧萧 (xiao xiao) | blade, spear, sword, shield |
| 南城客栈 | d/city/kezhan | 小二 (xiao er) | gou rou (food), jiudai (water bag) |
| 当铺 | d/city/dangpu | 董朴升 (dongpushen) | used gear (check for upgrades) |

---

## 11. Recovery

### Death
- Bot detects death signs in response text
- Recovery: close socket (don't `quit` — it's automatic on death), relog
- Re-gear from shop (if basic gear, ~15两 loss is acceptable)
- Resume from kezhan

### Disconnect / Lost
- Close socket, reconnect
- Relog at starting position
- Run self_check to re-orient
- Load pending mission from file

### Ourhome Escape
If bot spawns in `d/ourhome/` (newbie area):
```
recall → go longmen → go east → go north
```
Until rid no longer starts with `d/ourhome/`.

---

## 12. Files

| File | Purpose |
|------|---------|
| `config.py` | Constants, landmarks, regions, gear/economy params |
| `build_map.py` | One-time: parse LPC source → `xyj2000_map.json` |
| `map_engine.py` | Room graph, BFS, identification, map learning |
| `nav.py` | Navigator: dead reckoning, stuck detection, region tracking |
| `net.py` | Socket I/O, text parsing, connect/disconnect |
| `combat.py` | Fight logic: engage, monitor, chase |
| `economy.py` | Gear, food/water, banking |
| `mission.py` | Ask Yuan, resolve target, sweep vicinity |
| `bot.py` | Main loop, self-check, state machine |
| `xyj2000_map.json` | Static map (4,938 rooms, from LPC source) |
| `map_overrides.json` | Live map learning (broken edges, discovered rooms/edges) |
| `map_overrides.json.bak` | Rollback safety backup |
| `/tmp/xyjbot_mission.txt` | Current mission (survives restarts) |
| `/tmp/xyjbot.log` | Session log |
| `kill_tally.txt` | Lifetime kill count |

---

## 13. Landmarks

| Name | Room ID | Description |
|------|---------|-------------|
| hub | d/city/center | 十字街头 — center of 长安城 |
| yuan | d/city/tianjiantai | 天监台 — 袁天罡 (mission giver) |
| kezhan | d/city/kezhan | 南城客栈 — food, water, sleep |
| shop | d/city/bingqipu | 兵器铺 — 萧萧 (weapon/armor shop) |
| bank | d/city/bank | 相记钱庄 — deposit/withdraw |
| pawn | d/city/dangpu | 董记当铺 — 董朴升 (used gear) |
| wuguan | d/city/wuguan | 长安武馆 — 范芦平 (training) |
| caotang | d/city/yuancao | 袁氏草堂 — 袁守诚 |

---

## 14. Accessible Regions (Fresh Character)

Without flying, swimming, or advanced skills, the bot can reach:

| Region | Rooms | Access |
|--------|-------|--------|
| 长安城 (d/city) | 244 | Hub — always accessible |
| 长安郊外 (d/changan) | 70 | North from city gates |
| 西行路 (d/westway) | 34 | West from 长安 |
| 东行路 (d/eastway) | 53 | East from 长安 |
| 高老庄 (d/gao) | 76 | Via 西行路 |
| **Total** | **~477** | **~10% of map** |

Other regions require:
- **东海龙宫 (d/sea):** `dive` at 东海之滨 (need 避水咒 or 龙宫 membership)
- **南海普陀 (d/nanhai):** `swim` at 南海之滨
- **取经路 (d/qujing):** Quest progression, 2,127 rooms — main game content
- **月宫, 蓬莱, 天宫, etc.:** Flying skill required

---

## 15. Safety Rules

1. **Never `quit` casually** — loses all items. Close socket instead.
2. **Never `quit` with good gear** — only quit+relog if gear is basic (replaceable for ~15两).
3. **Always `fill jiudai` after buying** — fresh jiudai contains alcohol → drunkenness.
4. **No margin trading** (live Alpaca account rule, unrelated but same principle).
5. **`trash` > `rm`** for file operations.
6. **Map overrides are pessimistic** — pending discoveries don't affect navigation until confirmed.
7. **5 stucks = rollback** — if the bot gets stuck 5 times in one session, map overrides may be poisoned → auto-rollback to `.bak`.
