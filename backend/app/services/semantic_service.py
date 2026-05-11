"""
语义解析模块：将复杂的药品说明转换为通俗易懂的表达
采用规则 + 模板的方式，无需外部大模型 API
"""
import re
from typing import Optional


def simplify_efficacy(efficacy: Optional[str]) -> Optional[str]:
    """将功效说明简化为老人容易理解的表达"""
    if not efficacy:
        return None

    text = efficacy.strip()

    # 常见功效关键词映射
    keyword_map = {
        "清热解毒": "帮助退烧、消炎",
        "清瘟解毒": "帮助退热、减轻感冒发炎症状",
        "宣肺泄热": "帮助缓解咳嗽、咽痛、发热",
        "活血化瘀": "帮助血液流通",
        "祛风散寒": "驱走体内的寒气",
        "健脾益气": "帮助消化、增强体力",
        "滋阴补肾": "补肾、增强体质",
        "疏肝理气": "帮助肝脏工作，减少胸闷",
        "镇咳祛痰": "止咳、化痰",
        "降压": "降低血压",
        "降糖": "降低血糖",
        "降脂": "降低血脂",
        "抗菌消炎": "杀菌消炎",
        "止痛": "缓解疼痛",
        "退热": "退烧",
        "抗过敏": "减轻过敏症状",
        "镇静安神": "帮助安神、改善睡眠",
        "润肠通便": "帮助排便",
        "止泻": "止腹泻",
        "化痰止咳": "化痰、止咳",
        "消炎": "消除炎症",
        "抗感染": "抵抗感染",
        "头痛": "头痛",
        "感冒": "感冒",
        "发热": "发烧",
        "咽痛": "嗓子疼",
        "鼻塞": "鼻子不通气",
        "流涕": "流鼻涕",
    }

    simplified = text
    for key, val in keyword_map.items():
        if key in simplified and key != val:
            simplified = simplified.replace(key, val)

    # 添加前缀使表达更口语化
    if not simplified.startswith("这个药"):
        simplified = f"这个药的作用是：{simplified}"

    return simplified


def simplify_usage(usage: Optional[str]) -> Optional[str]:
    """将用法用量简化为通俗表达"""
    if not usage:
        return None

    text = usage.strip()
    parts = []

    # 提取服用方式
    if "口服" in text:
        parts.append("用嘴吃（口服）")
    elif "外用" in text:
        parts.append("涂在皮肤上（外用）")
    elif "含服" in text:
        parts.append("含在嘴里慢慢化")
    elif "舌下含服" in text:
        parts.append("放在舌头下面含着")
    elif "冲服" in text:
        parts.append("用水冲开喝")

    # 提取剂量
    dose_match = re.search(r"(?:一次|每次)\s*(\d+(?:\.\d+)?)\s*(片|粒|袋|支|丸|滴|ml|毫升|g|克|mg|毫克)", text)
    if dose_match:
        parts.append(f"每次吃{dose_match.group(1)}{dose_match.group(2)}")

    # 提取频率
    freq_match = re.search(r"(?:一日|每日|每天)\s*(\d+)\s*次", text)
    if freq_match:
        freq_num = int(freq_match.group(1))
        freq_map = {1: "每天吃1次", 2: "每天吃2次（早晚各一次）", 3: "每天吃3次（早中晚各一次）"}
        parts.append(freq_map.get(freq_num, f"每天吃{freq_num}次"))

    # 饭前饭后
    if "饭前" in text:
        parts.append("在吃饭之前吃")
    elif "饭后" in text:
        parts.append("在吃饭之后吃")
    elif "空腹" in text:
        parts.append("空着肚子的时候吃")
    elif "睡前" in text:
        parts.append("睡觉之前吃")

    if parts:
        return "，".join(parts) + "。"

    return f"用法：{text}"


