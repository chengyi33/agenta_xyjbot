# yxcdrg Gear-Up Plan (no killing)

Goal: get yxcdrg a real **weapon (dmg) + shield/armor** ASAP, **without killing** any NPCs
(ID too new — see GUIDE.md hard rules).

**Priority = BUY.** Money is plentiful, so just purchase the best dmg + shield available.
The 龙宫 free-loot run is only a **fallback** for when nothing good is buyable.

Constraints: never `quit` (close socket). Re-check `score` at every session start — the
equipped weapon drops on disconnect.

---

## Stage 0 — Assess (every login)
```
score        # read 兵器伤害力 (dmg), 盔甲保护力 (armor)
i            # weapon/armor already held? how much silver?
hp           # food/water levels
```
- If a weapon is already in inventory → `wield` it, re-check score.
- Note silver on hand (should be plenty). Top up food/water at kezhan if < ~100.

## Stage 1 — BUY weapon + shield (primary)
### 兵器铺 (weapon shop) — hub → `east, south`, keeper 萧萧
```
list                              # see everything in stock + prices
buy <best weapon> from xiao xiao  # prioritize highest 伤害/damage
wield <weapon>
buy shield from xiao xiao         # 牛皮盾 (~16 armor) baseline; buy better if listed
wear shield
score                             # confirm dmg up + armor up
```
Baseline if unsure: `buy blade from xiao xiao` (钢刀, 25 dmg) + `buy shield` (牛皮盾).
Buy the strongest listed — don't conserve money.

### 当铺 (pawn shop) — from kezhan `west, west` (or hub `south, west`), keeper 董朴升
Rotating stock, often has **strong gear the weapon shop doesn't carry**. Always check:
```
list
buy <good weapon/armor> from dongpushen
wield / wear it
score
```
Equip whichever weapon+shield combo gives the best `score` (dmg + armor). Keep spares.

## Stage 2 — Top up consumables
At **南城客栈 (kezhan)** — hub → `south, east`, keeper 店小二:
```
buy gourou from xiao er ; eat gourou     # food, repeat to full
buy jiudai from xiao er ; drink jiudai   # water, repeat to full
```

## Stage 3 — Kill guai
Once geared (dmg > 0 + shield on), resume Yuan kill-missions: `xyjbot.py` parses Yuan's
`region（landmark一带）`, walks to the landmark, searches its vicinity, and fights via the
monster id. Keep food/water topped; `set wimpy` for safety.

## Stage 4 — 拜师 (join a sect) — target: 龙宫 (Dragon Palace)
When strong enough, join the strongest menpai for combat: **龙宫**. It has the best PvP kit
— dragonfight (sheshen 3-hit burst), dragonforce (buff/shield/roar), fengbo-cha (stun CC),
seashentong (freeze), huntian-hammer (weapon destruction). Reach it via the 避水咒 → `dive`
route (below); 拜师 敖广 / 龙宫掌门 inside 龙宫大门.

(Alt sects: 月宫 = top 轻功 + 剑/掌 + 後羿射日; 方寸 = spells/literate. 龙宫 is the pick for
raw combat.)

---

## 龙宫 route (loot fallback AND the 拜师 destination)
If neither 兵器铺 nor 当铺 has a worthwhile weapon/armor, get gear free from Dragon Palace.
Needs the 避水咒 scroll to `dive`.

1. **避水咒:** buy a `jiudai` at kezhan → 袁氏草堂 (hub `west×3, north`) →
   `give jiudai to yuan` (袁守诚) → `tear nowords` → 避水咒 drops out.
2. **Loot run:** from hub `south×13` → 南海之滨 → `east, east, east` → 东海之滨 → `dive`
   → `e,e,ne,e,e,ne,ne,n` (get 长枪 + 藤甲) → `s,sw,sw,se,se,s` (another 藤甲) → `get all`.
   `wield spear ; wear tengjia`. Loot respawns each reconnect.
   (1997-guide route — verify hop-by-hop vs the map graph; on a failed step `look` + BFS.)

---

## Session checklist (quick)
1. `score` / `i` — weapon still equipped? silver?
2. **兵器铺 → buy best weapon + shield → wield/wear.**
3. **当铺 → check stock → buy anything better.**
4. Top up food/water at kezhan.
5. Geared → **kill guai** (Yuan missions via `xyjbot.py`).
6. Only if nothing buyable → 龙宫 loot fallback.
7. Later, when strong → 拜师 龙宫.
8. Close socket — **never `quit`**.
