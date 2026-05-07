from __future__ import annotations
import time
from datetime import date
from typing import Callable

from providers import create_provider
from storage.mongo import MongoStore


def _months_to_collect(cloud_name: str, store: MongoStore) -> list[tuple[int, int]]:
    """
    首次采集：回填过去 13 个月（含当月）
    非首次：只采集当月 + 上月（上月可能有滞后入账）
    """
    today = date.today()
    y, m = today.year, today.month

    if not store.has_cost_data(cloud_name):
        months = []
        cy, cm = y, m
        for _ in range(13):
            months.append((cy, cm))
            cm -= 1
            if cm == 0:
                cm = 12
                cy -= 1
        return months

    # 非首次：当月 + 上月
    prev_m = m - 1 if m > 1 else 12
    prev_y = y if m > 1 else y - 1
    return [(y, m), (prev_y, prev_m)]


def run_cost_collect(cloud_configs: list[dict], mongo_cfg: dict,
                     log_fn: Callable[[str], None] | None = None) -> None:
    """
    采集所有云账号的费用数据。
    - 首次：回填过去 13 个月
    - 非首次：仅更新当月 + 上月
    集成到主采集流程末尾，与定时任务共用同一 log_fn。
    """
    if log_fn is None:
        log_fn = print

    store = MongoStore(mongo_cfg["host"], mongo_cfg["port"], mongo_cfg["database"])

    for cloud_cfg in cloud_configs:
        cloud_name = cloud_cfg["name"]
        try:
            provider = create_provider(cloud_cfg)
            if provider is None:
                continue

            months = _months_to_collect(cloud_name, store)

            for year, month in months:
                log_fn(f"[费用] [{cloud_name}] 采集 {year}-{month:02d}...")
                try:
                    records = provider.get_costs(year, month)
                    if records:
                        count = store.upsert_cost_records(
                            cloud_name, provider.provider, year, month, records
                        )
                        log_fn(f"[费用] [{cloud_name}] {year}-{month:02d} "
                               f"{len(records)} 条记录，更新 {count} 条")
                    else:
                        log_fn(f"[费用] [{cloud_name}] {year}-{month:02d} 无费用数据")
                    time.sleep(0.3)
                except Exception as e:
                    log_fn(f"[费用] [{cloud_name}] {year}-{month:02d} 采集失败: {e}")

        except Exception as e:
            log_fn(f"[费用] [{cloud_name}] 初始化失败: {e}")
