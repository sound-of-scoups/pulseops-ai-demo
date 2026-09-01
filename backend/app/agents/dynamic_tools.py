from typing import Any, Dict


class DynamicSandboxToolCenter:
    """Runtime registry and deterministic sandbox used for the teaching demo."""

    def __init__(self) -> None:
        self.registry: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, label: str, description: str) -> Dict[str, Any]:
        tool = {"name": name, "label": label, "description": description, "registered_at": "runtime"}
        self.registry[name] = tool
        return tool

    def mock_execute_sql_sandbox(self, sql_query: str, expected_rows: int = 1000) -> Dict[str, Any]:
        sql = sql_query.upper()
        errors = []
        if "SELECT" not in sql and not sql.lstrip().startswith("WITH"):
            errors.append("只允许分析型 SELECT / WITH 查询")
        if "FROM" not in sql:
            errors.append("缺少 FROM 表来源")
        if "USER_BASE_DF" in sql and "WHERE" not in sql:
            errors.append("大表扫描必须带 WHERE 条件")
        if errors:
            return {"status": "FAIL", "errors": errors, "compiled_rows": 0, "cost_seconds": 0}
        return {"status": "PASS", "compiled_rows": expected_rows, "cost_seconds": 0.42, "sample": [{"user_id": "u_09f3", "vip_level": 6, "lifecycle_status": "churn_warning"}, {"user_id": "u_4a11", "vip_level": 5, "lifecycle_status": "churn_warning"}]}

    def clean_profile(self, rows: int) -> Dict[str, Any]:
        return {"tool": "profile_cleaner", "input_rows": rows, "output_rows": max(rows - 37, 0), "removed": {"duplicates": 18, "nulls": 12, "invalid_enum": 7}}

    def check_copy(self, text: str) -> Dict[str, Any]:
        banned = [word for word in ("代购", "免税", "规避关税", "100%", "绝对") if word in text]
        return {"status": "BLOCK" if banned else "PASS", "matched": banned, "tool": "copy_policy_check"}


sandbox_tool_center = DynamicSandboxToolCenter()
