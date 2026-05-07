import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# MongoDB 连接参数从环境变量读取，其他所有配置从数据库加载
MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = int(os.environ.get("MONGO_PORT", "27017"))
MONGO_DATABASE = os.environ.get("MONGO_DATABASE", "cloud_monitor_v2")

MONGO_CFG = {"host": MONGO_HOST, "port": MONGO_PORT, "database": MONGO_DATABASE}


def migrate_excel_to_db(cfg: dict, store):
    """首次启动时将云项目对照表.xlsx导入projects集合"""
    if store._db["projects"].count_documents({}) > 0:
        return
    excel_path = cfg.get("project_excel", "")
    if excel_path and not os.path.isabs(excel_path):
        excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), excel_path)
    if not excel_path or not os.path.exists(excel_path):
        return
    count = store.init_projects_from_excel(excel_path)
    if count > 0:
        print(f"[迁移] 云项目对照表导入成功，共 {count} 条项目")
        try:
            os.remove(excel_path)
            print(f"[迁移] 已删除 {excel_path}")
        except OSError:
            pass


if __name__ == "__main__":
    from storage.mongo import MongoStore

    store = MongoStore(MONGO_HOST, MONGO_PORT, MONGO_DATABASE)
    cfg = store.load_app_config()
    cfg["mongodb"] = MONGO_CFG  # 注入连接信息，保持下游代码兼容

    mode = os.getenv("mode", "api")

    migrate_excel_to_db(cfg, store)

    if mode == "run":
        from collector.runner import run_collect
        run_collect(cfg["clouds"], MONGO_CFG, cfg["schedule"]["hours"])

    elif mode == "task":
        from api.app import init_app
        from collector.scheduler import start as start_scheduler

        run_time = os.getenv("time", cfg["schedule"]["time"])
        start_scheduler(cfg["clouds"], MONGO_CFG, run_time, cfg["schedule"]["hours"])

        app = init_app(cfg, MONGO_CFG)
        print(f"[启动] API + 定时任务模式，采集时间: {run_time}")
        app.run(host="0.0.0.0", port=cfg["server"]["port"], debug=cfg["server"]["debug"])

    else:
        from api.app import init_app
        from collector.scheduler import start as start_scheduler

        start_scheduler(cfg["clouds"], MONGO_CFG,
                        cfg["schedule"]["time"], cfg["schedule"]["hours"])

        app = init_app(cfg, MONGO_CFG)
        print(f"[启动] API 服务 http://0.0.0.0:{cfg['server']['port']}")
        app.run(host="0.0.0.0", port=cfg["server"]["port"], debug=cfg["server"]["debug"])
