from __future__ import annotations
import json
import time
from datetime import datetime, timedelta

from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_ecs20140526 import models as ecs_models
from alibabacloud_cms20190101.client import Client as CmsClient
from alibabacloud_cms20190101 import models as cms_models
from alibabacloud_resourcemanager20200331.client import Client as RmClient
from alibabacloud_resourcemanager20200331 import models as rm_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

from providers.base import CloudProvider, Instance, MetricData, ExpiringResource, AccountBalance, CostRecord, _parse_expire_dt


_ALI_PRODUCT_CATEGORY: dict[str, str] = {
    # 计算
    "ecs": "compute", "eci": "compute", "fc": "compute",
    "sae": "compute", "cs": "compute", "gws": "compute",
    "ehpc": "compute", "batchcompute": "compute",
    # 存储
    "oss": "storage", "disk": "storage", "nas": "storage",
    "hybridbackup": "storage", "tablestore": "storage", "oss-cloudbox": "storage",
    # 网络
    "cdn": "network", "slb": "network", "alb": "network", "nlb": "network",
    "eip": "network", "vpc": "network", "cen": "network", "ga": "network",
    "nat": "network", "vpn": "network", "ddos": "network", "waf": "network",
    "cas": "network", "sag": "network", "privatezone": "network",
    # 数据库
    "rds": "database", "polardb": "database", "mongodb": "database",
    "kvstore": "database", "ads": "database", "drds": "database",
    "clickhouse": "database", "elasticsearch": "database", "adb": "database",
    "kafka": "database", "alikafka": "database", "mns": "database",
    "lindorm": "database", "hbase": "database", "ots": "database",
    "flink": "database", "emr": "database", "datahub": "database",
    "dts": "database", "gpdb": "database", "sls": "database",
    "selectdb": "database", "petadata": "database", "hitsdb": "database",
}


def _ali_classify(pip_code: str) -> str:
    return _ALI_PRODUCT_CATEGORY.get((pip_code or "").lower(), "other")


