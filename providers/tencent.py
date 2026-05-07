from __future__ import annotations
import time
from datetime import datetime, timedelta

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.cvm.v20170312 import cvm_client, models as cvm_models
from tencentcloud.monitor.v20180724 import monitor_client, models as monitor_models
from tencentcloud.tag.v20180813 import tag_client, models as tag_models

from providers.base import CloudProvider, Instance, MetricData, ExpiringResource, AccountBalance, CostRecord, _parse_expire_dt


_TENCENT_KW_CATEGORY: list[tuple[str, list[str]]] = [
    ("compute", ["云服务器", "轻量应用", "容器服务", "云函数", "弹性容器", "边缘计算", "批量计算", "高性能计算", "黑石"]),
    ("storage", ["云硬盘", "对象存储", "文件存储", "归档存储", "数据万象", "存储"]),
    ("network", ["负载均衡", "内容分发网络", "CDN", "公网IP", "NAT网关", "VPN连接", "专线接入",
                 "全球应用加速", "防火墙", "DDoS", "安全加速", "SSL证书", "带宽包"]),
    ("database", ["云数据库", "数据库", "Redis", "MongoDB", "Elasticsearch", "Kafka",
                  "消息队列", "数据仓库", "数据传输", "大数据", "流计算", "数据集成",
                  "数据订阅", "TDSQL", "ClickHouse"]),
]


def _tencent_classify(business_code_name: str) -> str:
    for cat, keywords in _TENCENT_KW_CATEGORY:
        for kw in keywords:
            if kw in (business_code_name or ""):
                return cat
    return "other"


