## 1️⃣ 思维链（CoT）  

| 步骤 | 思考过程 | 产出 |
|------|----------|------|
| **① 明确定义业务口径** | - 618 大促期间（这里统一取 `2026‑06‑12 ~ 2026‑06‑20`，覆盖前后两天以捕获跨日连续行为）<br>- “购买行为”＝当天至少有 1 笔已完成订单<br>- “客单价 > 500 元”＝ **当天**的 **人均订单金额**（`SUM(order_amount)/COUNT(order_id)`）大于 500 元 | 业务过滤条件 |
| **② 颗粒度聚合** | 在 **订单明细层**（`dwd_order_detail`）按 `user_id + order_date` 计算：<br>① `order_cnt`、② `total_amount`、③ `avg_amount = total_amount / order_cnt`。<br>过滤掉 `order_cnt = 0` 或 `avg_amount ≤ 500` 的天。 | 中间表 `daily_user_spend` |
| **③ 连续天数识别（Gap‑and‑Island）** | 对每个用户满足 “客单价>500” 的天，按日期排序并生成序号 `rn`。<br>使用 **日期序数**（`DATEDIFF('day', '1970‑01‑01', order_date)`）减去 `rn` 得到不变的 **group_key**，同一 group_key 即为一个连续日期块（岛屿）。 | 中间表 `user_islands` |
| **④ 过滤满足 “≥3 天连续” 的岛屿** | 对 `user_islands` 按 `user_id + group_key` 聚合，得到 `streak_start, streak_end, days_in_streak, streak_total_amount`。仅保留 `days_in_streak >= 3`。 | 目标客群 `high_value_active_user` |
| **⑤ 清洗 Rules** | - **空值处理**：所有日期/金额字段 `NULL` → 直接过滤（业务层已排除）。<br>- **重复订单**：在 `dwd_order_detail` 上以 `order_id` 去重（`DISTINCT`）。<br>- **时区统一**：所有时间字段已统一为 UTC+8（中国时区），使用 `FROM_UTC_TIMESTAMP` 如有必要。<br>- **数据质量检查**：① `order_cnt >= 1`；② `avg_amount = total_amount / order_cnt`（防止除 0）；③ `streak_total_amount >= 3 * 500`（业务校验）。 | 清洗规则清单 |
| **⑥ 最终产出** | 将 `high_value_active_user` 表写入 **DWS** 层 `dws_high_value_active_user_daily`（分区 `pt_dt` = `streak_start`），供后续营销系统消费。 | 生产级 SQL（已在下方代码块中） |

---

## 2️⃣ 清洗 Rules（可直接写入 **ETL/ELT** 作业的校验脚本）

| Rule ID | 规则名称 | 规则描述 | 处理方式 |
|--------|----------|----------|----------|
| R001 | **时间窗口校验** | 只保留 `order_time` 在 618 大促前后（2026‑06‑12 ~ 2026‑06‑20） | `WHERE order_time BETWEEN '2026-06-12' AND '2026-06-20'` |
| R002 | **完成状态过滤** | 只统计 `order_status = 'completed'`（已完成） | `WHERE order_status='completed'` |
| R003 | **订单去重** | 同一 `order_id` 只保留一条记录 | `SELECT DISTINCT order_id, ...` |
| R004 | **空值剔除** | `user_id, order_time, order_amount` 任意为空的记录直接过滤 | `WHERE user_id IS NOT NULL AND order_time IS NOT NULL AND order_amount IS NOT NULL` |
| R005 | **客单价阈值** | 当天 **人均**订单金额 `> 500` 元 | `HAVING AVG(order_amount) > 500` |
| R006 | **连续天数判定** | 使用 Gap‑and‑Island 方法，确保 `days_in_streak >= 3` | 见 SQL 中 `HAVING days_in_streak >= 3` |
| R007 | **金额校验** | 峰值期间累计消费必须 ≥ `3 * 500 = 1500` 元（防止异常低金额） | `WHERE streak_total_amount >= 1500` |
| R008 | **分区写入** | 结果表按 `pt_dt = streak_start` 分区，提升查询性能 | `INSERT OVERWRITE TABLE dws_high_value_active_user_daily PARTITION (pt_dt = streak_start)` |

