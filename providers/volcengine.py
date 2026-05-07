from __future__ import annotations
import time
from datetime import datetime, timedelta

from providers.base import CloudProvider, Instance, MetricData, ExpiringResource, AccountBalance, CostRecord, _parse_expire_dt


_VOLC_SERVICE_CATEGORY: dict[str, str] = {
    # 计算
    "云服务器": "compute",
    "弹性裸金属服务器": "compute",
    "GPU云服务器": "compute",
    "容器服务": "compute",
    "函数服务": "compute",
    "开源LLM模型": "compute",
    "字节跳动大模型服务（豆包大模型）": "compute",
    # 存储
    "对象存储": "storage",
    "弹性块存储": "storage",
    "文件存储NAS": "storage",
    "云备份": "storage",
    # 网络
    "公网IP": "network",
    "负载均衡": "network",
    "NAT网关": "network",
    "云企业网": "network",
    "云企业网跨境带宽_联通": "network",
    "私有网络": "network",
    "DDoS防护": "network",
    "WAF应用防护": "network",
    "内容分发网络": "network",
    # 数据库
    "云数据库 MySQL 版": "database",
    "云数据库 PostgreSQL 版": "database",
    "云数据库 MongoDB 版": "database",
    "缓存数据库 Redis 版": "database",
    "E-MapReduce": "database",
    "消息队列 Kafka 版": "database",
    "消息队列 RocketMQ 版": "database",
}


def _volc_classify(product_zh: str) -> str:
    for k, v in _VOLC_SERVICE_CATEGORY.items():
        if k in product_zh:
            return v
    return "other"


_METRICS_CFG = [
    ("CpuTotal", "VCM_ECS", "Instance", "cpu"),
    ("MemoryUsedUtilization", "VCM_ECS", "Instance", "mem"),
    ("DiskUsageUtilization", "VCM_ECS", "Storage", "disk"),
]


