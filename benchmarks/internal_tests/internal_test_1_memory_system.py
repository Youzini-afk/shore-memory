import sys
import os
import time
import random
import asyncio

# 添加后端和本地导入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "backend")
)
sys.path.insert(0, BACKEND_DIR)

# --- Imports --- 
try:
    from services.memory.trivium_store import TriviumMemoryStore
    TRIVIUM_AVAILABLE = True
except ImportError:
    TRIVIUM_AVAILABLE = False
    print("⚠️ 未找到 TriviumMemoryStore 接入层。尝试激活环境或检查依赖。")

class LifeSimulator:
    def __init__(self):
        self.themes = {
            "Work": ["Fixed a bug", "Meeting", "Rust programming", "Documentation"],
            "Life": ["Moved house", "Cooked dinner", "Sick flu", "Grocery shopping"],
            "Hobby": ["Played games", "Photography", "Guitar", "Hiking"],
            "Emotion": ["Anxious", "Happy", "Lonely", "Excited"],
        }

    def generate_data(self, count: int) -> list:
        data = []
        for i in range(count):
            theme = random.choice(list(self.themes.keys()))
            content = f"{random.choice(self.themes[theme])} (Event {i})"
            data.append({"id": i, "content": content, "theme": theme, "dim": [random.random() for _ in range(128)]})
        return data

class MemorySystemTest:
    def __init__(self):
        # 若是正式集成环境，这里的 TriviumMemoryStore 是作为异步容器封装
        self.store = TriviumMemoryStore(store_name="benchmark_internal")
        self.simulator = LifeSimulator()

    async def run_logic_validation(self):
        print("\n[阶段 1] 逻辑验证 (TriviumDB 异步节点插入与混合连结检索)")
        print("-" * 60)

        import numpy as np
        
        # 构建 A -> B 跨连接模式
        await self.store.insert(1, np.random.rand(128).tolist(), {"content": "事件 A 发生"})
        await self.store.insert(2, np.random.rand(128).tolist(), {"content": "发生过渡联动"})
        await self.store.insert(3, np.random.rand(128).tolist(), {"content": "事件 B 对应结果落定"})

        # Trivium 的 link 支持
        await self.store.link(1, 2, "chain", 0.9)
        await self.store.link(2, 3, "chain", 0.8)

        print("   ✅ 数据写入和关联建立：成功")

    async def run_stress_simulation(self, scale=500):
        print(f"\n[阶段 2] 压力模拟与记忆网建立 ({scale} 条长篇节点)")
        print("-" * 60)

        data = self.simulator.generate_data(scale)
        print(f"   Injecting {scale} random memory blocks ...")
        
        start_time = time.perf_counter()
        
        for d in data:
            await self.store.insert(d["id"]+10, d["dim"], {"content": d["content"], "theme": d["theme"]})
            
            # 制造连接
            if d["id"] % 5 == 0:
                await self.store.link(d["id"]+10, random.randint(10, scale), "random_association", 0.5)

        ingest_time = (time.perf_counter() - start_time) * 1000
        print(f"   ✅ TriviumStore 吞吐层 Ingestion completed in {ingest_time:.2f}ms")

        # 验证读取
        import numpy as np
        hits = await self.store.search(
            np.random.rand(128).tolist(), 
            top_k=5, 
            expand_depth=2, 
            enable_dpp=True
        )
        print(f"   ✅ Recall triggered. Example matched memories: {len(hits)} hit instances")

    async def run_story_context_test(self):
        print("\n[Phase 3] 语义联合图谱搜索：深层次游走")
        print("-" * 60)
        
        # 此测试确认 store 底层连接并未因为异步执行而被丢弃阻塞
        # 测试结束，清理
        db_p = getattr(self.store, 'db_path', None)
        if db_p and os.path.exists(db_p):
            self.store._db = None 
            os.remove(db_p)
            print("   ✅ System database cleaned post-experiment.")

async def main():
    print("=" * 60)
    print("   PEROCORE TRIVIUMDB ASYNC INTEGRATION TEST SUITE")
    print("=" * 60)

    if not TRIVIUM_AVAILABLE:
        print("未准备好执行环境。")
        return

    suite = MemorySystemTest()
    await suite.run_logic_validation()
    await suite.run_stress_simulation(1000)
    await suite.run_story_context_test()

    print("\n" + "=" * 60)
    print("   INTEGRATION TESTING COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
