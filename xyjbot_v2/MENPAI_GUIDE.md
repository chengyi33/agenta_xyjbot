# XYJ2000 — 门派选择指南 (Sect Selection Guide)

> 分析日期: 2026-07-08 | 角色: Honua (蛤怒) | 武学: 7765 | 潜能: 2476

## 八大门派总览

| # | 门派 | 位置 | 可达性 | 成长方向 | 评价 |
|---|------|------|--------|----------|------|
| 1 | 灵台方寸山 | d/lingtai | ✅ | 道士/法术 | 千钧棒法刚猛，有藏经阁 |
| 2 | 南海普陀山 | d/putuo | ❌ | 佛门/法术 | 大力降魔杵，灵丹妙药 |
| 3 | 昆仑山月宫 | d/moon | ❌ (仅女徒) | 法术/剑舞 | 轻灵飘逸，只收女徒 |
| 4 | 东海龙宫 | d/dntg | ⚠️ 需避水咒 | 均衡 | 水中霸主，聚宝盆 |
| 5 | 阴曹地府 | d/death | ✅ 长安桥 | 诡异/速成 | 摄气(吸血)+回城术 |
| 6 | 陷空山无底洞 | d/wudidong | ❌ 无地图 | 阴狠/拼命 | 只攻不守，玻璃大炮 |
| 7 | 大雪山 | d/xueshan | ✅ | 毒术/阴狠 | 毒术为主，不适合刷怪 |
| 8 | 五庄观 | d/wuzhuangguan | ❌ 取经路 | 法术/全面 | 技能最全，有人参果 |

---

## 🏆 首选推荐: 阴曹地府

### 选择理由

阴曹地府是自动化bot刷怪的最佳门派，核心原因：

1. **摄气 (Lifesteal)** — `exert sheqi`
   - 战斗中吸取敌人气血为己用
   - 大幅减少回复时间，刷怪效率翻倍
   - 文件: `daemon/class/ghost/tonsillitis/sheqi.c`

2. **回城术 (Town Portal)** — `cast townportal`
   - 任何时候可传送回酆都城
   - **彻底解决bot卡死问题** — 不再需要quit+relog
   - 节省大量金币（不用丢装备重买）

3. **护法 (Summon)** — `cast invocation`
   - 战斗中召唤鬼卒助战
   - 多打一，更安全

4. **速成** — 官方描述"学来甚易，又有加力"
   - 成长快，适合bot快速提升

5. **地狱火** — `cast inferno`
   - 重复攻击效应，持续伤害

6. **六道轮回** — `perform lunhui`
   - 烈火鞭绝招，高伤害

### 入门方式

```
地点: 长安城 → 桥 (d/changan/bridge)
命令: jump bridge
条件: 未加入任何门派即可直接进入
拜师: 白无常 (bai wuchang) — 无条件收徒
```

源码确认 (`d/changan/bridge.c`):
```c
// 未加入门派者 → 直接进入地府
// 已加入其他门派者 → 掉入水中
if( me->query("family") && 
    (string)me->query("family/family_name")!="阎罗地府" ) {
    me->move(__DIR__"inwater");  // 掉水里
} else {
    me->move("/d/death/gate");   // 进入地府
}
```

### 武功体系

| 类型 | 技能 | 绝招 |
|------|------|------|
| 内功 | 摄气诀 (tonsillitis) | sheqi(吸血), powerup(增强), powerfade(降杀气) |
| 掌法 | 惊魂掌 | - |
| 棒法 | 哭丧棒 | - |
| 鞭法 | 烈火鞭 | 六道轮回 (lunhui) |
| 剑法 | 追魂剑 | - |
| 轻功 | 鬼影迷踪 | - |
| 法术 | 勾魂术 | invocation(招鬼), inferno(地狱火), curse(诅咒), townportal(回城) |

### 师承体系

| 辈分 | NPC | 位置 |
|------|-----|------|
| 1代 | 地藏王菩萨 (dizhang) | 地府深处 |
| 2代 | 王方平 (wang fangping) | 地府 |
| 3代 | 白无常 (bai wuchang) | 地府入口 |
| 3代 | 黑无常 (hei wuchang) | 地府 |

---

## 🥈 备选: 方寸山

### 武功体系
- 千钧棒法 (qianjun-bang) — 孙悟空同款
- 菩提指 (puti-zhi)
- 小无相功 (wuxiang-force) 
- 筋斗云 (jindouyun) — 轻功
- 道家法术

### 优势
- 有藏经阁，可读书提升
- 千钧棒法攻击力强
- 已经在地图中可达

### 劣势
- 法师类成长 → 气血增长低 (15/年)
- 无吸血、无回城 → 更适合手动玩家
- 没有bot自动化优势

---

## 其他门派简评

### 龙宫
- 需要避水咒进入（bot目前获取失败）
- 水中战斗有优势
- 宝物丰富（聚宝盆）
- 均衡成长

### 大雪山
- 毒术为主 → 不适合追求快速击杀
- 寒冷气候有修行加成
- 门派背景故事最有趣（大鹏明王）

### 月宫
- 仅收女徒 → Honua 无法加入
- 轻灵路线，雪山剑法+冷月凝香舞
- 不可达（月宫在天界）

### 无底洞
- 需要在长安找到蝙蝠精拜师
- 玻璃大炮 → bot容易死
- 没有地图数据

### 五庄观
- 技能最全面（刀剑杖锤拳法+太乙仙法）
- 镇元神功可自疗
- 有人参果
- 但远在取经路，不可达

### 普陀山
- 佛法无边，大力降魔杵
- 灵丹妙药丰富
- 不可达

---

## Bot 加入地府的实施计划

### Phase 1: 入门
```
1. bot从长安城 → 导航到桥 (d/changan/bridge)
2. 确认未加入任何门派 (family == null)
3. jump bridge → 进入 d/death/gate
4. 找到白无常 → apprentice bai wuchang
```

### Phase 2: 学习技能 (优先级排序)
```
1. 摄气诀 (内功) → 先学到能使用 sheqi (吸血)
2. 鬼影迷踪 (轻功) → 基础移动
3. 烈火鞭 (武器) → 主要输出
4. 勾魂术 (法术) → townportal (回城) + inferno (地狱火)
5. 惊魂掌 / 哭丧棒 → 备用
```

### Phase 3: 刷怪循环更新
```
当前循环: MISSION → TRAVEL → SEARCH → FIGHT → LOOT → BANK → MISSION
更新循环: MISSION → TRAVEL → SEARCH → (exert sheqi) → FIGHT → LOOT → BANK → MISSION
          卡死时: cast townportal → 回到酆都城 → 重新导航
```

### 需要修改的文件
- `bot.py` — 新增 JOIN_SECT 状态，更新战斗逻辑加入 sheqi
- `config.py` — 新增地府 landmarks (gate, baiwuchang, 酆都城)
- `economy.py` — 新增技能学习逻辑
- `nav.py` — 确认地府路径可达