class VolcengineProvider(CloudProvider):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._volc_renew_map = None  # instance_id -> "是"/"否"/"未知"

    def _get_volc_renew_map(self) -> dict[str, str]:
        """通过火山云 Billing SDK 获取所有 ECS 包年包月的自动续费状态（全局缓存）"""
        if self._volc_renew_map is not None:
            return self._volc_renew_map

        result: dict[str, str] = {}
        try:
            import volcenginesdkbilling as billing
            import volcenginesdkcore as core
            c = core.Configuration()
            c.ak, c.sk, c.region = self.ak, self.sk, "cn-beijing"
            api = billing.BILLINGApi(core.ApiClient(c))
            next_token = None
            seen_tokens: set[str] = set()
            while True:
                req = billing.ListAvailableInstancesRequest(
                    product="ECS", max_results=100, next_token=next_token
                )
                resp = api.list_available_instances(req)
                batch = resp.instance_list or []
                for inst in batch:
                    rt = inst.renew_type or ""
                    if rt == "AutoRenewal":
                        result[inst.instance_id] = "是"
                    elif rt == "ManualRenewal":
                        result[inst.instance_id] = "否"
                    else:
                        result[inst.instance_id] = "未知"
                nt = resp.next_token
                if not nt or nt in seen_tokens or len(batch) < 100:
                    break
                seen_tokens.add(nt)
                next_token = nt
            print(f"[{self.name}] 火山云获取 {len(result)} 台 ECS 续费状态")
        except Exception as e:
            print(f"[{self.name}] 火山云续费状态获取失败: {e}")

        self._volc_renew_map = result
        return result

    def get_balance(self) -> AccountBalance | None:
        try:
            import volcenginesdkbilling as billing
            import volcenginesdkcore as core
        except ImportError:
            print(f"[{self.name}] 火山云 billing SDK 未安装")
            return None

        c = core.Configuration()
        c.ak, c.sk, c.region = self.ak, self.sk, "cn-beijing"
        api = billing.BILLINGApi(core.ApiClient(c))

        # 账户余额
        cash = 0.0
        credit = 0.0
        try:
            req = billing.QueryBalanceAcctRequest()
            resp = api.query_balance_acct(req)
            cash = float(resp.available_balance or 0)
            credit = float(resp.credit_limit or 0)
        except Exception as e:
            print(f"[{self.name}] 查询余额失败: {e}")

        # 代金券
        coupon = 0.0
        try:
            offset = 0
            limit = 100
            while True:
                req = billing.ListCouponsRequest(
                    status="Normal",
                    limit=limit,
                    offset=offset,
                )
                resp = api.list_coupons(req)
                for c in (resp.list or []):
                    coupon += float(c.remaining_amount or 0)
                if not resp.list or len(resp.list) < limit:
                    break
                offset += limit
        except Exception as e:
            print(f"[{self.name}] 查询代金券失败: {e}")

        return AccountBalance(cash_balance=round(cash, 2), coupon_amount=round(coupon, 2), credit_limit=round(credit, 2), available_amount=round(cash + credit, 2))

    def get_expiring_resources(self, region: str, days: int = 30) -> list[ExpiringResource]:
        """覆盖基类，补充自动续费状态"""
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        renew_map = self._get_volc_renew_map()
        result: list[ExpiringResource] = []
        for inst in self.get_instances(region):
            if inst.charging_mode != "包年包月":
                continue
            exp = _parse_expire_dt(inst.expire_time)
            if not exp or not (now <= exp <= cutoff):
                continue
            result.append(ExpiringResource(
                resource_id=inst.instance_id,
                name=inst.name,
                resource_type="ECS",
                region=inst.region,
                project=inst.project,
                expire_time=exp.strftime("%Y-%m-%d %H:%M:%S"),
                charging_mode=inst.charging_mode,
                status=inst.status,
                auto_renew=renew_map.get(inst.instance_id, "否"),
            ))
        return result

    def _get_ecs_client(self, region: str):
        import volcenginesdkcore as core
        import volcenginesdkecs as ecs_sdk
        cfg = core.Configuration()
        cfg.ak = self.ak
        cfg.sk = self.sk
        cfg.region = region
        return ecs_sdk.ECSApi(core.ApiClient(cfg))

    def _get_monitor_client(self, region: str):
        import volcenginesdkcore as core
        import volcenginesdkcloudmonitor as cm_sdk
        cfg = core.Configuration()
        cfg.ak = self.ak
        cfg.sk = self.sk
        cfg.region = region
        return cm_sdk.CLOUDMONITORApi(core.ApiClient(cfg))

    def get_instances(self, region: str) -> list[Instance]:
        try:
            import volcenginesdkecs as ecs_sdk
            client = self._get_ecs_client(region)
            result = []
            next_token = None
            while True:
                req = ecs_sdk.DescribeInstancesRequest(max_results=100, next_token=next_token)
                resp = client.describe_instances(req)
                for h in (resp.instances or []):
                    nics = h.network_interfaces or []
                    n_ip = nics[0].primary_ip_address if nics else ""
                    w_ip = (h.eip_address.ip_address if h.eip_address else "") or ""
                    result.append(Instance(
                        instance_id=h.instance_id,
                        name=h.instance_name,
                        region=region,
                        project=h.project_name or "default",
                        cpus=h.cpus or 0,
                        ram=int((h.memory_size or 0) / 1024),
                        n_ip=n_ip,
                        w_ip=w_ip,
                        status=h.status or "",
                        os_type=h.os_type or "",
                        charging_mode="包年包月" if h.instance_charge_type == "PrePaid" else "按量付费",
                        created=str(h.created_at or ""),
                        expire_time=str(h.expired_at or ""),
                    ))
                next_token = resp.next_token
                if not next_token:
                    break
            return result
        except Exception as e:
            print(f"[{self.name}] 获取实例失败 region={region}: {e}")
            return []

    def get_metrics(self, instance_id: str, region: str, hours: int) -> MetricData:
        try:
            import volcenginesdkcloudmonitor as cm_sdk
            client = self._get_monitor_client(region)
            result = MetricData()
            end_ts = int(time.time())
            start_ts = end_ts - hours * 3600

            for metric_name, namespace, sub_namespace, field in _METRICS_CFG:
                try:
                    dim = cm_sdk.DimensionForGetMetricDataInput(name="ResourceID", value=instance_id)
                    inst = cm_sdk.InstanceForGetMetricDataInput(dimensions=[dim])
                    req = cm_sdk.GetMetricDataRequest(
                        namespace=namespace,
                        sub_namespace=sub_namespace,
                        metric_name=metric_name,
                        instances=[inst],
                        start_time=start_ts,
                        end_time=end_ts,
                        period="1m",
                    )
                    resp = client.get_metric_data(req)
                    values = []
                    d = resp.data
                    if d:
                        for r in (d.metric_data_results or []):
                            for p in (r.data_points or []):
                                if p.value is not None:
                                    values.append(p.value)
                    if not values:
                        continue
                    avg = sum(values) / len(values)
                    if field == "cpu":
                        result.cpu_avg = round(avg, 2)
                        result.cpu_max = round(max(values), 2)
                    elif field == "mem":
                        result.mem_avg = round(avg, 2)
                        result.mem_max = round(max(values), 2)
                    elif field == "disk":
                        result.disk_avg = round(avg, 2)
                        result.disk_details = [{"device": "all", "usage": round(avg, 2)}]
                    elif field == "out":
                        result.out_avg = round(avg / 1_000_000, 4)
                    elif field == "in":
                        result.in_avg = round(avg / 1_000_000, 4)
                except Exception as e:
                    print(f"[{self.name}] 指标查询失败 {metric_name} {instance_id}: {e}")
            return result
        except Exception as e:
            print(f"[{self.name}] 获取监控失败 {instance_id}: {e}")
            return MetricData()

    def get_costs(self, year: int, month: int) -> list[CostRecord]:
        """调用 Billing list_bill_detail 获取月度费用，按 (project, product_zh) 聚合返回。
        project 字段直接来自账单，与 ECS 项目名一致。
        """
        try:
            import volcenginesdkbilling as billing_sdk
            import volcenginesdkcore as core
        except ImportError:
            print(f"[{self.name}] 火山云 billing SDK 未安装")
            return []

        c = core.Configuration()
        c.ak, c.sk, c.region = self.ak, self.sk, "cn-beijing"
        api = billing_sdk.BILLINGApi(core.ApiClient(c))

        bill_period = f"{year:04d}-{month:02d}"
        agg: dict[tuple, dict] = {}
        offset, limit = 0, 100
        total_fetched = 0

        while True:
            try:
                req = billing_sdk.ListBillDetailRequest(
                    bill_period=bill_period,
                    limit=limit,
                    offset=offset,
                )
                resp = api.list_bill_detail(req)
                items = resp.list or []
                total_fetched += len(items)

                for item in items:
                    d = item.to_dict() if hasattr(item, "to_dict") else {}
                    proj = (d.get("project") or "-") .strip()
                    if not proj or proj == "-":
                        proj = "默认项目"

                    product_zh = d.get("product_zh") or d.get("product") or ""
                    amount = float(d.get("payable_amount") or 0)
                    if amount <= 0:
                        continue

                    key = (proj, product_zh)
                    if key not in agg:
                        agg[key] = {"category": _volc_classify(product_zh), "amount": 0.0}
                    agg[key]["amount"] += amount

                if len(items) < limit:
                    break
                offset += limit

            except Exception as e:
                print(f"[{self.name}] 账单获取失败 {bill_period}: {e}")
                break

        records = [
            CostRecord(
                year=year,
                month=month,
                project=proj,
                service_type_code=product_zh,
                service_type_name=product_zh,
                service_category=v["category"],
                amount=round(v["amount"], 4),
            )
            for (proj, product_zh), v in agg.items()
            if v["amount"] > 0
        ]
        print(f"[{self.name}] 账单 {bill_period}: {total_fetched} 条明细 → {len(records)} 条聚合记录")
        return records

