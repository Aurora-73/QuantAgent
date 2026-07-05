#!/usr/bin/env python3
"""
QuantAgent - 跨平台一键安装脚本

用法:
  python scripts/install.py

要求:
  - Python 3.10+
  - Git
"""
import subprocess
import sys
import os
import shutil


def run_command(cmd, cwd=None, check=True):
    """运行命令并返回结果"""
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"ERROR: {cmd}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    return result


def check_command(name, install_url):
    """检查命令是否存在"""
    result = subprocess.run(f"which {name}" if sys.platform != "win32" else f"where {name}",
                           shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {name} 未安装")
        print(f"请从 {install_url} 安装")
        sys.exit(1)
    return True


def main():
    print("=" * 60)
    print("  QuantAgent 一键安装脚本")
    print("=" * 60)

    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("\n[1/6] 检查环境...")
    check_command("python", "https://www.python.org/downloads/")
    check_command("git", "https://git-scm.com/downloads")

    python_version = run_command("python --version", check=False).stdout.strip()
    git_version = run_command("git --version", check=False).stdout.strip()
    print(f"OK: Python: {python_version}")
    print(f"OK: Git: {git_version}")

    print("\n[2/6] 创建虚拟环境...")
    venv_path = os.path.join(current_dir, ".venv")
    
    needs_recreate = False
    if os.path.exists(venv_path):
        bin_dir = os.path.join(venv_path, "bin")
        scripts_dir = os.path.join(venv_path, "Scripts")
        if sys.platform == "win32" and os.path.exists(bin_dir) and not os.path.exists(scripts_dir):
            print("检测到 Linux 格式的虚拟环境，需要重新创建")
            needs_recreate = True
        else:
            print(".venv 已存在，跳过创建")
    
    if needs_recreate or not os.path.exists(venv_path):
        import shutil
        if os.path.exists(venv_path):
            shutil.rmtree(venv_path)
        run_command("python -m venv .venv", cwd=current_dir)
        print("OK: 虚拟环境创建成功")

    print("\n[3/6] 激活虚拟环境并安装依赖...")
    
    python_cmd = os.path.join(venv_path, "bin", "python")
    if os.path.exists(python_cmd):
        run_command(f'"{python_cmd}" -m pip install -r requirements.txt', cwd=current_dir)
    elif os.path.exists(os.path.join(venv_path, "Scripts", "python.exe")):
        python_cmd = os.path.join(venv_path, "Scripts", "python.exe")
        run_command(f'"{python_cmd}" -m pip install -r requirements.txt', cwd=current_dir)
    else:
        run_command("python -m pip install -r requirements.txt", cwd=current_dir)
    print("OK: 核心依赖安装成功")

    print("\n[4/6] 创建配置文件...")
    config_dir = os.path.join(current_dir, "configs")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    env_file = os.path.join(config_dir, ".env")
    env_example = os.path.join(config_dir, ".env.example")
    if not os.path.exists(env_file) and os.path.exists(env_example):
        shutil.copy(env_example, env_file)
        print("OK: 配置文件创建成功 (configs/.env)")
    else:
        print("配置文件已存在，跳过创建")

    print("\n[5/6] 创建必要目录...")
    dirs = ["data", "logs", "knowledge/daily", "knowledge/weekly", "knowledge/monthly"]
    for dir_name in dirs:
        dir_path = os.path.join(current_dir, dir_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"创建目录: {dir_name}")
    print("OK: 目录创建成功")

    print("\n[6/6] 验证安装...")
    
    python_candidates = [
        os.path.join(venv_path, "Scripts", "python.exe"),
        os.path.join(venv_path, "bin", "python.exe"),
        os.path.join(venv_path, "bin", "python"),
    ]
    python_cmd = None
    for candidate in python_candidates:
        if os.path.exists(candidate):
            python_cmd = candidate
            break
    
    if python_cmd is None:
        python_cmd = "python"
    
    result = run_command(f"{python_cmd} scripts/verify_project.py", cwd=current_dir, check=False)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("  OK: 安装成功！")
        print("=" * 60)
        print("\n使用方法:")
        if sys.platform == "win32":
            print("  1. 激活虚拟环境: .venv\\Scripts\\Activate.ps1")
        else:
            print("  1. 激活虚拟环境: source .venv/bin/activate")
        print("  2. 运行测试: python -m pytest")
        print("  3. 运行示例: python examples/00_quick_start.py")
        print("  4. 修改配置: 编辑 configs/.env")
        print("\n可选安装:")
        print("  Qlib: pip install qlib")
        print("  vnpy: pip install ta-lib vnpy vnpy-ctp")
        print("  OpenBB: pip install openbb")
    else:
        print("\n" + "=" * 60)
        print("  ERROR: 安装失败，请检查错误信息")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()