"""
数据存储模块 - 暂存和打印历史
"""
import json
import os
import shutil
import sys
from datetime import datetime
from packing import PackingRecord, BoxLabel


# 数据目录：固定到 EXE 同级（frozen）或源码同级（开发模式）
# 不再依赖 cwd，避免双击 EXE 时数据写到错误位置
def _resolve_data_dir() -> str:
    if getattr(sys, "frozen", False):
        # 打包后：用 EXE 所在目录
        base = os.path.dirname(sys.executable)
    else:
        # 源码：用 storage.py 所在目录
        base = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base, "data")
    return data_dir


DATA_DIR = _resolve_data_dir()

# 自动备份：每次保存保留最近 5 份历史（products.json.bak 是最新，.bak.4 最旧）
MAX_BACKUPS = 5
# 哪些文件需要备份（用户录入的核心数据，不要备份 UI 列宽这种临时配置）
BACKUP_FILES = {"products.json", "order_history.json", "current_packing.json"}


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _rotate_backup(filepath: str):
    """滚动备份：foo.json.bak.4 → 删，.bak.3 → .bak.4，...，.bak → .bak.1，foo.json → .bak"""
    if not os.path.exists(filepath):
        return
    base = os.path.basename(filepath)
    if base not in BACKUP_FILES:
        return  # 不备份的文件直接跳过

    data_dir = os.path.dirname(filepath)
    # 删除最旧的
    oldest = os.path.join(data_dir, f"{base}.bak.{MAX_BACKUPS - 1}")
    if os.path.exists(oldest):
        try:
            os.remove(oldest)
        except Exception:
            pass
    # 依次往后滚动
    for i in range(MAX_BACKUPS - 2, 0, -1):
        old = os.path.join(data_dir, f"{base}.bak.{i}")
        new = os.path.join(data_dir, f"{base}.bak.{i + 1}")
        if os.path.exists(old):
            try:
                shutil.move(old, new)
            except Exception:
                pass
    # .bak → .bak.1
    cur_bak = os.path.join(data_dir, f"{base}.bak")
    if os.path.exists(cur_bak):
        try:
            shutil.move(cur_bak, os.path.join(data_dir, f"{base}.bak.1"))
        except Exception:
            pass
    # 当前文件 → .bak（先复制再写，避免备份和最新值指向同一文件）
    try:
        shutil.copy2(filepath, cur_bak)
    except Exception:
        pass


def _load_json(filename: str, default=None):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(filename: str, data):
    _ensure_dir()
    filepath = os.path.join(DATA_DIR, filename)
    # 先滚动备份（写入前的"上一版"才是真正的备份）
    _rotate_backup(filepath)
    # 原子写入：先写临时文件，再 rename，避免中途崩溃损坏数据
    tmp = filepath + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, filepath)
    except Exception:
        # 写入失败也要清理临时文件
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
        raise


def save_packing(products, boxes, merge_tail=False, remark="", order_remark=""):
    """保存装箱暂存"""
    products_data = [p.to_dict() for p in products]
    boxes_data = [b.to_dict() for b in boxes]

    record = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "products": products_data,
        "boxes": boxes_data,
        "merge_tail": merge_tail,
        "remark": remark,
        "order_remark": order_remark,
    }

    # 同时保存到暂存和追加到历史
    _save_json("current_packing.json", record)

    history = _load_json("packing_history.json", [])
    history.append(record)
    # 保留最近100条
    if len(history) > 100:
        history = history[-100:]
    _save_json("packing_history.json", history)

    return record["id"]


def load_current_packing():
    """加载当前暂存的装箱数据"""
    data = _load_json("current_packing.json")
    if data:
        return PackingRecord.from_dict(data)
    return None


def clear_current_packing():
    """清除当前暂存"""
    filepath = os.path.join(DATA_DIR, "current_packing.json")
    if os.path.exists(filepath):
        os.remove(filepath)


def get_packing_history():
    """获取装箱历史记录"""
    return _load_json("packing_history.json", [])


def get_packing_history_by_id(record_id: str):
    """通过ID获取历史记录"""
    history = get_packing_history()
    for record in history:
        if record.get("id") == record_id:
            return record
    return None


def delete_history_record(record_id: str):
    """删除一条历史记录"""
    history = get_packing_history()
    new_history = [r for r in history if r.get("id") != record_id]
    _save_json("packing_history.json", new_history)


def clear_all_history():
    """清空所有历史"""
    _save_json("packing_history.json", [])


def save_print_log(record_id: str):
    """记录打印日志"""
    log = _load_json("print_log.json", [])
    entry = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "record_id": record_id,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    log.append(entry)
    _save_json("print_log.json", log)


def get_print_history():
    """获取打印历史"""
    return _load_json("print_log.json", [])


def get_combined_history():
    """获取带装箱详情打印历史"""
    logs = get_print_history()
    result = []
    for log in logs:
        record = get_packing_history_by_id(log["record_id"])
        if record:
            result.append({
                "print_id": log["id"],
                "record_id": log["record_id"],
                "time": log["time"],
                "products": record.get("products", []),
                "boxes": record.get("boxes", []),
                "merge_tail": record.get("merge_tail", False),
                "remark": record.get("remark", ""),
                "order_remark": record.get("order_remark", ""),
            })
    return result

# ===== 订单历史 =====
ORDER_HISTORY_FILE = "order_history.json"
UI_CONFIG_FILE = "ui_config.json"

def save_order_to_history(recipient: str, order_no: str, items: list, order_remark: str = "") -> str:
    """保存一个订单到历史记录"""
    history = _load_json(ORDER_HISTORY_FILE, [])
    entry = {
        "recipient": recipient,
        "order_no": order_no,
        "items": items,  # list of {"name":...,"sku":...,"per":...,"qty":...}
        "order_remark": order_remark,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    # 检查是否已存在同样订单，覆盖"
    found = False
    for i, h in enumerate(history):
        if h.get("order_no") == order_no and h.get("recipient") == recipient:
            history[i] = entry
            found = True
            break
    if not found:
        history.append(entry)
    _save_json(ORDER_HISTORY_FILE, history)
    return order_no

def load_order_history() -> list:
    """加载所有订单历史"""
    return _load_json(ORDER_HISTORY_FILE, [])

def delete_order_history(indexes: list):
    """删除指定索引的订单历史"""
    history = _load_json(ORDER_HISTORY_FILE, [])
    new_history = [h for i, h in enumerate(history) if i not in indexes]
    _save_json(ORDER_HISTORY_FILE, new_history)


def load_order_history_column_widths(defaults: dict) -> dict:
    """加载装箱历史列表列宽。"""
    config = _load_json(UI_CONFIG_FILE, {}) or {}
    widths = config.get("order_history_column_widths", {})
    result = dict(defaults)
    for key, value in widths.items():
        try:
            result[key] = int(value)
        except (TypeError, ValueError):
            continue
    return result


def save_order_history_column_widths(widths: dict):
    """保存装箱历史列表列宽。"""
    config = _load_json(UI_CONFIG_FILE, {}) or {}
    config["order_history_column_widths"] = {key: int(value) for key, value in widths.items()}
    _save_json(UI_CONFIG_FILE, config)