class TencentProvider(CloudProvider):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._project_map: dict[str, str] | None = None
        # {instance_id: [("系统盘(50G)", "disk-xxx"), ("数据盘1(100G)", "disk-yyy")]}
        self._disk_id_map: dict[str, list[tuple[str, str]]] = {}

    def _cred(self):
        return credential.Credential(self.ak, self.sk)

    def _get_project_map(self) -> dict[str, str]:
        if self._project_map is not None:
            return self._project_map
        result = {"0": "默认项目"}
        try:
            from tencentcloud.account.v20230817 import account_client
        except ImportError:
            pass
        try:
            cred = self._cred()
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            hp = HttpProfile(reqTimeout=15)
            cp = ClientProfile(httpProfile=hp)
            tc = tag_client.TagClient(cred, "ap-beijing", cp)
            req = tag_models.DescribeProjectsRequest()
            req.AllList = 1
            req.Limit = 1000
            req.Offset = 0
            resp = tc.DescribeProjects(req)
            for p in (resp.Projects or []):
                result[str(p.ProjectId)] = p.ProjectName
            print(f"[{self.name}] 腾讯云项目数: {len(result)}")
        except Exception as e:
            print(f"[{self.name}] 获取项目列表失败（将用ID代替）: {e}")
        self._project_map = result
        return result

    def _cache_disk_ids(self, instance_id: str, h) -> None:
        """从 CVM 实例对象中提取系统盘和数据盘 ID，缓存供后续监控查询使用"""
        disks: list[tuple[str, str]] = []
        sys_disk = getattr(h, "SystemDisk", None)
        if sys_disk and getattr(sys_disk, "DiskId", None):
            size = getattr(sys_disk, "DiskSize", 0) or 0
            disks.append((f"系统盘({size}G)", sys_disk.DiskId))
        for i, d in enumerate(getattr(h, "DataDisks", None) or []):
            if getattr(d, "DiskId", None):
                size = getattr(d, "DiskSize", 0) or 0
                disks.append((f"数据盘{i + 1}({size}G)", d.DiskId))
        if disks:
            self._disk_id_map[instance_id] = disks

    def get_balance(self) -> AccountBalance | None:
        try:
            from tencentcloud.billing.v20180709 import billing_client, models as billing_models
        except ImportError:
            print(f"[{self.name}] 腾讯云 billing SDK 未安装")
            return None

        cash = 0.0
        coupon = 0.0
        credit = 0.0
        owe = 0.0
        try:
            cred = self._cred()
            client = billing_client.BillingClient(cred, "ap-guangzhou")
            req = billing_models.DescribeAccountBalanceRequest()
            resp = client.DescribeAccountBalance(req)

            cash = float(resp.CashAccountBalance or 0) / 100.0
            credit = float(resp.CreditAmount or 0) / 100.0
            owe = float(resp.OweAmount or 0) / 100.0
            print(f"[{self.name}] BSS余额: cash={cash}, credit={credit}, owe={owe}, real_balance={resp.RealBalance}")
        except Exception as e:
            print(f"[{self.name}] 查询余额失败: {e}")

        return AccountBalance(cash_balance=round(cash, 2), coupon_amount=round(coupon, 2), credit_limit=round(credit, 2), owe_amount=round(owe, 2), available_amount=round(cash + credit - owe, 2))

    def get_instances(self, region: str) -> list[Instance]:
        cred = self._cred()
        client = cvm_client.CvmClient(cred, region)
        result = []
        offset = 0
        limit = 100
        while True:
            try:
                req = cvm_models.DescribeInstancesRequest()
                req.Offset = offset
                req.Limit = limit
                resp = client.DescribeInstances(req)
                instances = resp.InstanceSet or []
                project_map = self._get_project_map()
                for h in instances:
                    n_ip = h.PrivateIpAddresses[0] if h.PrivateIpAddresses else ""
                    w_ip = h.PublicIpAddresses[0] if h.PublicIpAddresses else ""
                    pid = str(h.Placement.ProjectId) if h.Placement else "0"
                    result.append(Instance(
                        instance_id=h.InstanceId,
                        name=h.InstanceName,
                        region=region,
                        project=project_map.get(pid, pid),
                        cpus=h.CPU,
                        ram=int(h.Memory / 1024),
                        n_ip=n_ip,
                        w_ip=w_ip,
                        status=h.InstanceState,
                        os_type=h.OsName or "",
                        charging_mode="包年包月" if h.InstanceChargeType == "PREPAID" else "按量付费",
                        created=h.CreatedTime or "",
                        expire_time=h.ExpiredTime or "",
                    ))
                    self._cache_disk_ids(h.InstanceId, h)
                if len(instances) < limit:
                    break
                offset += limit
            except TencentCloudSDKException as e:
                print(f"[{self.name}] 获取实例失败 region={region}: {e.message}")
                break
        return result

    def get_expiring_resources(self, region: str, days: int = 30) -> list[ExpiringResource]:
        result: list[ExpiringResource] = []
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        cred = self._cred()
        client = cvm_client.CvmClient(cred, region)
        offset = 0
        while True:
            try:
                req = cvm_models.DescribeInstancesRequest()
                req.Offset = offset
                req.Limit = 100
                req.Filters = [{"Name": "instance-charge-type", "Values": ["PREPAID"]}]
                resp = client.DescribeInstances(req)
                instances = resp.InstanceSet or []
                project_map = self._get_project_map()
                for h in instances:
                    raw_expire = h.ExpiredTime or ""
                    if not raw_expire:
                        continue
                    exp = _parse_expire_dt(raw_expire)
                    if exp and now <= exp <= cutoff:
                        pid = str(h.Placement.ProjectId) if h.Placement else "0"
                        renew_flag = getattr(h, "RenewFlag", "") or ""
                        if renew_flag == "NOTIFY_AND_AUTO_RENEW":
                            auto_renew = "是"
                        elif renew_flag in ("NOTIFY_AND_MANUAL_RENEW", "DISABLE_NOTIFY_AND_MANUAL_RENEW"):
                            auto_renew = "否"
                        else:
                            auto_renew = "未知"
                        result.append(ExpiringResource(
                            resource_id=h.InstanceId,
                            name=h.InstanceName,
                            resource_type="CVM",
                            region=region,
                            project=project_map.get(pid, pid),
                            expire_time=exp.strftime("%Y-%m-%d %H:%M:%S"),
                            charging_mode="包年包月",
                            status=h.InstanceState or "",
                            auto_renew=auto_renew,
                        ))
                if len(instances) < 100:
                    break
                offset += 100
            except TencentCloudSDKException as e:
                print(f"[{self.name}] CVM 到期查询失败 region={region}: {e.message}")
                break
        return result

    def _query_cvm_metric(self, client, instance_id: str, metric_name: str,
                          start_time: str, end_time: str, period: int) -> list[float]:
        req = monitor_models.GetMonitorDataRequest()
        req.Namespace = "QCE/CVM"
        req.MetricName = metric_name
        req.Instances = [{"Dimensions": [{"Name": "InstanceId", "Value": instance_id}]}]
        req.Period = period
        req.StartTime = start_time
        req.EndTime = end_time
        resp = client.GetMonitorData(req)
        points = resp.DataPoints[0].Values if resp.DataPoints else []
        return [v for v in points if v is not None]

    def _query_cbs_disk_usage(self, client, disk_id: str,
                              start_time: str, end_time: str, period: int) -> float | None:
        """查询单块 CBS 磁盘的使用率均值"""
        try:
            req = monitor_models.GetMonitorDataRequest()
            req.Namespace = "QCE/BLOCK_STORAGE"
            req.MetricName = "DiskUsage"
            req.Instances = [{"Dimensions": [{"Name": "diskId", "Value": disk_id}]}]
            req.Period = period
            req.StartTime = start_time
            req.EndTime = end_time
            resp = client.GetMonitorData(req)
            points = resp.DataPoints[0].Values if resp.DataPoints else []
            data = [v for v in points if v is not None]
            return round(sum(data) / len(data), 2) if data else None
        except Exception:
            return None

    def get_metrics(self, instance_id: str, region: str, hours: int) -> MetricData:
        cred = self._cred()
        client = monitor_client.MonitorClient(cred, region)
        result = MetricData()
        end_ts = int(time.time())
        start_ts = end_ts - hours * 3600
        start_time = time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime(start_ts))
        end_time = time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime(end_ts))
        period = 3600

        # CPU / 内存 / 网络
        non_disk_cfg = [
            ("CPUUsage", "cpu"),
            ("MemUsage", "mem"),
            ("WanOuttraffic", "out"),
            ("WanIntraffic", "in"),
        ]
        for metric_name, field in non_disk_cfg:
            try:
                data = self._query_cvm_metric(client, instance_id, metric_name,
                                              start_time, end_time, period)
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
            except Exception as e:
                print(f"[{self.name}] 指标查询失败 {metric_name} {instance_id}: {e}")

        # 磁盘：逐盘查询 CBS（QCE/BLOCK_STORAGE）
        disk_items = self._disk_id_map.get(instance_id, [])
        if disk_items:
            disk_details = []
            for label, disk_id in disk_items:
                usage = self._query_cbs_disk_usage(client, disk_id, start_time, end_time, period)
                if usage is not None:
                    disk_details.append({"device": label, "usage": usage})
            if disk_details:
                result.disk_details = disk_details
                result.disk_avg = round(max(d["usage"] for d in disk_details), 2)
                return result
            # CBS 无数据时 fallback 到 CvmDiskUsage
        try:
            data = self._query_cvm_metric(client, instance_id, "CvmDiskUsage",
                                          start_time, end_time, period)
            if data:
                avg = round(sum(data) / len(data), 2)
                result.disk_avg = avg
                result.disk_details = [{"device": "系统盘", "usage": avg}]
        except Exception as e:
            print(f"[{self.name}] CvmDiskUsage 查询失败 {instance_id}: {e}")

        return result

    def get_costs(self, year: int, month: int) -> list[CostRecord]:
        """调用腾讯云 DescribeBillResourceSummary 获取月度资源级账单，
        按 (项目名称, 产品名称) 聚合。ProjectName 字段直接返回中文项目名。
        """
        try:
            from tencentcloud.billing.v20180709 import billing_client, models as billing_models
        except ImportError:
            print(f"[{self.name}] 腾讯云 billing SDK 未安装，无法采集费用")
            return []

        bill_month = f"{year:04d}-{month:02d}"
        cred = self._cred()
        client = billing_client.BillingClient(cred, "ap-guangzhou")

        agg: dict[tuple, dict] = {}
        offset, limit = 0, 1000
        total_fetched = 0

        while True:
            try:
                req = billing_models.DescribeBillResourceSummaryRequest()
                req.Month = bill_month
                req.Offset = offset
                req.Limit = limit
                req.NeedRecordNum = 1
                resp = client.DescribeBillResourceSummary(req)
                items = resp.ResourceSummarySet or []
                total_fetched += len(items)

                for item in items:
                    proj = (getattr(item, "ProjectName", None) or "").strip() or "默认项目"
                    business_code = getattr(item, "BusinessCode", None) or ""
                    business_name = getattr(item, "BusinessCodeName", None) or business_code
                    amount = float(getattr(item, "RealTotalCost", 0) or 0)
                    if amount <= 0:
                        continue

                    key = (proj, business_code)
                    if key not in agg:
                        agg[key] = {"name": business_name, "category": _tencent_classify(business_name), "amount": 0.0}
                    agg[key]["amount"] += amount

                total = getattr(resp, "Total", None) or 0
                if len(items) < limit or (total and total_fetched >= total):
                    break
                offset += limit

            except TencentCloudSDKException as e:
                print(f"[{self.name}] 腾讯云账单获取失败 {bill_month}: {e.message}")
                break
            except Exception as e:
                print(f"[{self.name}] 腾讯云账单获取失败 {bill_month}: {e}")
                break

        records = [
            CostRecord(
                year=year, month=month,
                project=proj,
                service_type_code=biz_code,
                service_type_name=v["name"],
                service_category=v["category"],
                amount=round(v["amount"], 4),
            )
            for (proj, biz_code), v in agg.items()
            if v["amount"] > 0
        ]
        print(f"[{self.name}] 腾讯云账单 {bill_month}: {total_fetched} 条明细 → {len(records)} 条聚合")
        return records
