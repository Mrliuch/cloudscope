"""
将 config.yaml 中的配置初始化到数据库。
生产和本地测试数据库均可使用此脚本初始化。

用法：
    MONGO_HOST=localhost MONGO_PORT=27017 MONGO_DATABASE=cloud_monitor_v2_test \
        python scripts/init_config_to_db.py

    # 强制覆盖已有配置：
    FORCE=1 MONGO_DATABASE=cloud_monitor_v2_test python scripts/init_config_to_db.py
"""
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.mongo import MongoStore

MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = int(os.environ.get("MONGO_PORT", "27017"))
MONGO_DATABASE = os.environ.get("MONGO_DATABASE", "cloud_monitor_v2_test")
FORCE = os.environ.get("FORCE", "") == "1"


def main():
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    if not os.path.exists(cfg_path):
        print(f"[错误] 未找到 config.yaml：{cfg_path}")
        sys.exit(1)

    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    store = MongoStore(MONGO_HOST, MONGO_PORT, MONGO_DATABASE)

    existing = store._db["system_config"].find_one({"type": "app_config"})
    if existing and not FORCE:
        print(f"[跳过] {MONGO_DATABASE}.system_config 已存在配置，未覆盖。")
        print("       如需强制覆盖，请设置 FORCE=1 重新运行。")
        return

    # 只保留应用配置，去掉 mongodb 连接（由环境变量提供）
    cfg = {k: v for k, v in raw.items() if k not in ("mongodb", "_id")}
    store.save_app_config(cfg)
    print(f"[成功] 配置已初始化到 {MONGO_DATABASE}.system_config")
    print(f"       云账号数量：{len(cfg.get('clouds', []))}")
    print(f"       调度时间：{cfg.get('schedule', {}).get('time', '-')}")


if __name__ == "__main__":
    main()
