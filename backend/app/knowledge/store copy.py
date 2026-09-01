# backend/app/knowledge/store.py
from typing import Dict, Any

class EnterpriseKnowledgeStore:
    """企业核心数据资产元数据字典知识库 (防止 SQL 智能体因幻觉写错字段)"""
    
    @staticmethod
    def get_marketing_metadata_context() -> str:
        """将复杂的数仓物理表拓扑结构提炼为 Prompt 上下文增强注入"""
        return """
        [企业级数仓营销域字典架构声明]
        1. 物理表名: `user_base_df` (高价值核心客群流失预警表)
           - 字段: `user_id` (varchar, 用户唯一加密混淆 ID)
           - 字段: `last_active_date` (date, 最后一次活跃日期，格式 'YYYY-MM-DD')
           - 字段: `lifecycle_status` (string, 枚举值: 'active'活跃, 'churn_warning'流失预警, 'lost'已流失)
           - 字段: `vip_level` (int, 尊享等级，范围 1-7)
           - 字段: `geo_city` (string, 注册常驻城市编码)
        
        2. 物理表名: `marketing_campaign_logs` (触达复盘历史日志表)
           - 字段: `campaign_id` (int, 活动促销流水号)
           - 字段: `user_id` (varchar, 关联用户 ID)
           - 字段: `response_status` (int, 响应状态: 0未点击, 1点击未转化, 2深度闭环转化)
        """

    @staticmethod
    def get_historical_best_practices() -> str:
        """获取历史上红蓝对抗演化效果最好的高点击率文案范式"""
        return """
        [营销文案红线与金律知识库]
        - 黄金范式：采用【利益点前置】+【限时紧迫感催化】。
        - 驳回红线例证：禁止出现“大减价”、“100% 中奖”等引发合规投诉与公关危机的绝对化词汇。
        - 历史最佳案例：对 vip_level >= 5 的高价值流失预警客群，使用反思型文案比催促型文案点击率高 34%。
        """