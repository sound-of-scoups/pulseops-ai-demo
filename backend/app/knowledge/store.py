from typing import Any, Dict, List


class EnterpriseKnowledgeStore:
    """Offline knowledge base for schema, query guidance and quality rules."""

    SCHEMA: List[Dict[str, Any]] = [
        {"table": "user_base_df", "layer": "DWS", "purpose": "用户画像与生命周期", "fields": ["user_id", "vip_level", "lifecycle_status", "geo_city", "last_active_date"]},
        {"table": "user_order_df", "layer": "DWD", "purpose": "订单支付流水", "fields": ["order_id", "user_id", "payment_amount", "pay_time", "order_status"]},
        {"table": "user_behavior_log", "layer": "ODS", "purpose": "半结构化行为日志", "fields": ["log_id", "event_name", "context", "event_time"]},
        {"table": "marketing_campaign_logs", "layer": "DWD", "purpose": "触达与转化日志", "fields": ["user_id", "campaign_id", "response_status", "sent_at"]},
        {"table": "user_points_registry", "layer": "DWS", "purpose": "会员积分资产底表", "fields": ["user_id", "vip_level", "current_points", "last_update_operator"], "risk": "critical"},
    ]
    TOOLS = [
        {"name": "sql_sandbox", "label": "SQL 沙盒编译器", "type": "runtime", "description": "只读 EXPLAIN + 样本执行，返回行数与成本"},
        {"name": "profile_cleaner", "label": "画像清洗器", "type": "dynamic", "description": "去重、空值、枚举和时间窗校验"},
        {"name": "copy_policy_check", "label": "文案合规检查", "type": "dynamic", "description": "绝对化词、敏感词、退订入口检查"},
        {"name": "experiment_guard", "label": "实验护栏", "type": "guardrail", "description": "样本量、频控、A/B 分流比例检查"},
    ]
    QUALITY_RULES = [
        {"id": "R001", "name": "时间窗口", "rule": "只统计活动窗口内的已完成订单"},
        {"id": "R002", "name": "订单去重", "rule": "按 order_id 去重，避免重复流水放大金额"},
        {"id": "R003", "name": "空值剔除", "rule": "user_id、时间、金额为空的记录不得进入客群"},
        {"id": "R004", "name": "业务口径", "rule": "按 user_id + 日期聚合，日均客单价 > 500 元"},
        {"id": "R005", "name": "连续区间", "rule": "Gap-and-Island 合并连续日期，至少连续 3 天"},
        {"id": "R006", "name": "频控", "rule": "单用户 48 小时内最多 1 次触达，并提供退订入口"},
    ]

    @classmethod
    def identify_scene(cls, prompt: str) -> Dict[str, Any]:
        text = (prompt or "").lower()
        if any(k in text for k in ("user_points", "积分", "全量历史", "delete", "update")):
            return {"id": "risk", "label": "核心资产变更", "risk": "critical", "rows": 55000}
        if any(k in text for k in ("代购", "免税", "规避关税", "关税")):
            return {"id": "compliance", "label": "跨境合规纠偏", "risk": "high", "rows": 8200}
        if any(k in text for k in ("人工审核", "hitl", "review", "敏感特征")):
            return {"id": "hitl", "label": "高敏营销审核", "risk": "high", "rows": 18000}
        if any(k in text for k in ("json", "乱码", "留学生", "user_behavior_log")):
            return {"id": "log", "label": "半结构化日志清洗", "risk": "medium", "rows": 12600}
        if any(k in text for k in ("sh_011", "栅格", "沉睡", "limit 1000")):
            return {"id": "geo", "label": "沉睡 VIP 地理灰度", "risk": "low", "rows": 1000}
        if any(k in text for k in ("churn_warning", "流失预警", "召回")):
            return {"id": "churn", "label": "高价值流失召回", "risk": "low", "rows": 486}
        return {"id": "618", "label": "618 连续购买客群", "risk": "low", "rows": 12480}

    @classmethod
    def context(cls, prompt: str) -> Dict[str, Any]:
        scene = cls.identify_scene(prompt)
        return {"scene": scene, "schema": cls.SCHEMA, "tools": cls.TOOLS, "rules": cls.QUALITY_RULES}

    @staticmethod
    def get_context_by_scene(prompt: str) -> str:
        context = EnterpriseKnowledgeStore.context(prompt)
        return f"scene={context['scene']['id']}; tables={','.join(x['table'] for x in context['schema'])}; rules={len(context['rules'])}"

    @staticmethod
    def get_marketing_metadata_context() -> str:
        return "user_base_df(user_id, vip_level, lifecycle_status, geo_city); user_order_df(order_id, user_id, payment_amount, pay_time, order_status)"

    @staticmethod
    def get_historical_best_practices() -> str:
        return "利益点前置；避免绝对化承诺；高价值用户 48 小时内最多触达一次；文案必须有退订入口。"