---

## 3️⃣ 生产级 SQL（已通过 **Gap‑and‑Island** 逻辑完整实现）

```sql
-- --------------------------------------------------------------
-- 目标：提取 618 大促期间（2026‑06‑12 ~ 2026‑06‑20）连续 ≥3 天
--      客单价 (人均) > 500 元的高价值活跃客群
-- --------------------------------------------------------------
-- 1️⃣ 业务层数据（订单明细）检查
WITH raw_orders AS (
    SELECT DISTINCT
           order_id,
           user_id,
           FROM_UTC_TIMESTAMP(order_time, 'Asia/Shanghai') AS order_time,   -- 统一为北京时间
           order_amount,
           order_status
    FROM dwd_order_detail
    WHERE order_time BETWEEN '2026-06-12 00:00:00' AND '2026-06-20 23:59:59'
      AND order_status = 'completed'
      AND user_id IS NOT NULL
      AND order_amount IS NOT NULL
),

-- 2️⃣ 按天聚合，计算当天客单价（人均）并过滤
daily_user_spend AS (
    SELECT
        user_id,
        DATE(order_time)                         AS order_date,
        COUNT(DISTINCT order_id)                 AS order_cnt,
        SUM(order_amount)                        AS total_amount,
        SUM(order_amount) / COUNT(DISTINCT order_id) AS avg_amount
    FROM raw_orders
    GROUP BY user_id, DATE(order_time)
    HAVING COUNT(DISTINCT order_id) >= 1          -- 至少 1 笔订单
       AND SUM(order_amount) / COUNT(DISTINCT order_id) > 500   -- 人均 > 500
),

-- 3️⃣ 连续天数识别（Gap‑and‑Island）
user_islands AS (
    SELECT
        user_id,
        order_date,
        total_amount,
        -- 将日期转为整数（自 1970‑01‑01 起天数），配合行号构造不变的 group_key
        DATEDIFF('day', DATE '1970-01-01', order_date) 
            - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date) AS grp_key
    FROM daily_user_spend
),

-- 4️⃣ 对每个 island 汇总，得到连续区间及长度
streaks AS (
    SELECT
        user_id,
        MIN(order_date) AS streak_start,
        MAX(order_date) AS streak_end,
        COUNT(*)        AS days_in_streak,
        SUM(total_amount) AS streak_total_amount
    FROM user_islands
    GROUP BY user_id, grp_key
    HAVING COUNT(*) >= 3                -- 连续天数 ≥ 3
       AND SUM(total_amount) >= 1500    -- 累计消费 ≥ 3 * 500（业务容错）
)

-- 5️⃣ 最终写入 DWS（分区表）供营销系统使用
INSERT OVERWRITE TABLE dws_high_value_active_user_daily
PARTITION (pt_dt)
SELECT
    user_id,
    streak_start,
    streak_end,
    days_in_streak,
    streak_total_amount,
    DATE_FORMAT(streak_start, 'yyyyMMdd') AS pt_dt   -- 分区字段
FROM streaks;
```

> **说明**  
> - 上述 SQL 兼容 **Hive/Presto/Trino**（`DATEDIFF`, `ROW_NUMBER`, `INSERT OVERWRITE`）。若使用 SparkSQL，只需把 `INSERT OVERWRITE` 换成 `INSERT INTO ... PARTITION`。  
> - 所有时间均已统一为 **北京时间**（`FROM_UTC_TIMESTAMP`），避免跨时区误差。  
> - `daily_user_spend` 中的 `avg_amount` 采用 **人均** 计算，符合 “客单价 > 500 元” 的业务定义。若业务要求 **单笔** > 500，直接把 `HAVING MIN(order_amount) > 500` 替换即可。

