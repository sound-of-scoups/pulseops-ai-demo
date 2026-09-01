from typing import Any, Dict
from app.agents.base import FdeBaseAgent
from app.agents.dynamic_tools import sandbox_tool_center
from app.knowledge.store import EnterpriseKnowledgeStore


class SqlAgent(FdeBaseAgent):
    def __init__(self):
        super().__init__("SQL_Data_Clean_Agent", "根据知识库元数据生成可验证的分析 SQL")

    def build_sql(self, prompt: str, scene: Dict[str, Any]) -> Dict[str, Any]:
        scene_id = scene["id"]
        if scene_id == "risk":
            sql = "UPDATE user_points_registry\nSET current_points = 0, last_update_operator = 'agent_demo'\n-- intentionally missing WHERE: guardrail must stop this plan"
        elif scene_id == "log":
            sql = "WITH parsed AS (\n  SELECT log_id, event_time,\n    json_extract_scalar(context, '$.device_info.location.region') AS region,\n    json_extract_scalar(context, '$.user_profile.tags.education_status') AS education_status\n  FROM user_behavior_log\n  WHERE event_name IN ('page_view', 'click_banner')\n), cleaned AS (\n  SELECT DISTINCT log_id, event_time\n  FROM parsed\n  WHERE region = '华东' AND education_status = 'overseas_student'\n)\nSELECT * FROM cleaned"
        elif scene_id == "geo":
            sql = "SELECT u.user_id, u.vip_level, u.geo_city\nFROM user_base_df u\nLEFT JOIN marketing_campaign_logs m ON u.user_id = m.user_id\nWHERE u.geo_city = 'SH_011' AND u.vip_level >= 5\n  AND (m.response_status IS NULL OR m.response_status <> 2)\n  AND m.sent_at >= CURRENT_DATE - INTERVAL '2' YEAR\nLIMIT 1000"
        elif scene_id == "churn":
            sql = "SELECT user_id, vip_level, last_active_date\nFROM user_base_df\nWHERE lifecycle_status = 'churn_warning'\n  AND vip_level >= 5\n  AND last_active_date < CURRENT_DATE - INTERVAL '30' DAY\nLIMIT 500"
        elif scene_id == "compliance":
            sql = "SELECT DISTINCT user_id, event_time\nFROM user_behavior_log\nWHERE event_name = 'cross_border_product_view'\n  AND event_time >= CURRENT_DATE - INTERVAL '30' DAY"
        else:
            sql = "WITH daily_user_spend AS (\n  SELECT user_id, DATE(pay_time) AS order_date,\n    COUNT(DISTINCT order_id) AS order_cnt,\n    SUM(payment_amount) AS total_amount,\n    SUM(payment_amount) / COUNT(DISTINCT order_id) AS avg_amount\n  FROM user_order_df\n  WHERE pay_time BETWEEN TIMESTAMP '2026-06-12 00:00:00' AND TIMESTAMP '2026-06-20 23:59:59'\n    AND order_status = 'completed' AND user_id IS NOT NULL AND payment_amount IS NOT NULL\n  GROUP BY user_id, DATE(pay_time)\n  HAVING SUM(payment_amount) / COUNT(DISTINCT order_id) > 500\n), islands AS (\n  SELECT *, DATE_DIFF('day', DATE '1970-01-01', order_date) - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date) AS grp_key\n  FROM daily_user_spend\n), streaks AS (\n  SELECT user_id, MIN(order_date) AS streak_start, MAX(order_date) AS streak_end, COUNT(*) AS days_in_streak, SUM(total_amount) AS streak_total_amount\n  FROM islands GROUP BY user_id, grp_key\n  HAVING COUNT(*) >= 3 AND SUM(total_amount) >= 1500\n)\nSELECT * FROM streaks"
        return {"sql": sql, "rules": EnterpriseKnowledgeStore.QUALITY_RULES, "tool": sandbox_tool_center.register("profile_cleaner", "画像清洗器", "去重、空值、枚举和时间窗校验")}
