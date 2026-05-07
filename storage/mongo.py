import time
from datetime import datetime, timedelta
from typing import Optional

import pymongo
from bson import ObjectId

from providers.base import Instance, MetricData


class MongoStore:
    def __init__(self, host: str, port: int, database: str):
        self._client = pymongo.MongoClient(f"mongodb://{host}:{port}/")
        self._db = self._client[database]

    # ── 实例信息 ──────────────────────────────────────────────────────────────

    def upsert_instance(self, cloud_name: str, provider: str, inst: Instance, update_time: str):
        doc = {
            "cloud": cloud_name,
            "provider": provider,
            "instance_id": inst.instance_id,
            "name": inst.name,
            "region": inst.region,
            "project": inst.project,
            "group": inst.group,
            "last_group": inst.last_group,
            "manager": inst.manager,
            "cpus": inst.cpus,
            "ram": inst.ram,
            "n_ip": inst.n_ip,
            "w_ip": inst.w_ip,
            "status": inst.status,
            "os_type": inst.os_type,
            "charging_mode": inst.charging_mode,
            "created": inst.created,
            "expire_time": inst.expire_time,
            "update_time": update_time,
        }
        self._db["instances"].update_one(
            {"cloud": cloud_name, "instance_id": inst.instance_id},
            {"$set": doc},
            upsert=True,
        )

    def update_instance_disk_details(self, cloud_name: str, instance_id: str, disk_details: list):
        self._db["instances"].update_one(
            {"cloud": cloud_name, "instance_id": instance_id},
            {"$set": {"disk_details": disk_details}},
        )

    def clean_stale_instances(self, cloud_name: str, update_time: str, interval_hours: int = 5):
        """删除本次采集未刷新的过期实例"""
        col = self._db["instances"]
        threshold = (datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S") - timedelta(hours=interval_hours)).strftime("%Y-%m-%d %H:%M:%S")
        col.delete_many({"cloud": cloud_name, "update_time": {"$lt": threshold}})

    # ── 监控数据 ──────────────────────────────────────────────────────────────

    def insert_metric(self, cloud_name: str, provider: str, inst: Instance,
                      m: MetricData, hours: int, update_time: str):
        doc = {
            "cloud": cloud_name,
            "provider": provider,
            "instance_id": inst.instance_id,
            "name": inst.name,
            "region": inst.region,
            "project": inst.project,
            "group": inst.group,
            "last_group": inst.last_group,
            "manager": inst.manager,
            "cpus": inst.cpus,
            "ram": inst.ram,
            "n_ip": inst.n_ip,
            "w_ip": inst.w_ip,
            "hours": hours,
            "cpu_avg": m.cpu_avg,
            "cpu_max": m.cpu_max,
            "mem_avg": m.mem_avg,
            "mem_max": m.mem_max,
            "disk_avg": m.disk_avg,
            "disk_details": m.disk_details,
            "out_avg": m.out_avg,
            "in_avg": m.in_avg,
            "update_time": update_time,
        }
        self._db["metrics"].insert_one(doc)

    def record_collect_time(self, update_time: str):
        self._db["collect_time"].insert_one({"time": update_time})

    def clean_old_metrics(self, keep_days: int = 60):
        cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d %H:%M:%S")
        times_to_delete = [
            i["time"] for i in self._db["collect_time"].find({"time": {"$lt": cutoff}})
        ]
        if times_to_delete:
            self._db["metrics"].delete_many({"update_time": {"$in": times_to_delete}})
            self._db["collect_time"].delete_many({"time": {"$in": times_to_delete}})

    # ── 查询 ─────────────────────────────────────────────────────────────────

    def get_recent_collect_times(self, n: int) -> list[str]:
        docs = self._db["collect_time"].find().sort("time", -1).limit(n)
        return [d["time"] for d in docs]

    _METRICS_SORT_FIELDS = {
        "name", "provider", "region", "project", "group", "last_group", "manager",
        "cpus", "ram", "n_ip", "w_ip",
        "cpu_avg", "cpu_max", "mem_avg", "mem_max", "disk_avg", "out_avg", "in_avg",
    }

    def query_metrics(self, days: int, filters: dict,
                      sort_field: str = "cpu_avg", sort_order: str = "desc") -> list[dict]:
        """
        按天数聚合，返回每台机器的均值。
        filters 支持: cloud, provider, region, project, group
        """
        times = self.get_recent_collect_times(days)
        if not times:
            return []

        match: dict = {"update_time": {"$in": times}}
        for key in ("cloud", "provider", "region", "project", "group"):
            if filters.get(key):
                match[key] = filters[key]
        if filters.get("name"):
            match["name"] = {"$regex": filters["name"], "$options": "i"}
        if filters.get("ip"):
            ip_pat = {"$regex": filters["ip"], "$options": "i"}
            match["$or"] = [{"n_ip": ip_pat}, {"w_ip": ip_pat}]

        sf = sort_field if sort_field in self._METRICS_SORT_FIELDS else "cpu_avg"
        sd = -1 if sort_order == "desc" else 1

        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": {"instance_id": "$instance_id", "cloud": "$cloud"},
                "name": {"$last": "$name"},
                "cloud": {"$last": "$cloud"},
                "provider": {"$last": "$provider"},
                "region": {"$last": "$region"},
                "project": {"$last": "$project"},
                "group": {"$last": "$group"},
                "last_group": {"$last": "$last_group"},
                "manager": {"$last": "$manager"},
                "cpus": {"$last": "$cpus"},
                "ram": {"$last": "$ram"},
                "n_ip": {"$last": "$n_ip"},
                "w_ip": {"$last": "$w_ip"},
                "cpu_avg": {"$avg": "$cpu_avg"},
                "cpu_max": {"$max": "$cpu_max"},
                "mem_avg": {"$avg": "$mem_avg"},
                "mem_max": {"$max": "$mem_max"},
                "disk_avg": {"$avg": "$disk_avg"},
                "out_avg": {"$avg": "$out_avg"},
                "in_avg": {"$avg": "$in_avg"},
            }},
            {"$project": {
                "_id": 0,
                "instance_id": "$_id.instance_id",
                "cloud": "$_id.cloud",
                "name": 1, "provider": 1, "region": 1,
                "project": 1, "group": 1, "last_group": 1, "manager": 1,
                "cpus": 1, "ram": 1, "n_ip": 1, "w_ip": 1,
                "cpu_avg": {"$round": ["$cpu_avg", 2]},
                "cpu_max": {"$round": ["$cpu_max", 2]},
                "mem_avg": {"$round": ["$mem_avg", 2]},
                "mem_max": {"$round": ["$mem_max", 2]},
                "disk_avg": {"$round": ["$disk_avg", 2]},
                "out_avg": {"$round": ["$out_avg", 4]},
                "in_avg": {"$round": ["$in_avg", 4]},
            }},
            {"$sort": {sf: sd}},
        ]
        rows = list(self._db["metrics"].aggregate(pipeline))

        # 从 instances 集合取最新 disk_details（不做均值，显示当前快照）
        if rows:
            pairs = [{"instance_id": r["instance_id"], "cloud": r["cloud"]} for r in rows]
            inst_docs = list(self._db["instances"].find(
                {"$or": pairs},
                {"_id": 0, "instance_id": 1, "cloud": 1, "disk_details": 1}
            ))
            import re as _re
            _hash_re = _re.compile(r'^[0-9a-fA-F]{6,}$')

            def _clean_disk_details(raw: list) -> list:
                """过滤无法解码的 MD5 hash 条目，去重相同使用率，按使用率降序"""
                filtered = [d for d in raw if not _hash_re.match(d.get("device", ""))]
                seen: set = set()
                deduped = []
                for d in sorted(filtered, key=lambda x: x["usage"], reverse=True):
                    if d["usage"] not in seen:
                        seen.add(d["usage"])
                        deduped.append(d)
                return deduped

            disk_map = {f"{d['cloud']}:{d['instance_id']}": d.get("disk_details", []) for d in inst_docs}
            for r in rows:
                details = _clean_disk_details(disk_map.get(f"{r['cloud']}:{r['instance_id']}", []))
                r["disk_details"] = details
                if details:
                    r["disk_avg"] = round(max(d["usage"] for d in details), 2)
            # disk_avg was replaced with max(details); re-sort to restore correct order
            if sf == "disk_avg":
                rows.sort(key=lambda r: r.get("disk_avg", 0), reverse=(sd == -1))
        return rows

    def get_summary(self, days: int) -> dict:
        times = self.get_recent_collect_times(days)
        match = {"update_time": {"$in": times}} if times else {}

        total_hosts = self._db["instances"].count_documents({})
        total_projects = len(self._db["instances"].distinct("project"))

        cloud_dist = list(self._db["instances"].aggregate([
            {"$group": {"_id": "$cloud", "count": {"$sum": 1}}},
            {"$project": {"name": "$_id", "value": "$count", "_id": 0}},
        ]))

        provider_dist = list(self._db["instances"].aggregate([
            {"$group": {"_id": "$provider", "count": {"$sum": 1}}},
            {"$project": {"name": "$_id", "value": "$count", "_id": 0}},
        ]))

        cpu_buckets = _bucket_distribution(self._db, "metrics", match, "cpu_avg")
        mem_buckets = _bucket_distribution(self._db, "metrics", match, "mem_avg")

        top_projects = list(self._db["instances"].aggregate([
            {"$group": {"_id": "$project", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 15},
            {"$project": {"name": "$_id", "value": "$count", "_id": 0}},
        ]))

        return {
            "total_hosts": total_hosts,
            "total_projects": total_projects,
            "cloud_dist": cloud_dist,
            "provider_dist": provider_dist,
            "cpu_buckets": cpu_buckets,
            "mem_buckets": mem_buckets,
            "top_projects": top_projects,
        }

    # ── 项目维护 ──────────────────────────────────────────────────────────────

    def init_projects_from_excel(self, excel_path: str) -> int:
        """首次将 Excel 导入 projects 集合，已存在则跳过"""
        import os, pandas as pd
        if not os.path.exists(excel_path):
            return 0
        df = pd.read_excel(excel_path)
        count = 0
        for _, row in df.iterrows():
            vals = [str(v).strip() if str(v) != "nan" else "" for v in row]
            project = vals[0]
            if not project or project == "项目":
                continue
            self._db["projects"].update_one(
                {"project": project},
                {"$set": {
                    "project": project,
                    "group": vals[1] or "未知",
                    "last_group": vals[2] or "未知",
                    "manager": vals[3] or "未知",
                    "pms": vals[4] if len(vals) > 4 else "",
                    "cloud": vals[5] if len(vals) > 5 else "",
                }},
                upsert=True,
            )
            count += 1
        return count

    def get_all_projects(self) -> list[dict]:
        result = []
        for doc in self._db["projects"].find({}).sort("project", 1):
            doc["_id"] = str(doc["_id"])
            result.append(doc)
        return result

    @staticmethod
    def _project_id_filter(pid: str) -> dict:
        """兼容字符串和 ObjectId 两种 _id 格式"""
        try:
            return {"$or": [{"_id": ObjectId(pid)}, {"_id": pid}]}
        except Exception:
            return {"_id": pid}

    def upsert_project(self, data: dict) -> str:
        pid = data.pop("_id", None)
        doc = {k: v for k, v in data.items() if k in ("project", "group", "last_group", "manager", "pms", "cloud", "notify_email")}
        if pid:
            self._db["projects"].update_one(self._project_id_filter(pid), {"$set": doc})
            return pid
        result = self._db["projects"].insert_one(doc)
        return str(result.inserted_id)

    def delete_project(self, project_id: str) -> bool:
        r = self._db["projects"].delete_one(self._project_id_filter(project_id))
        return r.deleted_count > 0

    def get_project_map_from_db(self) -> dict[str, dict]:
        result = {}
        for doc in self._db["projects"].find():
            result[doc["project"]] = {
                "group": doc.get("group", "未知"),
                "last_group": doc.get("last_group", "未知"),
                "manager": doc.get("manager", "未知"),
                "cloud": doc.get("cloud", ""),
            }
        return result

    def refresh_project_info(self, project_map: dict) -> dict:
        """
        用最新对照表重新填充所有实例和 metrics 的 group/last_group/manager。
        project_map: {项目名: {group, last_group, manager}}
        返回 {instances_updated, metrics_updated}
        """
        inst_updated = 0
        for inst in self._db["instances"].find({}, {"_id": 1, "project": 1}):
            enrich = project_map.get(inst.get("project", ""), {})
            if not enrich:
                continue
            self._db["instances"].update_one(
                {"_id": inst["_id"]},
                {"$set": {
                    "group": enrich.get("group", "未知"),
                    "last_group": enrich.get("last_group", "未知"),
                    "manager": enrich.get("manager", "未知"),
                }}
            )
            inst_updated += 1

        m_updated = 0
        for m in self._db["metrics"].find({}, {"_id": 1, "project": 1}):
            enrich = project_map.get(m.get("project", ""), {})
            if not enrich:
                continue
            self._db["metrics"].update_one(
                {"_id": m["_id"]},
                {"$set": {
                    "group": enrich.get("group", "未知"),
                    "last_group": enrich.get("last_group", "未知"),
                    "manager": enrich.get("manager", "未知"),
                }}
            )
            m_updated += 1

        return {"instances_updated": inst_updated, "metrics_updated": m_updated}

    def get_filter_options(self) -> dict:
        return {
            "clouds": self._db["instances"].distinct("cloud"),
            "providers": self._db["instances"].distinct("provider"),
            "regions": self._db["instances"].distinct("region"),
            "projects": self._db["instances"].distinct("project"),
            "groups": [g for g in self._db["instances"].distinct("group") if g and g != "未知"],
        }


    # ── 到期资源 ──────────────────────────────────────────────────────────────

    def upsert_expiry_resource(self, r, update_time: str):
        from providers.base import ExpiringResource
        doc = {
            "resource_id": r.resource_id,
            "name": r.name,
            "resource_type": r.resource_type,
            "region": r.region,
            "project": r.project,
            "expire_time": r.expire_time,
            "charging_mode": r.charging_mode,
            "status": r.status,
            "cloud": r.cloud,
            "provider": r.provider,
            "group": r.group,
            "last_group": r.last_group,
            "manager": r.manager,
            "auto_renew": getattr(r, "auto_renew", "未知"),
            "update_time": update_time,
        }
        self._db["expiry_resources"].update_one(
            {"cloud": r.cloud, "resource_id": r.resource_id},
            {"$set": doc},
            upsert=True,
        )

    def clean_stale_expiry_resources(self, update_time: str, interval_hours: int = 5):
        threshold = (
            datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S") - timedelta(hours=interval_hours)
        ).strftime("%Y-%m-%d %H:%M:%S")
        self._db["expiry_resources"].delete_many({"update_time": {"$lt": threshold}})

    def clean_expiry_resources_for_cloud(self, cloud_name: str, update_time: str):
        """删除该账号本次采集以外的所有到期资源记录，确保实时性"""
        self._db["expiry_resources"].delete_many({
            "cloud": cloud_name,
            "update_time": {"$ne": update_time},
        })

    _EXPIRY_SORT_FIELDS = {
        "name", "resource_type", "cloud", "provider", "region",
        "expire_time", "status", "auto_renew", "days_left",
    }

    def query_expiry_resources(self, days: int, filters: dict,
                               sort_field: str = "expire_time", sort_order: str = "asc") -> list[dict]:
        now = datetime.now()
        cutoff_str = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        match: dict = {"expire_time": {"$gte": now_str, "$lte": cutoff_str}}
        for key in ("cloud", "provider", "resource_type", "group", "project", "auto_renew"):
            if filters.get(key):
                match[key] = filters[key]
        # 构建项目->通知邮箱映射，注入到每行
        project_email: dict[str, str] = {
            p.get("project", ""): p.get("notify_email", "")
            for p in self._db["projects"].find({}, {"project": 1, "notify_email": 1, "_id": 0})
            if p.get("notify_email")
        }
        sf = sort_field if sort_field in self._EXPIRY_SORT_FIELDS else "expire_time"
        # days_left 由 expire_time 计算而来，方向一致
        if sf == "days_left":
            sf = "expire_time"
        sd = pymongo.ASCENDING if sort_order == "asc" else pymongo.DESCENDING
        docs = list(self._db["expiry_resources"].find(match, {"_id": 0}).sort(sf, sd))

        # 批量关联 instances 获取内网IP
        if docs:
            pairs = [{"cloud": d["cloud"], "instance_id": d["resource_id"]} for d in docs]
            ip_map: dict[str, str] = {
                f"{inst['cloud']}:{inst['instance_id']}": inst.get("n_ip", "")
                for inst in self._db["instances"].find(
                    {"$or": pairs}, {"_id": 0, "cloud": 1, "instance_id": 1, "n_ip": 1}
                )
            }
        else:
            ip_map = {}

        result = []
        for doc in docs:
            try:
                exp = datetime.strptime(doc["expire_time"], "%Y-%m-%d %H:%M:%S")
                doc["days_left"] = max(0, (exp - now).days)
            except Exception:
                doc["days_left"] = -1
            # notify_email_override 优先；其次项目级邮箱
            override = (doc.pop("notify_email_override", None) or "").strip()
            proj_email = project_email.get(doc.get("project", ""), "")
            doc["notify_email"] = override or proj_email
            doc["notify_email_is_override"] = bool(override)
            doc["n_ip"] = ip_map.get(f"{doc['cloud']}:{doc['resource_id']}", "")
            result.append(doc)
        return result

    def save_expiry_email_override(self, cloud: str, resource_id: str, email: str) -> bool:
        """保存资源级邮箱覆盖（不写入 projects 表）"""
        r = self._db["expiry_resources"].update_one(
            {"cloud": cloud, "resource_id": resource_id},
            {"$set": {"notify_email_override": email.strip()}},
        )
        return r.matched_count > 0

    def get_expiry_filter_options(self) -> dict:
        return {
            "clouds": self._db["expiry_resources"].distinct("cloud"),
            "providers": self._db["expiry_resources"].distinct("provider"),
            "resource_types": self._db["expiry_resources"].distinct("resource_type"),
            "groups": [g for g in self._db["expiry_resources"].distinct("group") if g and g != "未知"],
            "projects": self._db["expiry_resources"].distinct("project"),
            "auto_renews": [v for v in self._db["expiry_resources"].distinct("auto_renew") if v],
        }


    # ── 费用统计 ──────────────────────────────────────────────────────────────

    def upsert_cost_records(self, cloud_name: str, provider: str,
                            year: int, month: int, records: list) -> int:
        """批量 upsert 费用记录到 cost_records 集合"""
        from pymongo import UpdateOne
        if not records:
            return 0
        ops = []
        for r in records:
            key = {
                "cloud": cloud_name,
                "provider": provider,
                "year": year,
                "month": month,
                "project": r.project,
                "service_type_code": r.service_type_code,
            }
            ops.append(UpdateOne(
                key,
                {"$set": {**key,
                    "service_type_name": r.service_type_name,
                    "service_category": r.service_category,
                    "amount": r.amount,
                }},
                upsert=True,
            ))
        result = self._db["cost_records"].bulk_write(ops)
        # 确保索引存在
        self._db["cost_records"].create_index(
            [("cloud", 1), ("provider", 1), ("year", 1), ("month", 1)],
            background=True,
        )
        return result.upserted_count + result.modified_count

    def get_cost_data(self, cloud: str, year: int, months: list) -> list:
        """按月+项目+服务类别聚合费用"""
        pipeline = [
            {"$match": {"cloud": cloud, "year": year, "month": {"$in": list(months)}}},
            {"$group": {
                "_id": {
                    "month": "$month",
                    "project": "$project",
                    "service_category": "$service_category",
                },
                "amount": {"$sum": "$amount"},
            }},
            {"$project": {
                "_id": 0,
                "month": "$_id.month",
                "project": "$_id.project",
                "service_category": "$_id.service_category",
                "amount": 1,
            }},
            {"$sort": {"month": 1, "project": 1}},
        ]
        return list(self._db["cost_records"].aggregate(pipeline))

    def has_cost_data(self, cloud_name: str) -> bool:
        """判断该账号是否已有费用数据（用于决定是否全量回填）"""
        return self._db["cost_records"].count_documents({"cloud": cloud_name}, limit=1) > 0

    def get_cost_clouds(self, provider: str) -> list:
        """返回有费用数据的云账号列表"""
        return self._db["cost_records"].distinct("cloud", {"provider": provider})

    # ── 应用配置 ──────────────────────────────────────────────────────────────

    _DEFAULT_APP_CONFIG: dict = {
        "auth": {
            "username": "admin",
            "password": "Admin@123",
            "jwt_secret": "change-me-please",
            "token_expire_hours": 24,
            "idle_timeout_minutes": 30,
        },
        "schedule": {"time": "01:30", "hours": 24},
        "server": {"port": 5002, "debug": False},
        "system_url": "",
        "email": {
            "host": "", "port": 465, "username": "",
            "password": "", "from_name": "云监控系统", "ssl": True,
        },
        "clouds": [],
        "project_excel": "",
    }

    def load_app_config(self) -> dict:
        """从数据库加载应用配置；不存在时写入默认值并返回"""
        doc = self._db["system_config"].find_one({"type": "app_config"}, {"_id": 0, "type": 0})
        if doc:
            return doc
        import copy
        default = copy.deepcopy(self._DEFAULT_APP_CONFIG)
        self.save_app_config(default)
        return default

    def save_app_config(self, config: dict) -> None:
        """将应用配置（不含 mongodb 连接）写入数据库"""
        import copy
        doc = copy.deepcopy(config)
        doc.pop("mongodb", None)   # MongoDB 连接始终来自环境变量
        doc.pop("_id", None)
        doc["type"] = "app_config"
        self._db["system_config"].update_one(
            {"type": "app_config"},
            {"$set": doc},
            upsert=True,
        )

    # ── 登录历史 ──────────────────────────────────────────────────────────────

    def record_login(self, username: str, ip: str, user_agent: str,
                     success: bool = True, fail_reason: str = ""):
        self._db["audit_logs"].insert_one({
            "event": "login_success" if success else "login_fail",
            "username": username,
            "ip": ip,
            "user_agent": user_agent,
            "detail": fail_reason,
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    def record_secret_view(self, username: str, ip: str, config_path: str):
        self._db["audit_logs"].insert_one({
            "event": "view_secret",
            "username": username,
            "ip": ip,
            "user_agent": "",
            "detail": config_path,
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    def get_audit_logs(self, event_filter: str = "", page: int = 1, page_size: int = 50) -> dict:
        query: dict = {}
        if event_filter:
            query["event"] = event_filter
        total = self._db["audit_logs"].count_documents(query)
        docs = list(self._db["audit_logs"].find(
            query, {"_id": 0},
            sort=[("ts", -1)],
            skip=(page - 1) * page_size,
            limit=page_size,
        ))
        return {"total": total, "items": docs}

    def get_login_history(self, username: str, limit: int = 20) -> list[dict]:
        docs = list(self._db["audit_logs"].find(
            {"username": username, "event": "login_success"},
            {"_id": 0, "username": 0, "event": 0},
            sort=[("ts", -1)],
            limit=limit,
        ))
        # 兼容旧字段名
        for d in docs:
            if "login_time" not in d:
                d["login_time"] = d.get("ts", "")
        return docs

    # ── 告警阈值 ──────────────────────────────────────────────────────────────

    def get_alert_thresholds(self) -> dict:
        doc = self._db["system_config"].find_one({"type": "alert_thresholds"}) or {}
        return {
            "cpu": doc.get("cpu", 80),
            "mem": doc.get("mem", 85),
            "disk": doc.get("disk", 90),
        }

    def save_alert_thresholds(self, thresholds: dict):
        self._db["system_config"].update_one(
            {"type": "alert_thresholds"},
            {"$set": {"type": "alert_thresholds",
                      "cpu": thresholds.get("cpu", 80),
                      "mem": thresholds.get("mem", 85),
                      "disk": thresholds.get("disk", 90)}},
            upsert=True,
        )

    def get_alerts(self, thresholds: dict) -> dict:
        """基于最新一次采集数据计算各类告警"""
        times = self.get_recent_collect_times(1)
        if not times:
            return {"cpu": [], "mem": [], "disk": [], "down": [],
                    "thresholds": thresholds, "collect_time": ""}
        latest = times[0]
        match = {"update_time": latest}
        base_fields = {"_id": 0, "name": 1, "cloud": 1, "provider": 1,
                       "region": 1, "project": 1, "group": 1, "manager": 1, "n_ip": 1}

        cpu_t = thresholds.get("cpu", 80)
        mem_t = thresholds.get("mem", 85)
        disk_t = thresholds.get("disk", 90)

        cpu_alerts = list(self._db["metrics"].find(
            {**match, "cpu_avg": {"$gte": cpu_t}},
            {**base_fields, "cpu_avg": 1, "cpu_max": 1},
        ).sort("cpu_avg", -1))

        mem_alerts = list(self._db["metrics"].find(
            {**match, "mem_avg": {"$gte": mem_t}},
            {**base_fields, "mem_avg": 1, "mem_max": 1},
        ).sort("mem_avg", -1))

        disk_alerts = list(self._db["metrics"].find(
            {**match, "disk_avg": {"$gte": disk_t}},
            {**base_fields, "disk_avg": 1, "disk_details": 1},
        ).sort("disk_avg", -1))

        _online_statuses = ["UP", "RUNNING", "Running", "Active", "active", "running"]
        down_alerts = list(self._db["instances"].find(
            {"status": {"$nin": _online_statuses}},
            {**base_fields, "status": 1},
        ))

        return {
            "cpu": cpu_alerts,
            "mem": mem_alerts,
            "disk": disk_alerts,
            "down": down_alerts,
            "thresholds": thresholds,
            "collect_time": latest,
        }

    # ── 用户管理 ──────────────────────────────────────────────────────────────

    ALL_MENUS = ["dashboard", "table", "expiry", "alert", "balance", "cost", "project_mgmt"]
    ALL_ACTIONS = ["collect", "refresh_expiry", "refresh_projects", "send_email"]

    def get_user_by_username(self, username: str) -> Optional[dict]:
        doc = self._db["users"].find_one({"username": username})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def list_users(self) -> list[dict]:
        docs = list(self._db["users"].find({}, {"password_hash": 0}))
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    def create_user(self, data: dict) -> str:
        doc = {
            "username": data["username"],
            "email": data.get("email", ""),
            "password_hash": data["password_hash"],
            "role": "user",
            "group_id": data.get("group_id"),
            "is_active": True,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_login": None,
        }
        result = self._db["users"].insert_one(doc)
        return str(result.inserted_id)

    def update_user(self, user_id: str, data: dict) -> bool:
        try:
            update_fields = {k: v for k, v in data.items()
                             if k in ("email", "group_id", "is_active", "password_hash")}
            if not update_fields:
                return True
            result = self._db["users"].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_fields},
            )
            return result.matched_count > 0
        except Exception:
            return False

    def delete_user(self, user_id: str) -> bool:
        try:
            result = self._db["users"].delete_one({"_id": ObjectId(user_id)})
            return result.deleted_count > 0
        except Exception:
            return False

    def update_last_login(self, username: str) -> None:
        self._db["users"].update_one(
            {"username": username},
            {"$set": {"last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}},
        )

    def init_admin_user(self, username: str, password_hash: str) -> None:
        if self._db["users"].count_documents({}) == 0:
            self._db["users"].insert_one({
                "username": username,
                "email": "",
                "password_hash": password_hash,
                "role": "admin",
                "group_id": None,
                "is_active": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_login": None,
            })

    # ── 权限组管理 ────────────────────────────────────────────────────────────

    _PRESET_GROUPS = [
        {
            "name": "只读观察员",
            "description": "可查看所有监控数据，无操作权限",
            "menus": ["dashboard", "table", "expiry", "alert", "balance", "cost"],
            "actions": [],
            "is_preset": True,
        },
        {
            "name": "运维人员",
            "description": "可查看所有数据并执行采集、刷新操作",
            "menus": ["dashboard", "table", "expiry", "alert", "balance", "cost", "project_mgmt"],
            "actions": ["collect", "refresh_expiry", "refresh_projects"],
            "is_preset": True,
        },
        {
            "name": "财务查看",
            "description": "仅可查看费用和余额相关数据",
            "menus": ["dashboard", "balance", "cost"],
            "actions": [],
            "is_preset": True,
        },
    ]

    def list_permission_groups(self) -> list[dict]:
        docs = list(self._db["permission_groups"].find({}))
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    def get_permission_group(self, group_id: str) -> Optional[dict]:
        try:
            doc = self._db["permission_groups"].find_one({"_id": ObjectId(group_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception:
            return None

    def create_permission_group(self, data: dict) -> str:
        doc = {
            "name": data["name"],
            "description": data.get("description", ""),
            "menus": data.get("menus", []),
            "actions": data.get("actions", []),
            "is_preset": False,
        }
        result = self._db["permission_groups"].insert_one(doc)
        return str(result.inserted_id)

    def update_permission_group(self, group_id: str, data: dict) -> bool:
        try:
            update_fields = {k: v for k, v in data.items()
                             if k in ("name", "description", "menus", "actions")}
            if not update_fields:
                return True
            result = self._db["permission_groups"].update_one(
                {"_id": ObjectId(group_id)},
                {"$set": update_fields},
            )
            return result.matched_count > 0
        except Exception:
            return False

    def delete_permission_group(self, group_id: str) -> bool:
        try:
            if self._db["users"].count_documents({"group_id": group_id}) > 0:
                return False
            result = self._db["permission_groups"].delete_one({"_id": ObjectId(group_id)})
            return result.deleted_count > 0
        except Exception:
            return False

    def init_preset_groups(self) -> None:
        if self._db["permission_groups"].count_documents({}) == 0:
            self._db["permission_groups"].insert_many(
                [dict(g) for g in self._PRESET_GROUPS]
            )

    # ── 运维平台链接管理 ────────────────────────────────────────────────────────

    def list_ops_links(self) -> list[dict]:
        docs = list(self._db["ops_links"].find({}).sort("sort_order", 1))
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    def create_ops_link(self, data: dict) -> str:
        max_order = self._db["ops_links"].count_documents({})
        doc = {
            "name": data["name"],
            "url": data["url"],
            "icon": data.get("icon", "Link"),
            "sort_order": data.get("sort_order", max_order),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        result = self._db["ops_links"].insert_one(doc)
        return str(result.inserted_id)

    def update_ops_link(self, link_id: str, data: dict) -> bool:
        try:
            fields = {k: v for k, v in data.items() if k in ("name", "url", "icon", "sort_order")}
            if not fields:
                return True
            result = self._db["ops_links"].update_one(
                {"_id": ObjectId(link_id)}, {"$set": fields}
            )
            return result.matched_count > 0
        except Exception:
            return False

    def delete_ops_link(self, link_id: str) -> bool:
        try:
            result = self._db["ops_links"].delete_one({"_id": ObjectId(link_id)})
            return result.deleted_count > 0
        except Exception:
            return False


def _bucket_distribution(db, col: str, match: dict, field: str) -> list[dict]:
    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {"instance_id": "$instance_id"},
            "val": {"$avg": f"${field}"},
        }},
        {"$bucket": {
            "groupBy": "$val",
            "boundaries": [0, 40, 60, 80, 101],
            "default": "other",
            "output": {"count": {"$sum": 1}},
        }},
    ]
    raw = list(db[col].aggregate(pipeline))
    labels = {0: "0-40%", 40: "40-60%", 60: "60-80%", 80: "80-100%"}
    return [{"name": labels.get(r["_id"], str(r["_id"])), "value": r["count"]} for r in raw if r["_id"] in labels]
