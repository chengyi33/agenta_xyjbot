# XYJ2000 Self-Guide (西游记2000)

Consolidated, still-true playbook for driving character **yxcdrg** (大龙) on
`146.190.143.182:6666`. Supersedes the old `skill.md` / `map.md` / `navigation.md`
(archived) — those held hardcoded routes that the map-graph bot replaced.

---

## ⛔ HARD RULES

### quit vs. disconnect — the position/item model (important, was misunderstood before)
| Action | Position after | Items |
|--------|----------------|-------|
| **Short socket disconnect / reconnect** (network drop, new socket) | **stays at LAST position** — no anchor | **kept** (items are NOT dropped on a brief disconnect). Only a *long* disconnect drops them. Always `look`/`i`/`score` on reconnect. |
| **`quit` command**, then relog | **respawns at char's `startroom`** (usually kezhan, but see ourhome note) | **loses ALL items + money** — must re-gear |

Consequences:
- **Reconnecting does NOT return you to a known spot.** If a prior session left the char
  lost in 高老庄, the next login lands in 高老庄, not kezhan. Don't assume a fresh login =
  kezhan.
- **`quit` usually teleports to kezhan** — but if the char's `startroom` is set to
  `d/ourhome/kedian` (荒郊小店), that's where they land instead. Fix: enter ourhome/kedian
  and let 店小二 (xiaoer) greet you — his code auto-resets `startroom → kezhan`. After that
  the next quit/death correctly goes to kezhan. **`d/ourhome/kedian` has NO map path to the
  main world** — escape by trying `recall` / `go east` / `go longmen`, or intentionally die
  and respawn at the now-fixed kezhan startroom.
- To end a normal session, just close the socket (keeps items except the wielded weapon).
  Only `quit` when you actually want the kezhan reset.

### When to `quit` to unstick
- Lost (can't identify position / can't reach the hub), **or**
- Struggling > ~10 min to reach a target.
→ Then: `quit` → relog (now at kezhan) → **re-gear** → resume. `xyjbot.py` does this
automatically (`recover_to_kezhan`), and forces kezhan at startup via `ensure_kezhan`.

### Money model — USE THE BANK

**相记钱庄** (`d/city/bank`) is the bank. From kezhan: `west → north → west → south`.

| Command | Effect |
|---------|--------|
| `account` | Check balance |
| `deposit X silver` | Deposit X 两 silver |
| `deposit gold` | Deposit gold coin items directly into account |
| `withdraw X silver` | Withdraw X 两 as silver |
| `convert` | Also converts gold coins → silver (alternate to deposit gold) |

**Rules:**
- **Keep ~50両 on hand** — covers food/water + 马盗 toll (10两). Deposit the rest.
- **After death with no money**: go to bank → `account` → `withdraw X silver` → re-gear.
- `ask da ye about gold` at kezhan is a **one-time grant only**. After that, all money comes from kill loot + bank savings.
- **Gifted gold coins**: go to bank → `deposit gold` (puts them in account) → `withdraw X silver`.
- **Never carry large amounts into combat.** Deposit before every risky fight.

`xyjbot.py` handles this automatically: `bank_deposit_excess()` after every kill, `bank_withdraw_for_gear()` before buying gear.

### Other
- **kezhan (`d/city/kezhan`) is the fixed recovery anchor** — reachable only via `quit`+relog.
- **Re-check gear every session start** — `score` 兵器伤害力; the wielded weapon drops on
  any disconnect, and `quit` drops everything.
- **Current plan: gear up first (buy dmg + shield at 兵器铺 / 当铺), THEN kill guai.** Money
  is plentiful — just buy the best; loot run is only a fallback. No 武馆 skill grinding.
  When strong, 拜师 龙宫 (strongest combat sect). See GEARUP.md.

---

## ARCHITECTURE (how the bot works now)

Everything runs through a persistent socket bot, not one-shot scripts:

- **`build_map.py`** parsed all 4,938 LPC room files → **`xyj2000_map.json`**
  (node = `d/area/room`, edges = exits).
- **`xyjmap.py`** — `XYJMap`: loads the graph, `by_short` name lookup, undirected `adj`,
  BFS `path()`, and the **find.map region map** (`area_dirs_for_region`, `rooms_under`).
