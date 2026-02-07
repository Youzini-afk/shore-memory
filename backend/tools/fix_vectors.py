import os
import json
import sqlite3
import shutil
import time
from typing import Set, Dict, List

def get_data_dir():
    base_dir = os.environ.get("PERO_DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "data")

def get_sql_ids(db_path: str, agent_id: str) -> Set[int]:
    if not os.path.exists(db_path):
        return set()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM memory WHERE agent_id = ?", (agent_id,))
        ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        return ids
    except Exception as e:
        print(f"[Error] 读取 SQL 失败: {e}")
        return set()

def get_missing_embeddings(db_path: str, ids: List[int]) -> List[Dict]:
    """从 SQL 获取缺失的向量数据"""
    results = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # SQLite 不支持 array parameter，手动拼接
        id_str = ",".join(map(str, ids))
        cursor.execute(f"SELECT id, content, embedding_json, tags FROM memory WHERE id IN ({id_str})")
        rows = cursor.fetchall()
        
        for row in rows:
            if row['embedding_json']:
                try:
                    vec = json.loads(row['embedding_json'])
                    if isinstance(vec, list) and len(vec) > 0:
                        results.append({
                            "id": row['id'],
                            "vector": vec,
                            "description": "",
                            "importance": 1.0,
                            "tags": row['tags'] or ""
                        })
                except:
                    pass
        conn.close()
    except Exception as e:
        print(f"[Error] 读取 SQL Embedding 失败: {e}")
    return results

def fix_agent(agent_id: str, sql_db_path: str, rust_db_dir: str):
    print(f"\n--- 修复 Agent: {agent_id} ---")
    
    sql_ids = get_sql_ids(sql_db_path, agent_id)
    index_path = os.path.join(rust_db_dir, "agents", agent_id, "memory.index")
    
    if not os.path.exists(index_path):
        print(f"索引文件不存在，跳过: {index_path}")
        return

    try:
        # Backup
        backup_path = index_path + f".bak.{int(time.time())}"
        shutil.copy2(index_path, backup_path)
        print(f"已备份索引到: {backup_path}")
        
        with open(index_path, 'r', encoding='utf-8') as f:
            vector_data = json.load(f)
            
        original_count = len(vector_data)
        
        # 1. 清理幽灵数据
        # 保留那些 ID 在 SQL 中存在的
        new_vector_data = [item for item in vector_data if item.get('id') in sql_ids]
        ghost_count = original_count - len(new_vector_data)
        
        # 2. 补全缺失数据
        current_vector_ids = {item.get('id') for item in new_vector_data}
        missing_ids = list(sql_ids - current_vector_ids)
        
        recovered_count = 0
        if missing_ids:
            print(f"发现 {len(missing_ids)} 条缺失向量，尝试从 SQL 恢复...")
            recovered_items = get_missing_embeddings(sql_db_path, missing_ids)
            if recovered_items:
                new_vector_data.extend(recovered_items)
                recovered_count = len(recovered_items)
                print(f"成功从 SQL 恢复 {recovered_count} 条向量。")
            else:
                print("SQL 中没有这些记录的 embedding_json，无法恢复。请运行 MemoryService 的重新嵌入逻辑。")
        
        # Save if changed
        if ghost_count > 0 or recovered_count > 0:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(new_vector_data, f, ensure_ascii=False) # 保持紧凑格式，或者 indent=None
            print(f"✅ 修复完成: 清理了 {ghost_count} 条幽灵数据，恢复了 {recovered_count} 条缺失数据。")
        else:
            print("数据一致，无需修复。")
            
    except Exception as e:
        print(f"[Error] 修复失败: {e}")

def main():
    data_dir = get_data_dir()
    sql_db_path = os.path.join(data_dir, "database.db")
    
    candidates = ["perocore.db", "pero.db", "core.db", "memory.db"]
    for c in candidates:
        p = os.path.join(data_dir, c)
        if os.path.exists(p):
            sql_db_path = p
            break
            
    rust_db_dir = os.path.join(data_dir, "rust_db")
    
    if not os.path.exists(sql_db_path):
        print("错误: 找不到 SQLite 数据库文件。")
        return
        
    # Auto discover agents
    agents = set()
    try:
        conn = sqlite3.connect(sql_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT agent_id FROM memory")
        rows = cursor.fetchall()
        for row in rows:
            if row[0]:
                agents.add(row[0])
        conn.close()
    except:
        agents.add("pero")
        
    agents_dir = os.path.join(rust_db_dir, "agents")
    if os.path.exists(agents_dir):
        for name in os.listdir(agents_dir):
            if os.path.isdir(os.path.join(agents_dir, name)):
                agents.add(name)
    
    if not agents:
        agents.add("pero")
        
    for agent in sorted(agents):
        fix_agent(agent, sql_db_path, rust_db_dir)

if __name__ == "__main__":
    main()
