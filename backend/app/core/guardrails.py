import re
from typing import Any, Dict


SESSION_CLUSTER_DB: Dict[str, Dict[str, Any]] = {}


class GuardrailManager:
    INPUT_BLOCKLIST = ("DROP TABLE", "SYSTEM_PROMPT_OVERRIDE", "IGNORE PREVIOUS INSTRUCTIONS")
    COPY_BLOCKLIST = ("代购", "免税", "规避关税", "偷税", "100%中奖")

    @classmethod
    def verify_input_safety(cls, prompt: str) -> Dict[str, Any]:
        matched = [word for word in cls.INPUT_BLOCKLIST if word in (prompt or "").upper()]
        return {"status": "BLOCK" if matched else "PASS", "matched": matched}

    @classmethod
    def inspect_sql(cls, sql: str, rows: int, scene_id: str) -> Dict[str, Any]:
        upper = sql.upper()
        write_op = bool(re.search(r"\b(UPDATE|DELETE|INSERT|TRUNCATE)\b", upper))
        if write_op and ("USER_POINTS_REGISTRY" in upper or rows > 10000):
            return {"status": "PENDING_REVIEW", "severity": "critical", "reason": "检测到核心资产写操作或大范围变更，必须人工审核", "rows": rows}
        if "LIMIT 1000" in upper:
            return {"status": "PASS", "severity": "low", "reason": "灰度 SQL 带有 LIMIT 1000 小流量锁"}
        return {"status": "PASS", "severity": "low", "reason": "只读查询且未越过数据变更阈值"}

    @classmethod
    def inspect_copy(cls, copy: str) -> Dict[str, Any]:
        matched = [word for word in cls.COPY_BLOCKLIST if word in (copy or "")]
        return {"status": "BLOCK" if matched else "PASS", "severity": "high" if matched else "low", "matched": matched, "reason": "命中文案合规红线" if matched else "文案合规检查通过"}

    def clean_and_validate(self, raw_data: str) -> str:
        return raw_data.strip() if raw_data and raw_data.strip() else ""


guardrail_manager = GuardrailManager()
