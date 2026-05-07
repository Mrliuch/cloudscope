import threading
import schedule
import time

from collector.runner import run_collect
from collector.expiry import run_expiry_collect


def start(cloud_configs: list[dict], mongo_cfg: dict, run_time: str, hours: int):
    def job():
        # 每次执行时从 app._cfg 读取最新配置，保证系统配置页保存后立即生效
        try:
            import api.app as _app
            cfg = _app._cfg
            clouds = cfg.get("clouds", cloud_configs)
            mc = cfg.get("mongodb", mongo_cfg)
            h = cfg.get("schedule", {}).get("hours", hours)
        except Exception:
            clouds, mc, h = cloud_configs, mongo_cfg, hours
        run_collect(clouds, mc, h)
        run_expiry_collect(clouds, mc, days=30)

    schedule.every().day.at(run_time).do(job)
    print(f"[定时任务] 已注册，每天 {run_time} 执行采集")

    def loop():
        while True:
            schedule.run_pending()
            time.sleep(30)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