class AliyunProvider(CloudProvider):

    def _ecs_client(self, region: str) -> EcsClient:
        cfg = open_api_models.Config(access_key_id=self.ak, access_key_secret=self.sk)
        cfg.endpoint = f"ecs.{region}.aliyuncs.com"
        return EcsClient(cfg)

    def _cms_client(self, region: str) -> CmsClient:
        cfg = open_api_models.Config(access_key_id=self.ak, access_key_secret=self.sk)
        cfg.endpoint = f"metrics.{region}.aliyuncs.com"
        return CmsClient(cfg)

    def _get_project_map(self) -> dict[str, str]:
        """resource_group_id -> display_name"""
        try:
            cfg = open_api_models.Config(access_key_id=self.ak, access_key_secret=self.sk)
            cfg.endpoint = "resourcemanager.aliyuncs.com"
            client = RmClient(cfg)
            runtime = util_models.RuntimeOptions()
            req = rm_models.ListResourceGroupsRequest(page_size=100)
            resp = client.list_resource_groups_with_options(req, runtime)
            return {g.id: g.display_name for g in resp.body.resource_groups.resource_group}
        except Exception as e:
            print(f"[{self.name}] 获取资源组失败: {e}")
            return {}

    @staticmethod
    def _parse_ali_money(v) -> float:
        """解析阿里云 BSS 金额字符串（可能含逗号分隔符，如 '150,000.00'）"""
        if v is None:
            return 0.0
        return float(str(v).replace(",", ""))

    def get_balance(self) -> AccountBalance | None:
        try:
            from alibabacloud_bssopenapi20171214.client import Client as BssClient
            from alibabacloud_bssopenapi20171214 import models as bss_models
        except ImportError:
            print(f"[{self.name}] BSS OpenAPI SDK 未安装")
            return None

        cfg = open_api_models.Config(access_key_id=self.ak, access_key_secret=self.sk)
        cfg.endpoint = "business.aliyuncs.com"
        client = BssClient(cfg)
        runtime = util_models.RuntimeOptions()

        cash = 0.0
        credit = 0.0
        available = 0.0
        try:
            resp = client.query_account_balance_with_options(runtime)
            data = resp.body.data
            cash = self._parse_ali_money(data.available_cash_amount)
            credit = self._parse_ali_money(data.credit_amount)
            available = self._parse_ali_money(data.available_amount)
            print(f"[{self.name}] BSS余额: cash={cash}, credit={credit}, available={available}")
        except Exception as e:
            print(f"[{self.name}] 查询余额失败: {e}")

        coupon = 0.0
        try:
            req = bss_models.QueryCashCouponsRequest(effective_or_not=True)
            resp = client.query_cash_coupons_with_options(req, runtime)
            coupons = resp.body.data.cash_coupon or []
            coupon = sum(self._parse_ali_money(c.balance) for c in coupons)
        except Exception as e:
            print(f"[{self.name}] 查询代金券失败: {e}")

        return AccountBalance(cash_balance=round(cash, 2), coupon_amount=round(coupon, 2), credit_limit=round(credit, 2), available_amount=round(available, 2))

    def get_instances(self, region: str) -> list[Instance]:
        client = self._ecs_client(region)
        runtime = util_models.RuntimeOptions()
        project_map = self._get_project_map()
        result = []
        page = 1
        while True:
            try:
                req = ecs_models.DescribeInstancesRequest(
                    region_id=region, page_size=100, page_number=page
                )
                resp = client.describe_instances_with_options(req, runtime)
                instances = resp.body.instances.instance or []
                for h in instances:
                    n_ip = (h.vpc_attributes.private_ip_address.ip_address or [""])[0]
                    w_ip = (h.public_ip_address.ip_address or [""])[0]
                    result.append(Instance(
                        instance_id=h.instance_id,
                        name=h.instance_name,
                        region=region,
                        project=project_map.get(h.resource_group_id, h.resource_group_id),
                        cpus=h.cpu,
                        ram=int(h.memory / 1024),
                        n_ip=n_ip,
                        w_ip=w_ip,
                        status=h.status,
                        os_type=h.ostype,
                        charging_mode="包年包月" if h.instance_charge_type == "PrePaid" else "按量付费",
                        created=h.creation_time,
                        expire_time=h.expired_time,
                    ))
                if len(instances) < 100:
                    break
                page += 1
            except Exception as e:
                print(f"[{self.name}] 获取实例失败 region={region}: {e}")
                break
        return result

    def _rds_client(self, region: str):
        try:
            from alibabacloud_rds20140815.client import Client as RdsClient
            cfg = open_api_models.Config(access_key_id=self.ak, access_key_secret=self.sk)
            cfg.endpoint = f"rds.{region}.aliyuncs.com"
            return RdsClient(cfg)
        except ImportError:
            return None

    def _get_ecs_auto_renew_map(self, region: str, instance_ids: list[str]) -> dict[str, str]:
        """批量查询 ECS 自动续费状态，返回 {instance_id: "是"/"否"}"""
        result: dict[str, str] = {}
        if not instance_ids:
            return result
        try:
            client = self._ecs_client(region)
            runtime = util_models.RuntimeOptions()
            # API 最多接受 100 个 ID（逗号分隔）
            for i in range(0, len(instance_ids), 100):
                chunk = instance_ids[i:i + 100]
                req = ecs_models.DescribeInstanceAutoRenewAttributeRequest(
                    region_id=region,
                    instance_id=",".join(chunk),
                )
                resp = client.describe_instance_auto_renew_attribute_with_options(req, runtime)
                attrs = (resp.body.instance_renew_attributes.instance_renew_attribute or [])
                for item in attrs:
                    result[item.instance_id] = "是" if item.auto_renew_enabled else "否"
        except Exception as e:
            print(f"[{self.name}] 查询 ECS 自动续费失败 region={region}: {e}")
        return result

    def get_expiring_resources(self, region: str, days: int = 30) -> list[ExpiringResource]:
        result: list[ExpiringResource] = []
        now = datetime.now()
        cutoff = now + timedelta(days=days)

        # ECS 到期
        expiring_ecs = []
        for inst in self.get_instances(region):
            if not inst.expire_time:
                continue
            exp = _parse_expire_dt(inst.expire_time)
            if exp and now <= exp <= cutoff:
                expiring_ecs.append((inst, exp))

        # 批量获取自动续费状态
        ar_map = self._get_ecs_auto_renew_map(region, [inst.instance_id for inst, _ in expiring_ecs])

        for inst, exp in expiring_ecs:
            result.append(ExpiringResource(
                resource_id=inst.instance_id,
                name=inst.name,
                resource_type="ECS",
                region=inst.region,
                project=inst.project,
                expire_time=exp.strftime("%Y-%m-%d %H:%M:%S"),
                charging_mode=inst.charging_mode,
                status=inst.status,
                auto_renew=ar_map.get(inst.instance_id, "未知"),
            ))

        # RDS 到期
        rds = self._rds_client(region)
        if rds is None:
            return result
        try:
            from alibabacloud_rds20140815 import models as rds_models
            runtime = util_models.RuntimeOptions()
            page = 1
            while True:
                req = rds_models.DescribeDBInstancesRequest(
                    region_id=region,
                    page_size=100,
                    page_number=page,
                    pay_type="Prepaid",
                )
                resp = rds.describe_dbinstances_with_options(req, runtime)
                items = (resp.body.items.d_binstance or []) if resp.body.items else []
                for db in items:
                    raw_expire = getattr(db, "expire_time", None) or ""
                    if not raw_expire:
                        continue
                    exp = _parse_expire_dt(raw_expire)
                    if exp and now <= exp <= cutoff:
                        result.append(ExpiringResource(
                            resource_id=db.d_binstance_id or "",
                            name=db.d_binstance_description or db.d_binstance_id or "",
                            resource_type="RDS",
                            region=region,
                            project="",
                            expire_time=exp.strftime("%Y-%m-%d %H:%M:%S"),
                            charging_mode="包年包月",
                            status=db.d_binstance_status or "",
                        ))
                if len(items) < 100:
                    break
                page += 1
        except Exception as e:
            print(f"[{self.name}] RDS 到期查询失败 region={region}: {e}")

        return result

    def get_metrics(self, instance_id: str, region: str, hours: int) -> MetricData:
        """单实例查询，批量时由 get_all_metrics_batch 的缓存结果代替"""
        batch = self._fetch_region_metrics(region, hours)
        return batch.get(instance_id, MetricData())

    def get_all_metrics_batch(self, instances: list[Instance], region: str, hours: int) -> dict[str, MetricData]:
        batch = self._fetch_region_metrics(region, hours)
        return {inst.instance_id: batch.get(inst.instance_id, MetricData()) for inst in instances}

    def _fetch_region_metrics(self, region: str, hours: int) -> dict[str, MetricData]:
        """批量拉取一个 region 内所有实例的监控（一次 API 调用覆盖全区域）"""
        client = self._cms_client(region)
        runtime = util_models.RuntimeOptions()
        result: dict[str, MetricData] = {}

        end_ms = int(time.time() * 1000)
        start_ms = end_ms - hours * 3600 * 1000
        period = str(min(hours * 3600, 3600))  # 最大 1h 粒度

        # CPU、内存、网络 用 DescribeMetricTop（批量拉取性能好）
        metrics_cfg = [
            ("CPUUtilization", "acs_ecs_dashboard", "cpu"),
            ("memory_usedutilization", "acs_ecs_dashboard", "mem"),
            ("networkout_rate", "acs_ecs_dashboard", "out"),
            ("networkin_rate", "acs_ecs_dashboard", "in"),
        ]

        for metric_name, namespace, field in metrics_cfg:
            try:
                req = cms_models.DescribeMetricTopRequest(
                    metric_name=metric_name,
                    namespace=namespace,
                    period=period,
                    orderby="Average",
                    length="1000",
                    start_time=str(start_ms),
                    end_time=str(end_ms),
                )
                resp = client.describe_metric_top_with_options(req, runtime)
                datapoints = json.loads(resp.body.datapoints or "[]")
                for dp in datapoints:
                    iid = dp.get("instanceId", "")
                    if not iid:
                        continue
                    if iid not in result:
                        result[iid] = MetricData()
                    avg = float(dp.get("Average", 0))
                    maximum = float(dp.get("Maximum", 0))
                    if field == "cpu":
                        result[iid].cpu_avg = round(avg, 2)
                        result[iid].cpu_max = round(maximum, 2)
                    elif field == "mem":
                        result[iid].mem_avg = round(avg, 2)
                        result[iid].mem_max = round(maximum, 2)
                    elif field == "out":
                        result[iid].out_avg = round(avg / 1_000_000, 4)
                    elif field == "in":
                        result[iid].in_avg = round(avg / 1_000_000, 4)
            except Exception as e:
                print(f"[{self.name}] 指标查询失败 {metric_name} region={region}: {e}")

        # 磁盘 用 DescribeMetricList 获取逐磁盘（设备）数据
        try:
            disk_map: dict[str, dict[str, float]] = {}  # {instance_id: {device: usage}}
            next_token = None
            while True:
                req = cms_models.DescribeMetricListRequest(
                    namespace="acs_ecs_dashboard",
                    metric_name="diskusage_utilization",
                    period=period,
                    start_time=str(start_ms),
                    end_time=str(end_ms),
                    length="1000",
                )
                if next_token:
                    req.next_token = next_token
                resp = client.describe_metric_list_with_options(req, runtime)
                datapoints = json.loads(resp.body.datapoints or "[]")
                for dp in datapoints:
                    iid = dp.get("instanceId", "")
                    device = dp.get("device", "") or dp.get("diskname", "unknown")
                    avg = float(dp.get("Average", 0))
                    if iid:
                        if iid not in disk_map:
                            disk_map[iid] = {}
                        if device not in disk_map[iid] or avg > disk_map[iid][device]:
                            disk_map[iid][device] = avg
                next_token = getattr(resp.body, "next_token", None) or ""
                if not next_token or len(datapoints) < 1000:
                    break
            for iid, devices in disk_map.items():
                if iid not in result:
                    result[iid] = MetricData()
                result[iid].disk_details = [
                    {"device": d, "usage": round(u, 2)}
                    for d, u in sorted(devices.items())
                ]
                result[iid].disk_avg = round(max(devices.values()), 2) if devices else 0.0
        except Exception as e:
            print(f"[{self.name}] 磁盘指标查询失败 region={region}: {e}")

        return result

    def get_costs(self, year: int, month: int) -> list[CostRecord]:
        """调用 BSS QueryInstanceBill 获取月度实例级账单，按 (资源组/项目, pip_code) 聚合。
        资源组即阿里云资源组（ResourceGroup），为用户自定义中文名称，默认分组记为"默认项目"。
        """
        try:
            from alibabacloud_bssopenapi20171214.client import Client as BssClient
            from alibabacloud_bssopenapi20171214 import models as bss_models
        except ImportError:
            print(f"[{self.name}] BSS OpenAPI SDK 未安装，无法采集费用")
            return []

        cfg = open_api_models.Config(access_key_id=self.ak, access_key_secret=self.sk)
        cfg.endpoint = "business.aliyuncs.com"
        client = BssClient(cfg)
        runtime = util_models.RuntimeOptions()

        billing_cycle = f"{year:04d}-{month:02d}"
        project_map = self._get_project_map()  # resource_group_id -> display_name

        agg: dict[tuple, dict] = {}
        page, page_size = 1, 300
        total_fetched = 0

        while True:
            try:
                req = bss_models.QueryInstanceBillRequest(
                    billing_cycle=billing_cycle,
                    page_num=page,
                    page_size=page_size,
                )
                resp = client.query_instance_bill_with_options(req, runtime)
                data = resp.body.data if resp.body else None
                items = (data.items.item if data and data.items else []) or []
                total_fetched += len(items)

                for item in items:
                    rg = getattr(item, "resource_group", None) or ""
                    proj = project_map.get(rg, rg) if rg else "默认项目"
                    if not proj or not proj.strip():
                        proj = "默认项目"

                    pip_code = (getattr(item, "pip_code", None) or "").lower()
                    product_name = getattr(item, "product_name", None) or pip_code
                    amount = float(getattr(item, "pretax_amount", 0) or 0)
                    if amount <= 0:
                        continue

                    key = (proj, pip_code)
                    if key not in agg:
                        agg[key] = {"name": product_name, "category": _ali_classify(pip_code), "amount": 0.0}
                    agg[key]["amount"] += amount

                if not data or (data.total_count or 0) <= page * page_size:
                    break
                page += 1

            except Exception as e:
                print(f"[{self.name}] BSS 账单获取失败 {billing_cycle}: {e}")
                break

        records = [
            CostRecord(
                year=year, month=month,
                project=proj,
                service_type_code=pip_code,
                service_type_name=v["name"],
                service_category=v["category"],
                amount=round(v["amount"], 4),
            )
            for (proj, pip_code), v in agg.items()
            if v["amount"] > 0
        ]
        print(f"[{self.name}] 阿里云账单 {billing_cycle}: {total_fetched} 条明细 → {len(records)} 条聚合")
        return records
