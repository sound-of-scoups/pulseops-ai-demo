import unittest

from app.agents.SQL_agent import SqlAgent
from app.agents.dynamic_tools import DynamicSandboxToolCenter
from app.core.guardrails import GuardrailManager
from app.knowledge.store import EnterpriseKnowledgeStore


class CoreWorkflowTests(unittest.TestCase):
    def test_scene_router_and_knowledge_base(self):
        context = EnterpriseKnowledgeStore.context("618 连续 3 天客单价大于 500 元")
        self.assertEqual(context["scene"]["id"], "618")
        self.assertGreaterEqual(len(context["schema"]), 5)
        self.assertGreaterEqual(len(context["rules"]), 6)

    def test_sql_sandbox_and_retry_asset(self):
        scene = EnterpriseKnowledgeStore.identify_scene("618")
        result = SqlAgent().build_sql("618", scene)
        sandbox = DynamicSandboxToolCenter().mock_execute_sql_sandbox(result["sql"], scene["rows"])
        self.assertEqual(sandbox["status"], "PASS")
        self.assertIn("ROW_NUMBER", result["sql"])

    def test_guardrails(self):
        manager = GuardrailManager()
        self.assertEqual(manager.inspect_sql("UPDATE user_points_registry SET current_points = 0", 55000, "risk")["status"], "PENDING_REVIEW")
        self.assertEqual(manager.inspect_copy("依法合规的会员权益")["status"], "PASS")
        self.assertEqual(manager.inspect_copy("代购免税大减价")["status"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