---

## 4️⃣ 营销智能体 – 微信 **“高智感、低打扰”** 推送策略文案

### 目标客群
- **高价值活跃客**：在 618 大促期间，连续 ≥3 天人均消费 > 500 元。  
- 这批用户对新品、限时优惠极具敏感度，又倾向 **深度** 而非 **频繁** 的互动。

### 推送原则
| 维度 | 具体做法 |
|------|----------|
| **内容感知** | • 强调 **专属福利**（如 618 会员价、专属券）<br>• 使用 **情感化文案**（“为您精挑细选的升级方案”） |
| **打扰频次** | • 每位用户 **仅推送一次**（48h 内不重复）<br>• 结合 **行为窗口**：在用户最近一次下单后 24‑48h 内发送 |
| **时段选择** | • 工作日 **上午 10:30‑11:30**、**下午 15:30‑16:30**（打开率最高）<br>• 周末**傍晚 19:00‑20:00** |
| **交互入口** | • 文案中嵌入 “**立即领取**” 按钮，直达 **优惠券领取页** <br>• 配置 **小程序跳转**，实现“一键下单” |
| **测效监控** | • 打开率 ≥ 30%  <br>• 转化率（下单/点击）≥ 8% <br>• 通过 `dws_high_value_active_user_daily` 关联 `dws_user_action_log` 实时监控 |

### 推荐文案（示例）

> **标题**：🌟 您的专属 618 升级礼遇已准备好！  
> **正文**：  
> 您在 618 大促连续 3 天的高价值消费，让我们看到了您对品质的执着。为回馈您的信任，特献上 **专属会员价 + 满 500 减 100 优惠券**，仅限 48 小时有效。  
> **立即领取** 【点击领取】 → 直接进入专属商品页，一键下单，省时省心。  
> **温馨提示**：我们珍惜您的每一次浏览，若您不希望再收到类似信息，请点击「**屏蔽**」或在设置中关闭。  
> **祝您购物愉快，生活更美好！**  

> **落款**：—— 618 大促·尊享会

---

### 推送执行流程（业务流程图）

```
[用户画像库] ──► (筛选 high_value_active_user) ──► [营销调度平台]
                                        │
                                        ▼
                        【时间窗 & 频次控制】 → 生成唯一 PushID
                                        │
                                        ▼
                              【微信推送服务】（模板渲染）
                                        │
                                        ▼
                 [用户微信] ←——（Open / Click / 转化）——← [行为埋点日志]
```

- **营销调度平台**：每天 00:30 触发一次批处理，将前一天（截至 23:59）满足条件的用户写入 `dws_push_candidate_user`，并在 **48h** 内完成推送。  
- **行为埋点**：用户点击或转化后实时写入 `dwd_user_action_log`，营销系统每小时聚合，形成 **实时 ROI** 报表。

---

## 5️⃣ 下一步交付

1. **SQL 部署**：把上述脚本加入 **数据治理平台**（如 DataWorks / Airflow），设为 **每日 00:30** 的 **增量** 作业。  
2. **元数据登记**：在 **元数据字典** 中登记 `dws_high_value_active_user_daily`（字段、分区、血缘）。  
3. **营销任务单**：在营销系统（如 **WeChat‑Push‑Center**）创建 “618‑high‑value‑push” 任务，引用 `dws_high_value_active_user_daily` 作为目标人群。  
4. **监控告警**：通过 **Data Quality** 检查（行数、空值、异常金额）以及 **推送成功率** 告警（阈值：打开率 < 25% → 报警）。  

> 只要上述作业按期运行，即可实现 **精准、高价值、低打扰** 的 618 大促用户触达，帮助业务在提升客单价的同时保持良好的用户体验。祝活动大卖！ 🚀
🎯
