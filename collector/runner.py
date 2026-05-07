from __future__ import annotations
import time

from providers import create_provider
from storage.mongo import MongoStore
from storage.enrich import enrich_instances
from providers.base import ExpiringResource

_MAX_LOGS = 500


class CollectStatus:
    def __init__(self):
        self.status = "idle"
        self.progress = {"current": 0, "total": 0, "current_cloud": ""}
        self.last_collect_time: str | None = None
        self.error: str | None = None
        self.logs: list[str] = []


_status = CollectStatus()


def _log(msg: str) -> None:
    print(msg)
    ts = time.strftime("%H:%M:%S")
    _status.logs.append(f"[{ts}] {msg}")
    if len(_status.logs) > _MAX_LOGS:
        _status.logs = _status.logs[-_MAX_LOGS:]


def get_status() -> dict:
    return {
        "status": _status.status,
        "progress": _status.progress,
        "last_collect_time": _status.last_collect_time,
        "error": _status.error,
        "logs": list(_status.logs),
    }


def run_collect(cloud_configs: list[dict], mongo_cfg: dict, hours: int = 24):
    if _status.status == "running":
        return

    _status.status = "running"
    _status.error = None
    _status.logs = []

    store = MongoStore(
        host=mongo_cfg["host"],
        port=mongo_cfg["port"],
        database=mongo_cfg["database"],
    )
    update_time = time.strftime("%Y-%m-%d %H:%M:%S")
    project_map = store.get_project_map_from_db()

    try:
        store.record_collect_time(update_time)
        total_clouds = len(cloud_configs)
        _status.progress = {"current": 0, "total": total_clouds, "current_cloud": ""}
        _log(f"开始采集，共 {total_clouds} 个云账号")

        for idx, cloud_cfg in enumerate(cloud_configs):
            cloud_name = cloud_cfg["name"]
            _status.progress = {"current": idx + 1, "total": total_clouds, "current_cloud": cloud_name}
            _log(f"[{cloud_name}] 开始采集")

            try:
                provider = create_provider(cloud_cfg)
                if provider is None:
                    _log(f"[{cloud_name}] 跳过（provider 为空）")
                    continue
                for region in provider.regions:
                    _log(f"[{cloud_name}] region={region} 获取实例...")
                    instances = provider.get_instances(region)
                    _log(f"[{cloud_name}] region={region} 共 {len(instances)} 台，获取监控...")

                    if project_map:
                        enrich_instances(instances, project_map)

                    for inst in instances:
                        store.upsert_instance(cloud_name, provider.provider, inst, update_time)

                    metrics_map = provider.get_all_metrics_batch(instances, region, hours)

                    for inst in instances:
                        m = metrics_map.get(inst.instance_id)
                        if m:
                            store.insert_metric(cloud_name, provider.provider, inst, m, hours, update_time)
                            if m.disk_details:
                                store.update_instance_disk_details(cloud_name, inst.instance_id, m.disk_details)

                    # 到期资源采集
                    try:
                        expiry_list = provider.get_expiring_resources(region, days=180)
                        for r in expiry_list:
                            r.cloud = cloud_name
                            r.provider = provider.provider
                            info = project_map.get(r.project, {})
                            if info:
                                r.group = info.get("group", "未知")
                                r.last_group = info.get("last_group", "未知")
                                r.manager = info.get("manager", "未知")
                            store.upsert_expiry_resource(r, update_time)
                        _log(f"[{cloud_name}] region={region} 到期资源（180天内）{len(expiry_list)} 条")
                    except Exception as e:
                        _log(f"[{cloud_name}] region={region} 到期资源采集失败: {e}")

                    time.sleep(1)

                # 清理本账号本次未更新的到期记录（确保不留历史数据）
                store.clean_expiry_resources_for_cloud(cloud_name, update_time)
                store.clean_stale_instances(cloud_name, update_time)
                _log(f"[{cloud_name}] 采集完成")

            except Exception as e:
                _log(f"[{cloud_name}] 采集失败: {e}")
                _status.error = f"{cloud_name}: {e}"

        store.clean_old_metrics()

        # 费用数据采集（集成在主流程末尾）
        try:
            from collector.cost import run_cost_collect
            _log("开始采集费用数据...")
            run_cost_collect(cloud_configs, mongo_cfg, log_fn=_log)
        except Exception as e:
            _log(f"费用采集失败（不影响主流程）: {e}")

        _status.last_collect_time = update_time
        _log(f"全部完成，时间: {update_time}")

    finally:
        _status.status = "idle"
        _status.progress = {"current": 0, "total": 0, "current_cloud": ""}
