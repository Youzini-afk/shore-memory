import subprocess
import sys
import os


def run_script(path):
    print(f"\n>>> Executing {os.path.basename(path)}...")
    # 默认向基准测试 1 传递 1M 规模
    cmd = [sys.executable, path]
    if "benchmark_1" in path:
        cmd.append("1000000")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    # 仅包含三个核心基准测试
    scripts = [
        "benchmarks/benchmark_1_massive_scale.py",
        "benchmarks/benchmark_2_multi_hop_reasoning.py",
        "benchmarks/benchmark_3_real_world_integration.py",
    ]

    print("\n" + "=" * 80)
    print("      PeroCore 核心基准测试套件 (无偏见 & 综合)")
    print("=" * 80)
    print("Version: 3.0 (Consolidated)")
    current_time = (
        subprocess.check_output(
            ["powershell", 'Get-Date -Format "yyyy-MM-dd HH:mm:ss"']
        )
        .decode()
        .strip()
    )
    print(f"Time: {current_time}")
    print("-" * 80)

    success_count = 0
    for script in scripts:
        # 仅获取文件名并检查当前目录或 benchmarks/ 子文件夹
        script_filename = os.path.basename(script)
        if os.path.exists(script_filename):
            script_path = script_filename
        elif os.path.exists(script):
            script_path = script
        else:
            print(f"Error: Script {script_filename} not found.")
            continue

        if run_script(script_path):
            success_count += 1

    print("\n" + "=" * 80)
    print(f"      基准测试总结: {success_count}/{len(scripts)} 已完成")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
