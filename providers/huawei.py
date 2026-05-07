from __future__ import annotations
import hashlib
import time
from datetime import datetime, timedelta

from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkecs.v2 import EcsClient, ListServersDetailsRequest
from huaweicloudsdkecs.v2.region.ecs_region import EcsRegion
from huaweicloudsdkces.v1 import CesClient, ShowMetricDataRequest, ListMetricsRequest
from huaweicloudsdkces.v1.region.ces_region import CesRegion
from huaweicloudsdkeps.v1 import EpsClient, ListEnterpriseProjectRequest
from huaweicloudsdkeps.v1.region.eps_region import EpsRegion

from providers.base import CloudProvider, Instance, MetricData, ExpiringResource, AccountBalance, CostRecord, _parse_expire_dt

# 华为云 CES disk_usedPercent 的 mount_point 维度值是挂载路径的 MD5 hash
# 预计算常用路径的 hash 用于反向解码显示标签
_MOUNT_HASH_TABLE: dict[str, str] = {
    hashlib.md5(p.encode()).hexdigest(): p for p in [
        "/", "/data", "/data1", "/data2", "/data3", "/data4",
        "/home", "/var", "/tmp", "/boot", "/opt", "/app",
        "/mnt", "/nfs", "/logs", "/srv", "/disk1", "/disk2",
        "/disk3", "/disk4", "/vol1", "/vol2",
        "/dev/shm", "/run", "/sys/fs/cgroup",
        # Oracle / 中间件常用路径
        "/u01", "/u02", "/u01/app", "/u02/app",
        "/oracle", "/mysql", "/redis", "/mongodb",
        "/kafka", "/zookeeper", "/elasticsearch", "/hadoop",
        # 业务常用路径
        "/backup", "/archive", "/log", "/logs1", "/logs2",
        "/opt/data", "/opt/logs", "/opt/app",
        "/var/lib/docker", "/docker",
        "/local", "/share", "/clouddrive",
    ]
}


def _decode_mount_point(hash_val: str):
    """将 MD5 hash 解码为挂载路径；未知时返回 None"""
    return _MOUNT_HASH_TABLE.get(hash_val)


_METRICS = [
    ("cpu_usage", "AGT.ECS", "cpu"),
    ("mem_usedPercent", "AGT.ECS", "mem"),
    ("disk_usedPercent", "AGT.ECS", "disk"),
    ("net_bitRecv", "AGT.ECS", "out"),
    ("net_bitSent", "AGT.ECS", "in"),
]

_HW_SERVICE_CATEGORY: dict[str, str] = {
    # 计算
    "hws.service.type.ec2": "compute",
    "hws.service.type.bms": "compute",
    "hws.service.type.cfe": "compute",
    "hws.service.type.fgs": "compute",
    "hws.service.type.cce": "compute",
    "hws.service.type.cci": "compute",
    "hws.service.type.cs":  "compute",
    # 存储
    "hws.service.type.ebs":  "storage",
    "hws.service.type.obs":  "storage",
    "hws.service.type.sfs":  "storage",
    "hws.service.type.evs":  "storage",
    "hws.service.type.dss":  "storage",
    "hws.service.type.sdrs": "storage",
    "hws.service.type.csbs": "storage",
    "hws.service.type.cbr":  "storage",
    "hws.service.type.vbs":  "storage",
    # 网络
    "hws.service.type.vpc":  "network",
    "hws.service.type.eip":  "network",
    "hws.service.type.cdn":  "network",
    "hws.service.type.elb":  "network",
    "hws.service.type.er":   "network",
    "hws.service.type.ga":   "network",
    "hws.service.type.dc":   "network",
    "hws.service.type.vpn":  "network",
    # 数据库
    "hws.service.type.rds":      "database",
    "hws.service.type.gaussdb":  "database",
    "hws.service.type.gaussdbv5":"database",
    "hws.service.type.dws":      "database",
    "hws.service.type.nosql":    "database",
    "hws.service.type.dcs":      "database",
    "hws.service.type.dds":      "database",
    "hws.service.type.css":      "database",
    "hws.service.type.dms":      "database",
}


