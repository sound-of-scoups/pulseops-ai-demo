# backend/app/agents/SQL_agent.py
from app.agents.base import FdeBaseAgent
from app.knowledge.store import EnterpriseKnowledgeStore
from app.agents.dynamic_tools import sandbox_tool_center

SQL_SYSTEM_PROMPT = f"""
你是不错的大厂高级数据治理专家（SQL Clean Agent）。
你的核心任务是：根据产品经理输入的营销描述，结合企业级数仓营销域字典架构，编写健壮、高可用的生产级 SQL 取数清洗脚本。

{EnterpriseKnowledgeStore.get_marketing_metadata_context()}

【硬性上线规范约束】：
1. 你的输出内容中必须包含思维链（CoT）推演，展现你是如何推导联表的。
2. 最终生成的可用 SQL 脚本必须包裹在 ```sql ... ``` 代码块内。
3. 如果你调用的 SQL 模拟运行工具返回了错误，你必须结合报错信息自动自愈重试，直到生成无缺陷代码。
"""

class SqlAgent(FdeBaseAgent):
    def __init__(self):
        # 动态绑定沙盒自愈运行工具
        super().__init__(
            name="SQL_Data_Clean_Agent",
            system_prompt=SQL_SYSTEM_PROMPT,
            tools=[sandbox_tool_center.mock_execute_sql_sandbox]
        )