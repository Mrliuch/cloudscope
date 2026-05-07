from __future__ import annotations
import time
from datetime import datetime

from providers import create_provider
from storage.mongo import MongoStore


class ExpiryStatus:
    def __init__(self):
        self.status = "idle"
        self.total = 0
        self.update_time: str | None = None
        self.error: str | None = None


_status = ExpiryStatus()


def get_expiry_status() -> dict:
    return {
        "status": _status.status,
        "total": _status.total,
        "update_time": _status.update_time,
        "error": _status.error,
    }


def run_expiry_collect(cloud_configs: list[dict], mongo_cfg: dict, days: int = 30):
    if _status.status == "running":
        return

    _status.status = "running"
    _status.error = None

    store = MongoStore(
        host=mongo_cfg["host"],
        port=mongo_cfg["port"],
        database=mongo_cfg["database"],
    )
    update_time = time.strftime("%Y-%m-%d %H:%M:%S")
    project_map = store.get_project_map_from_db()
    all_resources = []

    try:
        for cfg in cloud_configs:
            cloud_name = cfg.get("name", "")
            try:
                provider = create_provider(cfg)
                if provider is None:
                    continue
                for region in provider.regions:
                    try:
                        resources = provider.get_expiring_resources(region, days)
                        for r in resources:
                            r.cloud = provider.name
                            r.provider = provider.provider
                            enrich = project_map.get(r.project, {})
                            r.group = enrich.get("group", "未知")
                            r.last_group = enrich.get("last_group", "未知")
                            r.manager = enrich.get("manager", "未知")
                            all_resources.append(r)
                        if resources:
                            print(f"[expiry] {cloud_name} region={region} 到期资源 {len(resources)} 条")
                    except Exception as e:
                        print(f"[expiry] {cloud_name} region={region} 采集失败: {e}")
            except Exception as e:
                print(f"[expiry] 初始化 {cloud_name} 失败: {e}")

        for r in all_resources:
            store.upsert_expiry_resource(r, update_time)

        store.clean_stale_expiry_resources(update_time)

        _status.total = len(all_resources)
        _status.update_time = update_time
        print(f"[expiry] 采集完成，共 {len(all_resources)} 条到期资源")

    except Exception as e:
        _status.error = str(e)
        print(f"[expiry] 采集异常: {e}")
    finally:
        _status.status = "idle"