- **`xyjbot.py`** — connect → login → loop: `ask_yuan` → parse mission → `resolve_target`
  → `sweep_vicinity` → `fight` → `get all` → repeat. Navigation = **look before every
  step, identify room, BFS to goal** (no dead-reckoning).

### Navigation principle
The old failure was sweeping a whole city by ambiguous room name (街道 = 61 rooms map-wide)
and wandering when `identify()` failed. The fix is **hierarchy from Yuan's own message**
(see below): region → area directory → uniquely-named landmark room → search only its
vicinity. `identify()` is constrained to the mission's directory, so 街道 drops from 61
candidates to the few in that one area.

---

## YUAN MISSION SYSTEM (袁天罡 @ 天监台, `d/city/tianjiantai`)

`ask yuan about kill` → assigns a monster (lives ~30 min) and states its location.

### Message forms
| Yuan says | Meaning | Action |
|-----------|---------|--------|
| `近有<name>(<id>)在<region>（<landmark>一带）出没` | NEW mission | parse & go |
| `不是请您去收服<name>吗` | OLD mission still active | recover from saved mission file |
| `妖魔已经除尽了` (`除尽`) | previous target cleared | ask again for a new one |

### The location is hierarchical — this is the key
Built by `find_place()` in `world/adm/daemons/miscd.c` from the table
`world/adm/daemons/find.map` (GBK). Example:

```
近有青蛇怪(Qingshe guai)在开封城（春醇茶栈一带）出没
        └name┘ └──id──┘  └region┘ └landmark┘
```

- **region** (`开封城`) → directory via find.map (`开封城 → d/kaifeng`). This is the area.
  Region names can be ambiguous (`长安城 → d/city AND d/eastway`); the landmark resolves it.
- **landmark** (`春醇茶栈`) → a *uniquely-named* room = the search anchor. `一带` = "in the
  vicinity of", so the monster is in that room or a few hops away. Walk straight there,
  then search the neighborhood — never sweep the whole city.

`parse_mission()` and `resolve_target()` in `xyjbot.py` implement exactly this.

### Kill target
The **id in parens is the kill target**: `青蛇怪(Qingshe guai)` → try `kill qingshe`, then
fall back to `kill guai` / `kill jing`. Monster ids are registered as
`({id+" guai","guai"})` or `({id+" jing","jing"})`, so the generic `guai`/`jing` always
works. Monsters `random_move` between rooms, so re-check adjacent rooms if not found.

### Unreachable regions → wait for the timer
Regions not in find.map, or in dungeon/special dirs (dntg, qujing, moon, sea-without-爻,
red-mansion dream), are unreachable on foot. `resolve_target` returns `(None, [])` → the
bot waits ~60s and re-asks until the 30-min timer expires and Yuan reassigns.

### ⏱️ Guai/mission lifetime = 30 MINUTES (source-verified, don't re-read the code)
From `world/d/dntg/yunlou/npc/yaoguai.c` and `world/d/city/npc/yuantiangang.c`:

| Fact | Source | Value |
|------|--------|-------|
| Guai spawns with a stay_time | `yaoguai.c:528` `set("stay_time", time()+1800)` | **1800s = 30 min** |
| Yuan's reminder window ("不是请您去收服X吗") | `yuantiangang.c:134` `time()<t+1800` | 30 min |
| After stay_time, guai schedules `_leave` when a player next enters its room | `yaoguai.c:588-591` `call_out("_leave",300)` | +5 min |
| Hard destroy on sight | `yaoguai.c:582` `time()>(t+3600)` | +90 min |
| "妖魔已经除尽了" (already killed) window | `yuantiangang.c:152` `time()<t+300`(+300 if dx>20000) | 5–10 min after kill |

**Key behaviors:**
- The guai **`random_move`s** every few heartbeats (`chat_msg` = `random_move`), so over 30
  min it drifts several rooms from the landmark where it spawned. The landmark is where it
  was *at spawn*, not where it is now.
- **If you don't find it near the landmark within ~30 min, the mission is over** — asking
  Yuan again rolls a fresh guai (and drops your difficulty level by 1 for "failing").
- The guai is `blocker`/`aggressive_on_owner` type sometimes — it may block your exit
  ("要打此路过，留下买路财") or attack you as the mission owner.