def _hw_classify(code: str) -> str:
    return _HW_SERVICE_CATEGORY.get(code, "other")


_REGION_DISPLAY = {
    "cn-southwest-2": "西南-贵阳1",
    "cn-north-1": "华北-北京一",
    "cn-north-4": "华北-北京四",
    "cn-east-3": "华东-上海一",
    "cn-south-1": "华南-广州",
    "ap-southeast-1": "中国-香港",
    "na-mexico-1": "拉美-墨西哥城一",
    "tr-west-1": "土耳其-伊斯坦布尔",
    "sa-brazil-1": "拉美-圣保罗一",
    "me-east-1": "中东-利雅得",
    "ap-southeast-3": "亚太-新加坡",
    "cn-north-9": "华北-乌兰察布一",
}


class HuaweiProvider(CloudProvider):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._eps_map = None  # dict[str, str] | None，缓存企业项目映射
        self._bss_ecs_map = None  # resource_id -> {expire_time, auto_renew}，缓存 BSS 账单
        # region -> {instance_id -> [mount_point_hash, ...]}
        self._disk_dims_cache: dict[str, dict[str, list[str]]] = {}

    def _credentials(self) -> BasicCredentials:
        return BasicCredentials(self.ak, self.sk)

    def _global_credentials(self) -> GlobalCredentials:
        return GlobalCredentials(self.ak, self.sk)

    def _http_config(self) -> HttpConfig:
        cfg = HttpConfig.get_default_config()
        cfg.timeout = 10
        return cfg

    def _get_enterprise_project_map(self) -> dict[str, str]:
        """全局调用一次 EPS API，获取所有企业项目 id -> name 映射"""
        if self._eps_map is not None:
            return self._eps_map
        result = {"0": "default"}
        try:
            client = EpsClient.new_builder() \
                .with_credentials(self._global_credentials()) \
                .with_region(EpsRegion.value_of("cn-north-4")) \
                .with_http_config(self._http_config()) \
                .build()
            offset = 0
            while True:
                req = ListEnterpriseProjectRequest(limit=200, offset=offset)
                resp = client.list_enterprise_project(req)
                projects = resp.enterprise_projects or []
                for p in projects:
                    result[p.id] = p.name
                if len(projects) < 200:
                    break
                offset += 200
            print(f"[{self.name}] 企业项目共 {len(result)} 个")
        except Exception as e:
            print(f"[{self.name}] 获取企业项目失败（将用ID代替）: {e}")
        self._eps_map = result
        return result

    def get_balance(self) -> AccountBalance | None:
        try:
            from huaweicloudsdkbss.v2 import BssClient, ShowCustomerAccountBalancesRequest
            from huaweicloudsdkbss.v2.region.bss_region import BssRegion
        except ImportError:
            print(f"[{self.name}] BSS SDK 未安装")
            return None

        cash = 0.0
        coupon = 0.0
        credit = 0.0
        try:
            client = BssClient.new_builder() \
                .with_credentials(self._global_credentials()) \
                .with_region(BssRegion.value_of("cn-north-1")) \
                .with_http_config(self._http_config()) \
                .build()

            # 账户余额
            try:
                resp = client.show_customer_account_balances(
                    ShowCustomerAccountBalancesRequest()
                )
                for b in (resp.account_balances or []):
                    if b.measure_id == 1:  # 人民币
                        if b.account_type == 1:  # 现金账户
                            cash += float(b.amount or 0)
                    credit += float(b.credit_amount or 0)
            except Exception as e:
                print(f"[{self.name}] 查询余额失败: {e}")

            # 代金券
            try:
                from huaweicloudsdkbss.v2 import ListCouponsRequest
                req = ListCouponsRequest(
                    status_list=[1],  # 1 = 可使用
                    limit=100,
                    offset=0,
                )
                resp = client.list_coupons(req)
                for c in (resp.coupons or []):
                    coupon += float(c.coupon_amount or 0)
            except Exception as e:
                print(f"[{self.name}] 查询代金券失败: {e}")

        except Exception as e:
            print(f"[{self.name}] BSS 客户端创建失败: {e}")
            return None

        return AccountBalance(cash_balance=round(cash, 2), coupon_amount=round(coupon, 2), credit_limit=round(credit, 2), available_amount=round(cash + credit, 2))

    def get_costs(self, year: int, month: int) -> list[CostRecord]:
        """调用 BSS monthly_break_down 获取按项目+服务类型汇总的费用。
        API 返回资源明细（details），在 Python 层按 (project, service_type_code) 聚合后返回。
        金额使用 current_month_amortized_amount（摊销成本净值），与华为云官网"摊销成本分析"页面一致。
        """
        try:
            from huaweicloudsdkbss.v2 import BssClient, ListCustomerBillsMonthlyBreakDownRequest
            from huaweicloudsdkbss.v2.region.bss_region import BssRegion
        except ImportError:
            print(f"[{self.name}] BSS SDK 未安装，无法采集费用")
            return []

        try:
            client = BssClient.new_builder() \
                .with_credentials(self._global_credentials()) \
                .with_region(BssRegion.value_of("cn-north-1")) \
                .with_http_config(self._http_config()) \
                .build()
        except Exception as e:
            print(f"[{self.name}] BSS 客户端创建失败: {e}")
            return []

        shared_month = f"{year:04d}-{month:02d}"
        eps_map = self._get_enterprise_project_map()  # id -> name

        # 聚合：(proj_name, svc_code) -> {svc_name, category, amount}
        agg: dict[tuple, dict] = {}
        offset, limit = 0, 100
        total_fetched = 0

        while True:
            try:
                req = ListCustomerBillsMonthlyBreakDownRequest()
                req.shared_month = shared_month
                req.offset = offset
                req.limit = limit
                resp = client.list_customer_bills_monthly_break_down(req)
                details = resp.details or []
                total_fetched += len(details)

                for b in details:
                    proj_id = getattr(b, "enterprise_project_id", "") or "0"
                    proj_name = (
                        getattr(b, "enterprise_project_name", None)
                        or eps_map.get(proj_id, proj_id)
                        or "默认项目"
                    )
                    if proj_id == "0" or not proj_name or proj_name == "0":
                        proj_name = "默认项目"

                    svc_code = getattr(b, "service_type_code", "") or ""
                    svc_name = getattr(b, "service_type_name", svc_code) or svc_code

                    # 摊销成本净值（含退款负值），与华为云官网"摊销成本分析"页面一致
                    raw = getattr(b, "current_month_amortized_amount", None)
                    if raw is None:
                        raw = getattr(b, "amortized_cash_amount", None)
                    if raw is None:
                        continue
                    amount = float(raw)

                    key = (proj_name, svc_code)
                    if key not in agg:
                        agg[key] = {"svc_name": svc_name, "category": _hw_classify(svc_code), "amount": 0.0}
                    agg[key]["amount"] += amount

                if len(details) < limit:
                    break
                offset += limit

            except Exception as e:
                print(f"[{self.name}] BSS 月账单获取失败 {shared_month}: {e}")
                break

        records = [
            CostRecord(
                year=year,
                month=month,
                project=proj_name,
                service_type_code=svc_code,
                service_type_name=v["svc_name"],
                service_category=v["category"],
                amount=round(v["amount"], 4),
            )
            for (proj_name, svc_code), v in agg.items()
            if v["amount"] > 0
        ]
        print(f"[{self.name}] BSS 费用 {shared_month}: {total_fetched} 条明细 → {len(records)} 条聚合记录")
        return records

    def get_instances(self, region: str) -> list[Instance]:
        creds = self._credentials()
        client = EcsClient.new_builder() \
            .with_credentials(creds) \
            .with_region(EcsRegion.value_of(region)) \
            .with_http_config(self._http_config()) \
            .build()
        project_map = self._get_enterprise_project_map()
        result = []
        try:
            req = ListServersDetailsRequest()
            req.limit = 1000
            resp = client.list_servers_details(req)
            for s in (resp.servers or []):
                ips = [addr.addr for addrs in s.addresses.values() for addr in addrs]
                n_ip = ips[0] if ips else ""
                w_ip = ips[1] if len(ips) > 1 else ""
                result.append(Instance(
                    instance_id=s.id,
                    name=s.name,
                    region=_REGION_DISPLAY.get(region, region),
                    project=project_map.get(s.enterprise_project_id, s.enterprise_project_id),
                    cpus=int(s.flavor.vcpus),
                    ram=int(int(s.flavor.ram) / 1024),
                    n_ip=n_ip,
                    w_ip=w_ip,
                    status="UP" if s.status == "ACTIVE" else "DOWN",
                    os_type=s.metadata.get("os_type", ""),
                    charging_mode="包年包月" if s.metadata.get("charging_mode") == "1" else "按需计费",
                    created=s.created,
                    expire_time=getattr(s, "auto_terminate_time", "") or "",
                ))
        except exceptions.ClientRequestException as e:
            print(f"[{self.name}] 获取实例失败 region={region}: {e.error_msg}")
        return result

    def _build_bss_ecs_map(self) -> dict[str, dict]:
        """一次性拉取所有包年包月 ECS 的到期时间和续费策略（全局缓存）"""
        if self._bss_ecs_map is not None:
            return self._bss_ecs_map

        from huaweicloudsdkbss.v2 import BssClient, ListPayPerUseCustomerResourcesRequest, QueryResourcesReq
        from huaweicloudsdkbss.v2.region.bss_region import BssRegion

        _policy_map = {0: "否", 1: "是", 2: "到期转按需", 3: "否"}
        result: dict[str, dict] = {}
        try:
            bss_client = BssClient.new_builder() \
                .with_credentials(self._global_credentials()) \
                .with_region(BssRegion.value_of("cn-north-1")) \
                .with_http_config(self._http_config()) \
                .build()
            offset = 0
            limit = 100
            while True:
                body = QueryResourcesReq(
                    service_type_code="hws.service.type.ec2",
                    status_list=[2],
                    limit=limit,
                    offset=offset,
                )
                resp = bss_client.list_pay_per_use_customer_resources(
                    ListPayPerUseCustomerResourcesRequest(body=body)
                )
                for r in (resp.data or []):
                    result[r.resource_id] = {
                        "expire_time": r.expire_time or "",
                        "auto_renew": _policy_map.get(r.expire_policy, "未知"),
                    }
                if not resp.data or len(resp.data) < limit:
                    break
                offset += limit
            print(f"[{self.name}] BSS 共获取 {len(result)} 台包年包月 ECS 账单数据")
        except Exception as e:
            print(f"[{self.name}] BSS 账单数据获取失败: {e}")

        self._bss_ecs_map = result
        return result

    def _get_ecs_expiry_via_bss(self, region: str, days: int) -> list[ExpiringResource]:
        """结合 BSS 账单 + ECS 实例信息，获取包年包月 ECS 到期资源（含自动续费状态）"""
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        result: list[ExpiringResource] = []

        bss_map = self._build_bss_ecs_map()
        if not bss_map:
            return result

        project_map = self._get_enterprise_project_map()
        try:
            ecs_client = EcsClient.new_builder() \
                .with_credentials(self._credentials()) \
                .with_region(EcsRegion.value_of(region)) \
                .with_http_config(self._http_config()) \
                .build()
            req = ListServersDetailsRequest()
            req.limit = 1000
            resp = ecs_client.list_servers_details(req)
            servers = resp.servers or []
        except exceptions.ClientRequestException as e:
            print(f"[{self.name}] ECS 列表获取失败 region={region}: {e.error_msg}")
            return result

        for s in servers:
            if s.metadata.get("charging_mode") != "1":
                continue
            bss_info = bss_map.get(s.id)
            if not bss_info or not bss_info["expire_time"]:
                continue
            exp = _parse_expire_dt(bss_info["expire_time"])
            if not exp or not (now <= exp <= cutoff):
                continue
            result.append(ExpiringResource(
                resource_id=s.id,
                name=s.name,
                resource_type="ECS",
                region=_REGION_DISPLAY.get(region, region),
                project=project_map.get(s.enterprise_project_id, s.enterprise_project_id),
                expire_time=exp.strftime("%Y-%m-%d %H:%M:%S"),
                charging_mode="包年包月",
                status="UP" if s.status == "ACTIVE" else "DOWN",
                auto_renew=bss_info["auto_renew"],
            ))

        return result

    def get_expiring_resources(self, region: str, days: int = 30) -> list[ExpiringResource]:
        """查询 ECS 和 RDS 包年包月到期资源"""
        result: list[ExpiringResource] = []
        now = datetime.now()
        cutoff = now + timedelta(days=days)

        # ECS：通过 BSS 订单 API 查询实际到期时间（auto_terminate_time 字段始终为空）
        result.extend(self._get_ecs_expiry_via_bss(region, days))

        # RDS
        try:
            from huaweicloudsdkrds.v3 import RdsClient, ListInstancesRequest
            from huaweicloudsdkrds.v3.region.rds_region import RdsRegion
            creds = self._credentials()
            rds_client = RdsClient.new_builder() \
                .with_credentials(creds) \
                .with_region(RdsRegion.value_of(region)) \
                .with_http_config(self._http_config()) \
                .build()
            req = ListInstancesRequest()
            resp = rds_client.list_instances(req)
            for inst in (resp.instances or []):
                charge_info = inst.charge_info
                if not charge_info or getattr(charge_info, "charge_mode", "") != "prePaid":
                    continue
                raw_expire = getattr(charge_info, "period_end_time", None) or ""
                if not raw_expire:
                    continue
                exp = _parse_expire_dt(raw_expire)
                if exp and now <= exp <= cutoff:
                    is_ar = getattr(charge_info, "is_auto_renew", None)
                    auto_renew = "是" if is_ar is True else ("否" if is_ar is False else "未知")
                    result.append(ExpiringResource(
                        resource_id=inst.id or "",
                        name=inst.name or "",
                        resource_type="RDS",
                        region=region,
                        project="",
                        expire_time=exp.strftime("%Y-%m-%d %H:%M:%S"),
                        charging_mode="包年包月",
                        status=inst.status or "",
                        auto_renew=auto_renew,
                    ))
        except Exception as e:
            print(f"[{self.name}] RDS 到期查询失败 region={region}: {e}")
        return result

    def _build_disk_dims_cache(self, client: CesClient, region: str) -> None:
        """全量拉取该 region 的 disk_usedPercent 指标，建立 instance_id->mount_point_hashes 缓存。
        华为云 CES ListMetrics 带 dim_0 过滤对多维指标失效（仅返回单维指标），
        因此全量拉取（limit=1000）后在内存中按 instance_id 分组。
        """
        cache: dict[str, list[str]] = {}
        try:
            req = ListMetricsRequest(
                namespace="AGT.ECS",
                metric_name="disk_usedPercent",
                limit=1000,
            )
            resp = client.list_metrics(req)
            for m in (resp.metrics or []):
                inst_id = None
                mp_hash = None
                for d in (m.dimensions or []):
                    if d.name == "instance_id":
                        inst_id = d.value
                    elif d.name == "mount_point":
                        mp_hash = d.value
                if inst_id and mp_hash:
                    cache.setdefault(inst_id, [])
                    if mp_hash not in cache[inst_id]:
                        cache[inst_id].append(mp_hash)
        except Exception as e:
            print(f"[{self.name}] 加载磁盘维度缓存失败 region={region}: {e}")
        self._disk_dims_cache[region] = cache

    def _get_mount_hashes(self, client: CesClient, region: str, instance_id: str) -> list[str]:
        """获取实例的 mount_point hash 列表，使用 region 级缓存。"""
        if region not in self._disk_dims_cache:
            self._build_disk_dims_cache(client, region)
        return self._disk_dims_cache.get(region, {}).get(instance_id, [])

    def get_metrics(self, instance_id: str, region: str, hours: int) -> MetricData:
        creds = self._credentials()
        client = CesClient.new_builder() \
            .with_credentials(creds) \
            .with_region(CesRegion.value_of(region)) \
            .with_http_config(self._http_config()) \
            .build()
        result = MetricData()
        now_ms = int(time.time()) * 1000
        from_ms = now_ms - hours * 3600 * 1000
        dim_0 = f"instance_id,{instance_id}"

        for metric_name, namespace, field in _METRICS:
            try:
                if field == "disk":
                    mount_hashes = self._get_mount_hashes(client, region, instance_id)
                    if not mount_hashes:
                        continue
                    raw_details: list[dict] = []
                    for mp_hash in mount_hashes:
                        try:
                            req = ShowMetricDataRequest(
                                namespace=namespace,
                                metric_name=metric_name,
                                dim_0=dim_0,
                                dim_1=f"mount_point,{mp_hash}",
                                filter="average",
                                period=300,
                                _from=from_ms,
                                to=now_ms,
                            )
                            resp = client.show_metric_data(req)
                            data = [p.average for p in (resp.datapoints or []) if p.average is not None]
                            if not data:
                                continue
                            decoded = _decode_mount_point(mp_hash)
                            raw_details.append({
                                "device": decoded,   # None 表示未知
                                "usage": round(sum(data) / len(data), 2),
                            })
                        except Exception:
                            pass

                    if raw_details:
                        # 去重：同使用率只保留一条，优先保留有解码名称的
                        raw_details.sort(key=lambda x: (x["usage"], x["device"] is None), reverse=True)
                        seen_usage: set[float] = set()
                        deduped: list[dict] = []
                        unknown_idx = 0
                        for entry in raw_details:
                            u = entry["usage"]
                            if u in seen_usage:
                                continue
                            seen_usage.add(u)
                            if entry["device"] is None:
                                unknown_idx += 1
                                entry = {"device": f"磁盘-{unknown_idx}", "usage": u}
                            deduped.append(entry)

                        result.disk_details = deduped   # 已按 usage 降序
                        result.disk_avg = deduped[0]["usage"]
                    continue

                req = ShowMetricDataRequest(
                    namespace=namespace,
                    metric_name=metric_name,
                    dim_0=dim_0,
                    filter="average",
                    period=300,
                    _from=from_ms,
                    to=now_ms,
                )
                resp = client.show_metric_data(req)
                data = [p.average for p in (resp.datapoints or []) if p.average is not None]
                if not data:
                    continue
                avg = sum(data) / len(data)
                if field == "cpu":
                    result.cpu_avg = round(avg, 2)
                    result.cpu_max = round(max(data), 2)
                elif field == "mem":
                    result.mem_avg = round(avg, 2)
                    result.mem_max = round(max(data), 2)
                elif field == "out":
                    result.out_avg = round(avg / 1_000_000, 4)
                elif field == "in":
                    result.in_avg = round(avg / 1_000_000, 4)
            except Exception:
                pass
        return result
