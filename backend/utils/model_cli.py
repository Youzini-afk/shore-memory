import argparse
import json
import os
import sys
from typing import Any, Dict

# 确保能找到 backend 包
# 添加当前脚本所在目录的上一级（即 backend 目录）到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)
sys.path.append(os.path.dirname(backend_dir))  # 添加项目根目录

from backend.core.model_manager import model_manager  # noqa: E402


def check_models() -> Dict[str, Any]:
    """检查所有模型状态"""
    results = {}

    # 检查所有预定义模型
    for model_key, model_info in model_manager.models.items():
        exists = model_manager.check_model_exists(model_key)
        path = model_manager.get_actual_model_path(model_key) if exists else None

        results[model_key] = {
            "exists": exists,
            "path": path,
            "type": model_info.type.value,
        }

    return results


def download_model(model_key: str, force: bool = False):
    """下载指定模型"""
    print(f"Downloading {model_key}...", flush=True)
    try:
        if model_key == "all":
            for key in model_manager.models:
                # print(f"Checking/Downloading {key}...", flush=True)
                model_manager.download_model(key, force)
        else:
            model_manager.download_model(model_key, force)
        print("Download complete.", flush=True)
    except Exception as e:
        print(f"Error downloading {model_key}: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="PeroCore Model Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # check command
    subparsers.add_parser("check", help="Check model status")

    # download command
    download_parser = subparsers.add_parser("download", help="Download models")
    download_parser.add_argument("--model", default="all", help="Model key (or 'all')")
    download_parser.add_argument(
        "--force", action="store_true", help="Force re-download"
    )

    args = parser.parse_args()

    if args.command == "check":
        status = check_models()
        print(json.dumps(status, indent=2))
    elif args.command == "download":
        download_model(args.model, args.force)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