**Bot implementation:** `xyjbot.py` stamps `t_start` when a NEW mission is parsed
(`ask_yuan` → `save_mission(..., t_start)`), persists it in `xyjbot_mission.txt`, and
`main()` skips a mission whose `mission_age(t_start) ≥ MISSION_TTL` (1800s), re-asking Yuan
for a fresh one instead of chasing a despawned guai. Reminder form keeps the original
`t_start`; new "近有…出没" resets it.

**Bot search policy:** `sweep_vicinity` sweeps the whole reachable area if it's small
(≤45 rooms, e.g. 高老庄 ~34 — the guai wanders so we must), else only the landmark's
`radius=3` vicinity (huge regions like 长安 — avoids the endless circling). Not found →
`"not_found"`; after 2 not_founds on the same target it waits 5 min for the guai to expire.

### 🐣 Where guai can spawn (spawn dirs — from `yaoguai.c` dirs1/2/3)
The guai only spawns in these directories, so an ambiguous landmark **must** resolve to one
of them (not a same-named room elsewhere):
`d/city, d/westway, d/kaifeng, d/lingtai, d/moon, d/gao, d/sea, d/nanhai, d/eastway,
d/ourhome/honglou` (dirs1) + `d/xueshan, d/qujing/*, d/penglai` (dirs2) +
`d/death, d/meishan, d/qujing/lingshan` (dirs3).

**Trap:** landmark-less missions like `在御花园出没` — 御花园 exists in `d/huanggong`
(palace, reachable on foot but **NOT a spawn dir**) AND in `d/sea`/`d/qujing` (龙宫/取经,
spawn dirs but need dive/special access). The guai is always in the spawn-dir copy, which is
usually **unreachable on foot** → wait out the timer. `resolve_target` filters candidates to
`SPAWN_DIRS` so it never wastes time sweeping the palace.

---

## COMBAT

| Item | Stat | Cost | Buy |
|------|------|------|-----|
| 钢刀 | 25 dmg | 5两 | `buy blade from xiao xiao` (兵器铺) then `wield blade` |
| 牛皮盾 | ~16 armor | 10两 | `buy shield from xiao xiao` then `wear shield` |

- `set wimpy 15` — auto-flee at low HP. **Death wipes all money AND XP.** Always flee; you
  can recover HP and come back to finish the guai (see Wimpy vs KO below).
- **马盗 (Ma dao) road bandit**: appears on roads during navigation. **Pay immediately:**
  `give ma dao 10 silver` — the moment you see 马盗 in the room, pay before doing anything
  else. If you don't pay fast enough, combat starts and they will kill you.
