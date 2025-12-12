import os
import shutil
import subprocess


def build():
    # Check if 'dist' exists and clean it
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")

    # Base command
    cmd = [
        "uv",
        "run",
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "小维抽卡助手",
        "--clean",
        "--icon=logo.ico",
        "--add-data=logo.png;.",
        "--add-data=bg_small.png;.",
    ]

    # Add main script
    cmd.append("main.py")

    print(f"Running build command: {' '.join(cmd)}")
    print("-" * 50)
    print("Building optimized executable (Tkinter)...")

    try:
        subprocess.run(cmd, check=True)
        print("-" * 50)
        print("Build SUCCESS!")
        print(f"Executable created at: {os.path.abspath('dist/小维抽卡助手.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"Build FAILED with error code {e.returncode}")


if __name__ == "__main__":
    build()
