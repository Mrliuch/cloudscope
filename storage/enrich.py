"""
从云项目对照表.xlsx 读取项目 → 部门/二级部门/负责人 映射，
采集后对 Instance 对象进行 enrichment。

Excel 列顺序: 项目(0), 部门(1), 二级部门(2), 负责人(3), PMS(4), 云厂商(5)
"""
import os
import pandas as pd
from providers.base import Instance


def load_project_map(excel_path: str) -> dict[str, dict]:
    """返回 {项目名: {group, last_group, manager, cloud}}"""
    if not os.path.exists(excel_path):
        print(f"[enrich] 对照表不存在: {excel_path}，跳过 enrichment")
        return {}
    try:
        df = pd.read_excel(excel_path)
        result = {}
        for _, row in df.iterrows():
            vals = [str(v).strip() if str(v) != "nan" else "" for v in row]
            project = vals[0]
            if not project or project == "项目":
                continue
            result[project] = {
                "group": vals[1] or "未知",
                "last_group": vals[2] or "未知",
                "manager": vals[3] or "未知",
                "cloud": vals[5] if len(vals) > 5 else "",
            }
        print(f"[enrich] 加载对照表成功，共 {len(result)} 条项目映射")
        return result
    except Exception as e:
        print(f"[enrich] 读取对照表失败: {e}")
        return {}


def enrich_instances(instances: list[Instance], project_map: dict[str, dict]) -> list[Instance]:
    """用对照表填充 group/last_group/manager，无匹配则保留默认值"""
    for inst in instances:
        info = project_map.get(inst.project)
        if info:
            inst.group = info["group"]
            inst.last_group = info["last_group"]
            inst.manager = info["manager"]
    return instances
