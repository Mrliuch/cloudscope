from typing import Optional
from providers.base import CloudProvider, Instance, MetricData


def create_provider(account_config: dict) -> Optional[CloudProvider]:
    """返回 None 表示跳过（AK/SK 为空）"""
    if not account_config.get("ak") or not account_config.get("sk"):
        print(f"[跳过] {account_config.get('name')} AK/SK 未配置")
        return None
    provider_type = account_config["provider"]
    if provider_type == "aliyun":
        from providers.aliyun import AliyunProvider
        return AliyunProvider(account_config)
    elif provider_type == "huawei":
        from providers.huawei import HuaweiProvider
        return HuaweiProvider(account_config)
    elif provider_type == "tencent":
        from providers.tencent import TencentProvider
        return TencentProvider(account_config)
    elif provider_type == "volcengine":
        from providers.volcengine import VolcengineProvider
        return VolcengineProvider(account_config)
    else:
        raise ValueError(f"不支持的云厂商: {provider_type}")
