import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.path_resolver import path_resolver

logger = logging.getLogger(__name__)


@dataclass
class AssetMetadata:
    asset_id: str
    type: str  # plugin | persona | model_3d | mod | interface
    source: str  # official | local | workshop
    display_name: str
    version: str
    path: str  # 绝对路径
    workshop_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    def to_dict(self):
        return asdict(self)


class AssetRegistry:
    """
    资产注册表 (Asset Registry)
    负责扫描并注册所有可用资产，解决 asset_id 冲突（优先级：Local > Workshop > Official）。
    """

    _instance = None

    def __init__(self):
        self.assets: Dict[str, AssetMetadata] = {}  # asset_id -> AssetMetadata
        self.asset_type_index: Dict[str, List[str]] = {}  # type -> [asset_id]
        self._scanned = False

    def scan_all(self, force=False):
        """扫描所有已知的资产目录"""
        if self._scanned and not force:
            return
        logger.info("开始全量资产扫描...")
        self.assets.clear()
        self.asset_type_index.clear()

        # 定义扫描顺序 (优先级从低到高，后扫描的覆盖先扫描的)
        # 1. Official (内置)
        self._scan_official()

        # 2. Workshop (创意工坊)
        self._scan_workshop()

        # 3. Local (用户自定义)
        self._scan_local()

        self._scanned = True
        logger.info(f"资产扫描完成，共索引 {len(self.assets)} 个资产")

    def get_asset(self, asset_id: str) -> Optional[AssetMetadata]:
        """通过 ID 获取资产元数据"""
        if not self._scanned:
            self.scan_all()
        return self.assets.get(asset_id)

    def get_assets_by_type(self, asset_type: str) -> List[AssetMetadata]:
        """获取特定类型的所有资产"""
        if not self._scanned:
            self.scan_all()
        ids = self.asset_type_index.get(asset_type, [])
        return [self.assets[aid] for aid in ids if aid in self.assets]

    def _register_asset(self, meta: AssetMetadata):
        """注册单个资产，处理冲突"""
        existing = self.assets.get(meta.asset_id)
        if existing:
            logger.debug(
                f"资产覆盖: {meta.asset_id} ({existing.source} -> {meta.source})"
            )

        self.assets[meta.asset_id] = meta

        # 更新类型索引
        if meta.type not in self.asset_type_index:
            self.asset_type_index[meta.type] = []
        if meta.asset_id not in self.asset_type_index[meta.type]:
            self.asset_type_index[meta.type].append(meta.asset_id)

    def _load_asset_json(self, dir_path: Path, source: str) -> Optional[AssetMetadata]:
        """尝试从目录加载 asset.json 或 manifest.json 或 description.json"""
        # 优先查找 asset.json (新标准)
        asset_json_path = dir_path / "asset.json"
        manifest_path = dir_path / "manifest.json"  # 兼容旧版
        description_path = dir_path / "description.json"  # 兼容现有插件

        data = None

        if asset_json_path.exists():
            try:
                with open(asset_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"无法解析 asset.json: {asset_json_path}, error: {e}")
                return None
        elif manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    # 尝试从 manifest.json 中提取/转换元数据
                    if "asset_id" in raw:
                        data = raw
                    else:
                        # 临时兼容：为旧版 manifest 生成临时 asset_id
                        if "metadata" in raw and "name" in raw["metadata"]:
                            # Bedrock 模型
                            data = {
                                "asset_id": f"com.perocore.model.{raw['metadata']['name'].lower()}",
                                "type": "model_3d",
                                "display_name": raw["metadata"]["name"],
                                "version": raw["metadata"].get("version", "1.0.0"),
                                "config": raw,
                            }
                        # 插件 (旧版 manifest?)
                        elif "name" in raw and "entryPoint" in raw:
                            data = {
                                "asset_id": f"com.perocore.plugin.{raw['name'].lower()}",
                                "type": "plugin",
                                "display_name": raw["name"],
                                "version": raw.get("version", "1.0.0"),
                                "config": raw,
                            }
            except Exception as e:
                logger.warning(f"无法解析 manifest.json: {manifest_path}, error: {e}")
                return None
        elif description_path.exists():
            try:
                with open(description_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    # 如果已有 asset_id，直接使用新格式
                    if "asset_id" in raw:
                        data = raw
                    # 插件描述文件 (旧版兼容)
                    elif "name" in raw and "entryPoint" in raw:
                        data = {
                            "asset_id": f"com.perocore.plugin.{raw['name'].lower()}",
                            "type": "plugin",
                            "display_name": raw.get("displayName", raw["name"]),
                            "version": raw.get("version", "1.0.0"),
                            "config": raw,
                        }
            except Exception as e:
                logger.warning(
                    f"无法解析 description.json: {description_path}, error: {e}"
                )
                return None

        if data and "asset_id" in data:
            # 优先使用 display_name，兼容旧版 displayName
            display_name = data.get("display_name") or data.get("displayName", data["asset_id"])
            return AssetMetadata(
                asset_id=data["asset_id"],
                type=data.get("type", "unknown"),
                source=source,
                display_name=display_name,
                version=data.get("version", "1.0.0"),
                path=str(dir_path),  # 记录目录路径
                workshop_id=data.get("workshop_id"),
                config=data,  # 存储完整数据，便于其他模块访问
            )
        return None

    def _scan_directory_recursive(self, root_path: Path, source: str, depth=2):
        """递归扫描目录寻找 asset.json，同时支持 .pero 文件"""
        if not root_path.exists():
            return

        # os.walk 是自顶向下的。
        # 当我们修改 dirs 列表时，它会影响后续的遍历。
        for root, dirs, files in os.walk(root_path):
            current_path = Path(root)
            # 计算当前深度 (相对于 root_path)
            try:
                rel_path = current_path.relative_to(root_path)
                rel_depth = 0 if str(rel_path) == "." else len(rel_path.parts)
            except ValueError:
                continue

            # 1. 检查当前目录是否是资产 (manifest.json 等)
            meta = self._load_asset_json(current_path, source)
            if meta:
                self._register_asset(meta)
                # 找到资产后，停止向下递归当前资产目录的子目录
                dirs[:] = []
                continue

            # 2. 检查当前目录下是否有 .pero 文件 (作为独立资产)
            for file in files:
                if file.endswith(".pero"):
                    file_path = current_path / file
                    # 为 .pero 文件创建 AssetMetadata
                    # 防止与同名目录资产冲突 (通常不会同时存在)
                    asset_name = file.replace(".pero", "")
                    asset_id = f"com.perocore.model.{asset_name.lower()}"

                    # 检查是否已存在 (例如目录形式的同名资产)
                    if asset_id not in self.assets:
                        meta = AssetMetadata(
                            asset_id=asset_id,
                            type="model_3d",
                            source=source,
                            display_name=asset_name,
                            version="1.0.0",
                            path=str(file_path),
                            config={},
                        )
                        self._register_asset(meta)

            # 只有在非资产目录才判断深度限制
            # 如果当前深度已经达到或超过限制，并且当前目录不是资产，那么就不应该再扫描它的子目录了
            if rel_depth >= depth:
                dirs[:] = []

    def _scan_official(self):
        """扫描内置资产"""
        # 1. 3D 模型: @app/public/assets/3d
        model_root = path_resolver.resolve("@app/public/assets/3d")
        # 必须创建目录，否则 _scan_directory_recursive 会直接返回
        if not model_root.exists():
            # 在测试环境中，可能需要确保目录存在，但在实际环境中这应该是部署时就有的
            # 这里的逻辑没问题，如果不存在就不扫
            pass
        self._scan_directory_recursive(model_root, "official")

        # 2. 插件: @app/backend/nit_core/plugins
        plugin_root = path_resolver.resolve("@app/backend/nit_core/plugins")
        # 插件目录结构比较深，可能需要更深的扫描或特定逻辑
        # 目前插件是 plugins/<Category>/<PluginName>
        self._scan_directory_recursive(plugin_root, "official", depth=4)

        # 2.1 核心工具 (也是一种插件): @app/backend/nit_core/tools
        tools_root = path_resolver.resolve("@app/backend/nit_core/tools")
        self._scan_directory_recursive(tools_root, "official", depth=4)

        # 3. 人设: @app/backend/services/mdp/agents
        persona_root = path_resolver.resolve("@app/backend/services/mdp/agents")
        self._scan_directory_recursive(persona_root, "official", depth=2)

        # 4. 模组: @app/backend/mods
        mod_root = path_resolver.resolve("@app/backend/mods")
        self._scan_directory_recursive(mod_root, "official")

    def _scan_workshop(self):
        """扫描创意工坊资产"""
        workshop_root = path_resolver.get_root("@workshop")
        if not workshop_root.exists():
            return

        # 创意工坊结构: @workshop/content/<AppID>/<WorkshopID>/...
        # 假设我们直接映射到 @workshop/content/<WorkshopID> 或者简化为 @workshop/<WorkshopID>
        # 根据 path_resolver 的测试，目前是直接在 root 下
        self._scan_directory_recursive(workshop_root, "workshop", depth=2)

    def _scan_local(self):
        """扫描用户自定义资产"""
        local_root = path_resolver.resolve("@data/custom")
        # 在测试用例中，我们创建了 asset 但没有创建 custom 目录结构?
        # 测试用例中创建的是 self.data_dir / "custom/my_plugin"
        # path_resolver.resolve("@data/custom") -> self.data_dir / "custom"
        self._scan_directory_recursive(local_root, "local", depth=3)


# 全局单例
def get_asset_registry() -> AssetRegistry:
    if AssetRegistry._instance is None:
        AssetRegistry._instance = AssetRegistry()
    return AssetRegistry._instance


asset_registry = get_asset_registry()
