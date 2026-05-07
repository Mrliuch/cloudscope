from __future__ import annotations
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Instance:
    instance_id: str
    name: str
    region: str
    project: str = ""
    cpus: int = 0
    ram: int = 0
    n_ip: str = ""
    w_ip: str = ""
    status: str = ""
    os_type: str = ""
    charging_mode: str = ""
    created: str = ""
    expire_time: str = ""
    group: str = "未知"
    last_group: str = "未知"
    manager: str = "未知"


@dataclass
class MetricData:
    cpu_avg: float = 0.0
    cpu_max: float = 0.0
    mem_avg: float = 0.0
    mem_max: float = 0.0
    disk_avg: float = 0.0          # 所有磁盘中最大使用率
    disk_details: list = field(default_factory=list)  # [{"device": "/dev/vda1", "usage": 45.2}]
    out_avg: float = 0.0
    in_avg: float = 0.0


@dataclass
class ExpiringResource:
    resource_id: str
    name: str
    resource_type: str      # ECS / RDS / CBS / SLB 等
    region: str
    project: str
    expire_time: str        # "YYYY-MM-DD HH:MM:SS"（统一转北京时间存储）
    charging_mode: str
    status: str
    cloud: str = ""
    provider: str = ""
    group: str = "未知"
    last_group: str = "未知"
    manager: str = "未知"
    auto_renew: str = "未知"   # "是" / "否" / "未知"


def _parse_expire_dt(s: str) -> datetime | None:
    """解析到期时间字符串，统一返回北京时间（UTC+8）naive datetime"""
    if not s or s.strip() in ("", "None", "null", "0001-01-01T00:00:00Z"):
        return None
    try:
        from dateutil.parser import parse as _dp
        dt = _dp(s)
        if dt.tzinfo is not None:
            utc8 = timedelta(hours=8)
            dt = dt.utctimetuple()
            import calendar
            ts = calendar.timegm(dt)
            dt = datetime.utcfromtimestamp(ts) + utc8
        return dt
    except Exception:
        return None


@dataclass
class CostRecord:
    year: int
    month: int
    project: str
    service_type_code: str
    service_type_name: str
    service_category: str   # compute / storage / network / database / other
    amount: float           # 元（人民币）


@dataclass
class AccountBalance:
    cash_balance: float = 0.0
    coupon_amount: float = 0.0
    credit_limit: float = 0.0
    owe_amount: float = 0.0
    available_amount: float = 0.0
    currency: str = "CNY"


class CloudProvider(ABC):
    def __init__(self, account_config: dict):
        self.name: str = account_config["name"]
        self.provider: str = account_config["provider"]
        self.ak: str = account_config["ak"]
        self.sk: str = account_config["sk"]
        self.regions: list[str] = account_config.get("regions", [])

    @abstractmethod
    def get_instances(self, region: str) -> list[Instance]:
        """获取指定 region 的所有运行中实例"""

    @abstractmethod
    def get_metrics(self, instance_id: str, region: str, hours: int) -> MetricData:
        """获取单个实例 hours 小时内监控均值"""

    def get_expiring_resources(self, region: str, days: int = 30) -> list[ExpiringResource]:
        """默认实现：从 get_instances() 过滤包年包月且在 days 天内到期的 ECS 实例"""
        result: list[ExpiringResource] = []
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        for inst in self.get_instances(region):
            if not inst.expire_time:
                continue
            exp = _parse_expire_dt(inst.expire_time)
            if exp and now <= exp <= cutoff:
                result.append(ExpiringResource(
                    resource_id=inst.instance_id,
                    name=inst.name,
                    resource_type="ECS",
                    region=inst.region,
                    project=inst.project,
                    expire_time=exp.strftime("%Y-%m-%d %H:%M:%S"),
                    charging_mode=inst.charging_mode,
                    status=inst.status,
                ))
        return result

    def get_balance(self) -> AccountBalance | None:
        """获取账户余额，默认返回 None（不支持或未实现）"""
        return None

    def get_costs(self, year: int, month: int) -> list[CostRecord]:
        """获取指定月份的项目费用明细，默认返回空列表（子类按需实现）"""
        return []

    def get_all_metrics_batch(self, instances: list[Instance], region: str, hours: int) -> dict[str, MetricData]:
        """并发获取所有实例监控（10 线程）。子类可重写以实现批量 API 优化。"""
        result: dict[str, MetricData] = {}
        if not instances:
            return result

        def _fetch(inst: Instance) -> tuple[str, MetricData]:
            try:
                return inst.instance_id, self.get_metrics(inst.instance_id, region, hours)
            except Exception as e:
                print(f"[{self.name}] 获取监控失败 {inst.name}({inst.instance_id}): {e}")
                return inst.instance_id, MetricData()

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_fetch, inst): inst for inst in instances}
            for future in as_completed(futures):
                instance_id, metric = future.result()
                result[instance_id] = metric
        return result
