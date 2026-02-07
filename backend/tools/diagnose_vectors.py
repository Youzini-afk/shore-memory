import os
import json
import sqlite3
from typing import Set, Dict, List

def get_data_dir():
    # 模拟 backend/services/vector_store_service.py 中的路径逻辑
    # 假设脚本位于 backend/tools/diagnose_vectors.py，回退两层到 backend
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    # 再回退一层到根目录 (如果 backend 是根目录下的子目录)
    # 但根据 vector_store_service.py:
    # base_dir = os.environ.get("PERO_DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 在 service 中 __file__ 是 backend/services/vector_store_service.py
    # dirname -> backend/services
    # dirname -> backend
    # 所以 base_dir 是 backend 的父目录，即项目根目录
    
    # 在这里 __file__ 是 backend/tools/diagnose_vectors.py
    # dirname -> backend/tools
    # dirname -> backend
    # 所以 base_dir 应该是 backend 目录
    base_dir = os.environ.get("PERO_DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "data")

def get_sql_ids(db_path: str, agent_id: str) -> Set[int]:
    if not os.path.exists(db_path):
        print(f"[Warn] 数据库文件不存在: {db_path}")
        return set()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # 假设 Memory 表有 id 和 agent_id 字段
        cursor.execute("SELECT id FROM memory WHERE agent_id = ?", (agent_id,))
        ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        return ids
    except Exception as e:
        print(f"[Error] 读取 SQL 失败: {e}")
        return set()

def get_vector_ids(index_path: str) -> Set[int]:
    if not os.path.exists(index_path):
        return set()
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            # 尝试直接加载 JSON
            # Rust 的 serde_json 默认输出即为标准 JSON
            data = json.load(f)
            if isinstance(data, list):
                # data 是 List[IntentAnchor]
                # IntentAnchor { id: i64, ... }
                return {item.get("id") for item in data if "id" in item}
            else:
                print(f"[Warn] 索引文件格式不是列表: {index_path}")
                return set()
    except json.JSONDecodeError:
        print(f"[Error] 索引文件 JSON 解析失败 (可能是二进制格式或损坏): {index_path}")
        return set()
    except Exception as e:
        print(f"[Error] 读取索引文件失败: {e}")
        return set()

def diagnose_agent(agent_id: str, sql_db_path: str, rust_db_dir: str):
    print(f"\n--- 诊断 Agent: {agent_id} ---")
    
    # 1. SQL IDs
    sql_ids = get_sql_ids(sql_db_path, agent_id)
    print(f"SQL 记录数: {len(sql_ids)}")
    
    # 2. Vector IDs
    # 路径逻辑参考 VectorStoreService._get_agent_index_path
    index_path = os.path.join(rust_db_dir, "agents", agent_id, "memory.index")
    vector_ids = get_vector_ids(index_path)
    print(f"Vector 记录数: {len(vector_ids)}")
    
    # 3. Compare
    missing_vector = sql_ids - vector_ids
    ghost_data = vector_ids - sql_ids
    
    if not missing_vector and not ghost_data:
        print("✅ 数据完全一致！")
    else:
        if missing_vector:
            print(f"❌ 缺失向量 (SQL 有但 Vector 无): {len(missing_vector)} 条")
            print(f"   IDs (前10个): {list(missing_vector)[:10]}...")
        
        if ghost_data:
            print(f"👻 幽灵数据 (Vector 有但 SQL 无): {len(ghost_data)} 条")
            print(f"   IDs (前10个): {list(ghost_data)[:10]}...")

def main():
    data_dir = get_data_dir()
    sql_db_path = os.path.join(data_dir, "database.db")
    
    # 优先检查 perocore.db
    candidates = ["perocore.db", "pero.db", "core.db", "memory.db"]
    for c in candidates:
        p = os.path.join(data_dir, c)
        if os.path.exists(p):
            sql_db_path = p
            break
    
    print(f"数据目录: {data_dir}")
    print(f"数据库路径: {sql_db_path}")
    
    if not os.path.exists(sql_db_path):
        print("错误: 找不到 SQLite 数据库文件。")
        return
        
    rust_db_dir = os.path.join(data_dir, "rust_db")

    # Debug: 列出所有表
    try:
        conn = sqlite3.connect(sql_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"数据库表: {tables}")
        conn.close()
    except Exception as e:
        print(f"列出表失败: {e}")


    # 自动发现所有 Agent
    agents = set()
    # 从数据库中查找所有 agent_id
    try:
        conn = sqlite3.connect(sql_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT agent_id FROM memory")
        rows = cursor.fetchall()
        for row in rows:
            if row[0]:
                agents.add(row[0])
        conn.close()
    except Exception as e:
        print(f"无法从数据库获取 Agent 列表: {e}")
        # Fallback to default
        agents.add("pero")
        
    # 同时也检查 rust_db/agents 目录下的文件夹
    agents_dir = os.path.join(rust_db_dir, "agents")
    if os.path.exists(agents_dir):
        for name in os.listdir(agents_dir):
            if os.path.isdir(os.path.join(agents_dir, name)):
                agents.add(name)
    
    if not agents:
        agents.add("pero")
        
    for agent in sorted(agents):
        diagnose_agent(agent, sql_db_path, rust_db_dir)

if __name__ == "__main__":
    main()