- **Victory strings** (any of): 死了 服了 投降 青烟 原形 领罪 走开 大赦.
- **Loss/KO**: 承让 (lost), 清醒 / 眼前一黑 (KO'd — **KO ≠ death, lose nothing**).
- On `逃跑` (monster fled), re-issue `kill <id>` to re-engage.

### Wimpy flee vs KO — CRITICAL DIFFERENCE

| Outcome | What happened | Guai status | What to do |
|---------|---------------|-------------|-----------|
| **Wimpy flee** (`逃跑`) | You ran away at low HP | **Still there** — it stays in room | Check `hp`, wait til >50% HP, eat/drink, go back and kill |
| **KO / passed out** (`清醒`) | You passed out during fight | **GONE** — mission guai despawns | Wait for mission timer to expire (~30 min), then ask yuan for next mission |

`xyjbot.py`: wimpy returns `"fled"` → recover HP → retry. KO returns `"mission_lost"` → recover then wait for yuan to reassign.

### Clothing / gear conflicts

The game only allows ONE item per slot. To equip better gear when already wearing something:
1. `remove <old item>` — take off current armor (e.g. `remove coarse` for 粗布衣)
2. `drop <old item>` — drop it (so it doesn't block the slot)
3. `wear <new item>` or `wear all`

Example sequence when getting 战袍 + 金环锁子甲:
```
remove coarse; drop coarse   (drop starting linen shirt)
unwield all; wield all       (re-wield to get best weapon)
wear all                     (puts on 战袍, 金环锁子甲, 青萝藤盾)
```

### Free gear at 天监台 (yuan's location)

The user sometimes drops good armor/weapons on the ground at 天监台 for the bot to pick up. Always check with `look` before heading to the shop. If items are visible:
```
get all; unwield all; remove all; drop coarse; wield all; wear all
mount ma   (mount the horse for faster travel if one was left)
```
The horse 黑马 can be mounted with `mount ma` for faster navigation.

---

## FOOD / WATER — critical for HP regen

**Low food/water = slow HP regeneration = you die quickly in any fight.**
Keep both bars near full. Read exact values from **`hp`** (not `score`): the lines are
`食物：  394/  360` and `饮水：  352/  360`. (`hp` also gives 气血 & 精神 — see below.)

Commands: **`eat gou rou`** (红烧狗肉), **`drink jiudai`** (桂花酒袋). NOT `eat rou`.

**Empty container messages** (stop spamming, need refill):
- Food full: `你已经吃太饱了` / `饱了`
- Wine bag empty: `桂花酒袋已经被喝得一滴也不剩了` / `干干净净`

**Refill an empty 桂花酒袋 with `fill jiudai` at kezhan** (cheap — refills the bag you
already carry; don't buy new ones). Then `drink jiudai` to full. Buy more 红烧狗肉 for food.
`xyjbot.py`: `eat_drink_if_needed()` returns which bars ran out; `restock_consumables()`
walks to kezhan, `fill jiudai`, buys gou rou, and tops up.

### Stock up at 南城客栈 (kezhan, `d/city/kezhan`)

Money is plentiful; don't conserve. If food OR water < ~100, buy 5–10× and eat/drink until
bars max (~400 food / 360 water).

| Item | Buy | Note |
|------|-----|------|
| 炸鸡腿 | `buy jitui from xiao er` | 80文 |
| 红烧狗肉 | `buy gourou from xiao er` | 1两, more food |
| 桂花酒袋 | `buy jiudai from xiao er` | 1两, drink (also used for 无字天书, below) |

---

## GAME MECHANICS (strategy that stays true)

- **Early game: weapon is everything** — dmg 0 vs 25 is lose-vs-win. Always be armed.
- **Level all skills EVENLY.** Monsters scale to your *highest* skill; if unarmed=10 but
  dodge=3, the monster fights at ~8 while you only dodge at 3. Keep skills balanced.
- Yuan monsters are scaled to *your* level — not fixed difficulty.

---

## KEY NPCs

| NPC | Location | Path from hub (十字街头 `d/city/center`) | Use |
|-----|----------|------------------------------------------|-----|
| 袁天罡 | 天监台 | north, west | `ask yuan about kill` — missions |
| 萧萧 | 兵器铺 | east, south | buy 钢刀 / 牛皮盾 |
| 店小二 | 南城客栈 | south, east | buy jitui/gourou/jiudai |
| 范芦平 | 长安武馆 | east, north | learn unarmed/dodge/parry/force |
| 袁守诚 | 袁氏草堂 | west×3, north | `give jiudai` → 无字天书 (→ 避水咒) |
| 董朴升 | 董记当铺 | south, west (or from kezhan: west, west) | **pawn shop — check stock, often very good items to buy** |

(Paths above are for quick manual reference; the bot uses BFS over the graph.)

> **当铺 (董记当铺)** is 2 west of 南城客栈 (kezhan → west → 朱雀大街 → west → 当铺).
> Its stock rotates and frequently has strong gear worth buying — check it whenever
> passing through the city.

---

## SPECIAL ROUTES NOT IN THE WALK-GRAPH (need verbs/items)

These transitions use `swim`/`dive`/items, so they aren't normal edges — handle explicitly.

### 普陀山 (Mount Putuo) — needs `swim`
`hub → south ×13 → 南海之滨(southseashore) → swim → 小岛(island, d/nanhai) →
north(听经石) → north(山路) → northup(山路) → northup(山门)`. Cost ~20 kee + 20 sen.
紫竹林 (zhulin) is a random-exit maze — wander; both monster and player random-walk.

### 龙宫 (Dragon Palace) — needs 避水咒 to `dive`
`hub → south ×13 → 南海之滨 → east(seashore1) → east(seashore2) → east(eastseashore)
→ dive → under1 → east → under2 → east → under3 → northeast → under4 → east → 龙宫大门`.

**Get 避水咒 (repeatable):**
1. `buy jiudai from xiao er` (kezhan, 1两)
2. go to 袁氏草堂: `hub → west×3 → north`
3. `give jiudai to yuan` (袁守诚) → get 〖无字天书〗
4. `study nowords` (optional, trains `spells`, needs 道行≥50)
5. `tear nowords` → 避水咒 scroll appears. Book respawns each time you give a 桂花酒袋.

**🎁 龙宫 free-loot run (repeatable — fixes dmg=0!):** once you can `dive`, from
东海之滨: `dive → e → e → ne → e → e → ne → ne → n` picks up a **长枪 (spear)** and a
**藤甲 (rattan armor)**; then `s → sw → sw → se → se → s` grabs another **藤甲**. The loot
respawns each reconnect, so this is early weapon + armor + resale money for a newbie.
`wield spear` / `wear tengjia` immediately. (Route from community guide — verify hop-by-hop
against the map graph; the canonical dive path is under1→…→龙宫大门 above.)

**Long-term goal:** join 龙宫 (拜师 敖广 / 龙宫掌门) for the PvP build — dragonfight,
dragonforce, fengbo-cha, seashentong, huntian-hammer.

### Unreachable on foot (skip / wait for reassign)
- **月宫 (moon)** — needs fly.
- **红楼一梦 (dream, d/ourhome/honglou)** — needs sleep/dream entry.
- Any **dntg / qujing** dungeon region (e.g. 石屋 `d/dntg/hgs`).

---

## SECRETS & PROGRESSION (community tips, c.1997 — verify in-game)

Source: player guides in the old `xyj_webfeedback.md` (诸葛先生 / 小鸟 / 阿绣). Dated but
mostly still-true; confirm before relying on any single step.

### Where to learn each skill (books)
| Skill | Levels | Where / how |
|-------|--------|-------------|
| force | 0–31 | 傲来国; +31 伏魔山真经 (傲来国 武馆 东方二小姐, needs a bloomed flower from 红楼梦) |
| spells | 0–21 傲来国; 41–51 方寸山 藏经阁 (道德经) | `ask guang about 道德经` |
| literate | 0–51 月宫/方寸; 100–141 长安 (李白 — kill for 青莲剑谱 + 太白诗选) | 方寸: 千字文 |
| sword | 0–51 | 长安 |
| stick | 0–31 | 方寸山 练功室 老道 |
| spear | 0–61 | 将军府 |
| parry | 0–61 高家集; 100–141 长安城中心 `ask yuchi` (help him first) | see 夏展鹏 below |
| blade | 0–21 | buy (兵器铺) |
| unarmed | 0–31 buy; 0–51 武馆 范青屏 拳经; 100–141 二郎神; 兵马俑 (长安城外) | |
| dodge | 0–41 | 月宫 爬树/爬旗杆(傲来国)/滑冰(雪山) |
| buddhism | 0–41 | 方寸山 |

**parry book (高家集):** behind 高员外 back garden `jump wall` → bandits → kill boss
夏展鹏 → search body. He's tough and **poisons** (镖) — needs high 道行; cure poison at
**华清池** (长安东, bathe/drink). Newbie: skip until strong.

### Character build & talents (阿绣's guide)
- **定力 (concentration) = 10** is the single biggest speed lever: 定力10 trains ~**3× faster**
  than 定力30 (only hurts combat slightly). Keep it low.
- 根骨/悟性/灵性 ~**28–30**, 福缘 depends on wealth (福缘 reduces skill loss on death; 30 if
  poor, 10 if rich). 根骨 sets HP gain per age-year (14→22).
- 内力 (neili) & 法力 (mana) matter a lot: high 内力 → high 气血 → faster practice; high 精神
  (from 内力) → faster reading. Level them up.
- **Learn priority (early):** special-attack 工夫 first (lets you punch above your weight),
  then special force/spells. Skip plain unarmed & special-dodge (dodge grows free in combat).
  literate → 51 early, then push to 100/141 during a slow-道行 phase.

### NPC grinding progression (cheap → strong, mostly grouped so no chasing)
小丫鬟/小道童 → 丫鬟/老妈子 (~200 天道行) → 伙计/武官弟子 → 长安小兵 (9 of them) →
衙役 → 天兵 (16 on 天上) → 朱紫国校卫队 (14) / 武将 / 草头神 / 百年芭蕉 → 天丁 / 煤山太尉 →
千年芭蕉. Technique: wear armor, **break their weapon**, then finish with a 鸡腿 (jitui)
wielded; `abandon hammer`, toggle `enable dodge/parry none` to funnel potential.

### 🛡️ Anti-PK emergency escape (if a player/steal/cast targets you)
Death/KO by a player wipes skills+money. Escape sequence (from 阿绣, for when badly wounded):
```
wear all; unwield jitui; wield all; enforce max; enchant max
```
then spam `quit` every ~0.5s until it takes (plain `quit` fails while busy). Also
`set no_accept`, `set block_tell`, `tune chat`, `tune rumor` to avoid PK bait.
**For our bot: just disconnect the socket** — same effect, keeps items on a short drop.

### First quest: 女儿国 (西梁女儿国) — story reference
长安 → west repeatedly (pay 马盗 2両 en route) → 母子河 → south to river crossing → cross →
north (if dead-end, west a bit then north) → 小公主 → `ask princess about 郎君` →
`answer 愿意` → tossed into a green maze → practice ~2 min then walk **west** repeatedly to
exit → pick up the 传国之宝 (melts in sun — `quit`+relog respawns you in the maze to retry).
Crossing 女儿河: don't drink the water (pregnancy debuff). Clears west-quest #1.

### Money & upkeep
- Early coins: `kill 高婆` → 1 gold; later `kill 龙婆` → 5 gold. **Save money.**
- **杀气 (kill-qi)** rises as you kill NPCs; too high and you may auto-attack players. Lower
  it by giving coins to the **庙祝** (temple keeper) in a 长安 temple. Same keeper sells
  **福缘** (give gold → +福缘), which reduces skill loss on death.
- **华清池** (长安东): cures poison/disease.

### Getting to other areas (access verbs/items)
| Area | How |
|------|-----|
| 普陀山 | south to sea → `swim` |
| 龙宫 | 避水咒 → east sea edge → `dive` (see route above) |
| 傲来国 | east sea edge, **don't dive** → `zuo mufa` → `enter` → wait → on landing `out` immediately (miss it and you're stuck) |
| 花果山 (猕猴桃 +内力/法力) | via 傲来国 path, go toward 花果山; kill 流/马元帅 (very hard) → 桃林 |
| 地府 | 避水咒 → 泾水桥 (south gate) → `jump bridge`; exit with `open guancai` |
| 雪山 | `ask 乌鸦 about 大雪山` → get map |
| 无底洞 | find the 蝙蝠 (bat) NPC in 长安, 拜师 |
| 红楼梦 (dream) | enter via sleep; **exit:** `n;n;n;n;u` then `ask girl about 回去` (Chinese chars) |

### Combat efficiency (for grinding)
- vs armored NPCs: break their weapon first, then finish with 鸡腿 (`kill` with jitui
  wielded); `abandon hammer`, and `enable dodge none` / `enable parry none` at the right
  time to funnel potential into the skill you want.
- **Level skills evenly** (monsters scale to your highest) — reiterated from mechanics above.

---

## COMMON MISTAKES (still worth avoiding)

| Mistake | Fix |
|---------|-----|
| Assuming position without looking | Look before every step; identify from the room title line only |
| 汴京铁塔(tieta) → south | tieta has NO south — `northwest`→舜王街, `northeast`→尧王街 |
| Sweeping a whole city for a monster | Go to the landmark from Yuan, search its vicinity |
| `kill <fullname-first-word>` fails | Use Yuan's id, else `kill guai` / `kill jing` |
| Searching an unreachable target | Decode region first; if not in find.map, wait for timer |
| Forgetting weapon drops on reconnect | Re-check `score` 兵器伤害力 at session start |
| Typing `quit` casually | NEVER — close the socket instead (quit = lose everything) |
| Navigating past 马盗 without paying | Stop immediately, `give ma dao 10 silver`, then wait before moving |
| Death respawning at ourhome (disconnected) | Enter ourhome/kedian → xiaoer auto-fixes startroom → next death goes to kezhan |
