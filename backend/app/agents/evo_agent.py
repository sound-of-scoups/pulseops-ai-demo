from typing import Any, Dict
from app.agents.base import FdeBaseAgent


class EvoAgent(FdeBaseAgent):
    def __init__(self):
        super().__init__("RedBlue_Evo_Contending_Agent", "红蓝对抗生成与反思式文案优化")

    def generate(self, scene: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        scene_id = scene["id"]
        audience = {"618": "618 连续 3 天客单价 > 500 元的高价值活跃用户", "churn": "VIP 5+ 且超过 30 天未活跃的流失预警用户", "geo": "上海 SH_011 栅格内沉睡 VIP 用户", "log": "华东地区的海外留学生用户", "compliance": "有跨境商品浏览行为的用户", "hitl": "核心高价值客群", "risk": "会员积分资产相关用户"}.get(scene_id, "目标用户")
        blocked = scene_id == "compliance" and any(k in prompt for k in ("代购", "免税", "关税"))
        final = "【拦截】原始需求命中跨境税收敏感词，未下发文案。请改为‘依法合规的跨境商品专享权益’后重试。" if blocked else f"标题：给懂生活的你，一份专属升级礼\n\n正文：{audience}，本期为你准备了专享权益。无需反复比较，精选商品与会员价已放入专属清单，48 小时内可领取。\n\n行动按钮：领取专属权益\n频控：48 小时内不重复触达｜退订：回复 T"
        return {"audience": audience, "variants": [{"id": "A", "title": "你的专属升级礼已准备好", "copy": final, "score": 0.81 if not blocked else 0.0, "angle": "利益前置"}, {"id": "B", "title": "把喜欢的，留给更懂你的选择", "copy": final.replace("专属升级礼", "会员精选清单"), "score": 0.76 if not blocked else 0.0, "angle": "情感认同"}], "winner": "A" if not blocked else None, "blocked": blocked}