def simplify_caution(caution: Optional[str]) -> Optional[str]:
    """将注意事项简化"""
    if not caution:
        return None

    text = caution.strip()
    warnings = []

    keyword_rules = [
        (("孕妇禁用",), "怀孕的人不能吃"),
        (("孕妇慎用", "孕妇", "妊娠"), "怀孕的人要小心，最好先问医生"),
        (("儿童禁用",), "小孩子不能吃"),
        (("儿童", "成人监护"), "儿童使用时需要大人照看"),
        (("哺乳期",), "喂奶的妈妈最好先问医生"),
        (("过敏者禁用", "过敏体质者慎用", "过敏"), "对这个药过敏的人不能吃，容易过敏的人要小心"),
        (("肝功能不全", "肝病"), "肝不好的人要小心，最好先问医生"),
        (("肾功能不全", "肾病"), "肾不好的人要小心，最好先问医生"),
        (("高血压", "心脏病", "糖尿病"), "有高血压、心脏病、糖尿病等慢性病的人要先问医生"),
        (("辛辣",), "吃这个药的时候不要吃辣的"),
        (("烟", "酒"), "吃这个药的时候不要抽烟喝酒"),
        (("油腻",), "吃这个药的时候不要吃太油腻的东西"),
        (("生冷",), "吃这个药的时候少吃太凉的食物"),
        (("不宜驾驶",), "吃了这个药不要开车"),
        (("嗜睡",), "吃了可能会犯困"),
        (("长期服用",), "这个药不适合长期一直吃"),
        (("38.5", "去医院就诊"), "如果发烧很高或者症状重，要尽快去医院"),
        (("3天症状无缓解", "三天症状无缓解"), "吃了几天还没好转，要去医院看看"),
        (("运动员",), "运动员使用前要先确认是否适合"),
    ]

    for keywords, message in keyword_rules:
        if all(keyword in text for keyword in keywords):
            warnings.append(message)

    if warnings:
        deduped = list(dict.fromkeys(warnings))
        return "注意：" + "；".join(deduped) + "。"

    return f"注意事项：{text}"


def generate_reminder_description(frequency: Optional[str], usage: Optional[str]) -> dict:
    """
    根据频率和用法生成提醒方案建议
    返回: { "times_per_day": int, "time_suggestions": [str], "meal_relation": str, "dosage": str }
    """
    result = {
        "times_per_day": 3,
        "time_suggestions": ["08:00", "12:00", "18:00"],
        "meal_relation": "after_meal",
        "dosage": "按说明书服用",
    }

    combined = (frequency or "") + (usage or "")

    # 提取频率
    freq_match = re.search(r"(?:一日|每日|每天)\s*(\d+)\s*次", combined)
    if freq_match:
        n = int(freq_match.group(1))
        result["times_per_day"] = n
        if n == 1:
            result["time_suggestions"] = ["08:00"]
        elif n == 2:
            result["time_suggestions"] = ["08:00", "20:00"]
        elif n == 3:
            result["time_suggestions"] = ["08:00", "12:00", "18:00"]
        elif n == 4:
            result["time_suggestions"] = ["08:00", "12:00", "16:00", "20:00"]

    # 饭前饭后
    if "饭前" in combined or "餐前" in combined:
        result["meal_relation"] = "before_meal"
        result["time_suggestions"] = [
            t.replace(":00", ":30" if "08" not in t else ":00").replace("08:00", "07:30").replace("12:00", "11:30").replace("18:00", "17:30")
            for t in result["time_suggestions"]
        ]
    elif "空腹" in combined:
        result["meal_relation"] = "empty_stomach"
        result["time_suggestions"] = [
            t.replace("08:00", "06:30") for t in result["time_suggestions"]
        ]
    elif "睡前" in combined:
        result["meal_relation"] = "before_sleep"
        result["time_suggestions"] = ["21:30"]
        result["times_per_day"] = 1
    else:
        result["meal_relation"] = "after_meal"

    # 剂量
    dose_match = re.search(r"(?:一次|每次)\s*(\d+(?:\.\d+)?)\s*(片|粒|袋|支|丸|滴|ml|毫升|g|克|mg|毫克)", combined)
    if dose_match:
        result["dosage"] = f"每次{dose_match.group(1)}{dose_match.group(2)}"

    return result
