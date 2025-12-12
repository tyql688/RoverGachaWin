import os
import sys
import re
import queue
import winreg
import tkinter as tk
import threading
from tkinter import ttk, scrolledtext
import ctypes
import datetime

import pyperclip

# Constants
GACHA_URL_PATTERN = r'(https://aki-gm-resources(?:-oversea)?\.aki-game\.(?:net|com)/aki/gacha/index\.html#/record[^"\'\s]*)'
LOG_FILE_REL_PATH = r"Client\Saved\Logs\Client.log"
DEBUG_LOG_REL_PATH = (
    r"Client\Binaries\Win64\ThirdParty\KrPcSdk_Global\KRSDKRes\KRSDKWebView\debug.log"
)


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class RoverGachaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("小维抽卡助手")
        self.root.geometry("640x450")
        self.root.configure(bg="#ffffff")

        # Icon Setup (Handle both Window and Taskbar)
        try:
            # 1. 设置窗口和任务栏图标 (.ico)
            ico_path = resource_path("logo.ico")
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)

            # 2. 设置标题栏小图标 (.png) - 这种方式对某些窗口管理器更有效
            png_path = resource_path("logo.png")
            if os.path.exists(png_path):
                icon_img = tk.PhotoImage(file=png_path)
                self.root.iconphoto(True, icon_img)

        except Exception:
            pass

        # Data
        self.found_url = None
        self.checked_paths = set()
        self.msg_queue = queue.Queue()
        self.candidates = []

        # UI Setup
        self._setup_ui()

        # Start queue polling
        self.root.after(100, self._process_queue)

    def _setup_ui(self):
        # Configure styles
        style = ttk.Style()
        style.theme_use("clam")

        # Labels
        style.configure(
            "Title.TLabel",
            background="#ffffff",
            foreground="#18181b",
            font=("Microsoft YaHei", 14, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background="#ffffff",
            foreground="#71717a",
            font=("Microsoft YaHei", 9),
        )

        # Button
        style.configure(
            "Action.TButton",
            background="#15803d",
            foreground="white",
            font=("Microsoft YaHei", 11, "bold"),
            borderwidth=0,
            focuscolor="none",
        )
        style.map(
            "Action.TButton",
            background=[("active", "#16a34a"), ("disabled", "#f4f4f5")],
            foreground=[("disabled", "#a1a1aa")],
        )

        # Main Layout
        main_frame = tk.Frame(self.root, bg="#ffffff")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)

        # Decoration (Background - Top Right)
        try:
            # 3. 设置右上角装饰图
            bg_path = resource_path("bg_small.png")
            if os.path.exists(bg_path):
                self.bg_img = tk.PhotoImage(file=bg_path)
                bg_label = tk.Label(
                    main_frame, image=self.bg_img, bg="#ffffff", borderwidth=0
                )
                # relx=1.0, rely=0.0, anchor="ne" (North East) -> 右上角
                # x=-20, y=20 -> 往左下移动，确保完全显示在窗口内
                bg_label.place(relx=1.0, rely=0.0, anchor="ne", x=0, y=0)
                # No lower() needed if we want it visible, but button is now shorter so no overlap
        except Exception:
            pass

        # Title
        lbl_title = ttk.Label(main_frame, text="小维抽卡助手", style="Title.TLabel")
        lbl_title.pack(pady=(0, 15))

        # Button
        self.btn_scan = ttk.Button(
            main_frame,
            text="⚡ 一键获取抽卡链接",
            style="Action.TButton",
            command=self.start_scan,
        )
        # 按钮短一点：不使用 fill=tk.X，改用 ipadx 增加内边距，默认居中
        self.btn_scan.pack(ipady=8, ipadx=30)

        # Log Area
        # 不需要滚动条，使用 tk.Text 替代 ScrolledText
        self.log_area = tk.Text(
            main_frame,
            bg="#f4f4f5",
            fg="#18181b",
            insertbackground="#18181b",
            font=("Consolas", 9),
            relief=tk.FLAT,
            padx=10,
            pady=10,
        )
        # pady=(30, 15) 增加顶部间距，防止遮挡背景图
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=(30, 15))
        self.log_area.tag_config("error", foreground="#ef4444")
        self.log_area.tag_config("success", foreground="#16a34a")
        self.log_area.tag_config("warning", foreground="#f97316")
        # 字体大一点
        self.log_area.tag_config(
            "url", foreground="#2563eb", font=("Consolas", 11, "bold")
        )
        self.log_area.tag_config("normal", foreground="#18181b")
        self.log_area.insert(tk.END, "点击按钮开始扫描...\n", "normal")
        self.log_area.configure(state="disabled")

        # Status
        self.lbl_status = ttk.Label(main_frame, text="准备就绪", style="Status.TLabel")
        self.lbl_status.pack()

    # --- Queue Processing (Main Thread) ---
    def _process_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "log":
                    text, tag = data
                    self._append_log(text, tag)
                elif msg_type == "status":
                    self.lbl_status.configure(text=data)
                elif msg_type == "finished":
                    found, url = data
                    self._on_scan_finished(found, url)
                self.msg_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._process_queue)

    def _append_log(self, text, tag="normal"):
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, text + "\n", tag)
        self.log_area.see(tk.END)
        self.log_area.configure(state="disabled")

    # --- Actions ---
    def start_scan(self):
        self.btn_scan.configure(state="disabled", text="正在扫描...")
        self.log_area.configure(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.configure(state="disabled")

        self.found_url = None
        self.checked_paths.clear()

        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _on_scan_finished(self, found, url):
        self.btn_scan.configure(state="normal", text="⚡ 一键获取抽卡链接")

        if found and url:
            try:
                pyperclip.copy(url)
                self._append_log("成功！URL 已自动复制到剪贴板。", "success")
                self._append_log(url, "url")
                self.lbl_status.configure(text="URL 已复制到剪贴板")
            except Exception as e:
                self._append_log(f"找到 URL 但复制失败: {e}", "error")
                self.lbl_status.configure(text="复制失败")
        else:
            self.lbl_status.configure(text="未找到 URL")

    # --- Workers (Background Thread) ---
    def _scan_thread(self):
        self.msg_queue.put(("log", ("正在自动扫描游戏路径...", "normal")))

        found = False
        try:
            self.candidates.clear()
            if self.scan_mui_cache():
                found = True
            if self.scan_firewall():
                found = True
            if self.scan_uninstall_registry():
                found = True
            if self.scan_common_paths():
                found = True

            if not self.candidates:
                self.msg_queue.put(("log", ("扫描完成，未找到有效的抽卡链接。", "error")))
                self.msg_queue.put(("log", ("请确认已打开过游戏内的抽卡历史记录。", "warning")))
                self.msg_queue.put(("finished", (False, "")))
            else:
                latest = self._select_latest_candidate(self.candidates)
                if latest:
                    self.found_url = latest["url"]
                    src_time = latest.get("time")
                    if src_time:
                        self.msg_queue.put(("log", (f"最新抽卡记录时间: {src_time.strftime('%Y-%m-%d %H:%M:%S')}", "normal")))
                    self.msg_queue.put(("log", (f"最新抽卡记录来源路径: {latest['path']}", "normal")))
                    self.msg_queue.put(("finished", (True, self.found_url)))
                else:
                    self.msg_queue.put(("log", ("扫描完成，但无法确定最新记录。", "warning")))
                    self.msg_queue.put(("finished", (False, "")))

        except Exception as e:
            self.msg_queue.put(("log", (f"发生错误: {e}", "error")))
            self.msg_queue.put(("finished", (False, "")))

    # --- Logic ---
    def check_game_path(self, path):
        # 1. 路径标准化与去重 (解决 D:/Games 和 D:\Games 重复问题)
        try:
            path = os.path.normpath(os.path.abspath(path))
        except Exception:
            return False

        path_lower = path.lower()
        if "onedrive" in path_lower:
            return False
        if path_lower in self.checked_paths:
            return False
        self.checked_paths.add(path_lower)

        if not os.path.exists(path):
            return False

        # 定义要检查的日志文件
        log_targets = [LOG_FILE_REL_PATH, DEBUG_LOG_REL_PATH]

        potential_dir_found = False

        for rel_path in log_targets:
            desc = os.path.basename(rel_path)
            full_path = os.path.join(path, rel_path)
            dir_path = os.path.dirname(full_path)

            # 2. 确定日志目录是否存在
            if os.path.exists(dir_path):
                if not potential_dir_found:
                    self.msg_queue.put(("log", (f"发现潜在游戏目录: {path}", "normal")))
                    potential_dir_found = True

                # 3. 确定日志文件是否存在
                if os.path.exists(full_path):
                    self.msg_queue.put(("log", (f"  └─ 发现日志文件: {desc}", "normal")))
                    # 4. 检查文件内容 (是否存在抽卡记录 & 是否过期)
                    record = self.extract_record_from_file(full_path)
                    if record and record.get("url"):
                        self.candidates.append(record)
                    else:
                        self.msg_queue.put(("log", (f"  └─ ⚠️ 文件 {desc} 中未找到抽卡链接", "warning")))
        return potential_dir_found

    def extract_url_from_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            found_url = None
            found_time = None
            for line in lines:
                matches = re.findall(GACHA_URL_PATTERN, line)
                if matches:
                    last_match = matches[-1]
                    found_url = last_match[0] if isinstance(last_match, tuple) else last_match
                    # 提取时间戳
                    ts_match = re.search(r"^\[(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2}):(\d{3})\]", line)
                    if ts_match:
                        y, m, d, H, M, S, ms = map(int, ts_match.groups())
                        found_time = datetime.datetime(y, m, d, H, M, S, ms * 1000)
                    else:
                        found_time = None

            if found_url:
                self.msg_queue.put(("log", (f"  └─ ✅ 成功提取到链接", "success")))
                if found_time:
                    time_str = found_time.strftime("%Y-%m-%d %H:%M:%S")
                    # 5. 检查是否过期 (30分钟)
                    if (datetime.datetime.now() - found_time).total_seconds() > 1800:
                         self.msg_queue.put(("log", (f"  └─ ⚠️ 链接生成于 {time_str}，已超过30分钟，可能已过期", "warning")))
                         self.msg_queue.put(("log", (f"  └─ 请在游戏中重新打开抽卡记录以刷新链接", "warning")))
                    else:
                         self.msg_queue.put(("log", (f"  └─ 链接生成于 {time_str}，状态有效 (30分钟内)", "success")))
                else:
                     self.msg_queue.put(("log", (f"  └─ 未能解析链接时间，无法判断时效性", "warning")))

                return found_url

        except Exception as e:
            self.msg_queue.put(("log", (f"  └─ 读取出错: {e}", "error")))
        return None

    def extract_record_from_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            found_url = None
            found_time = None
            for line in lines:
                matches = re.findall(GACHA_URL_PATTERN, line)
                if matches:
                    last_match = matches[-1]
                    found_url = last_match[0] if isinstance(last_match, tuple) else last_match
                    ts_match = re.search(r"^\[(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2}):(\d{3})\]", line)
                    if ts_match:
                        y, m, d, H, M, S, ms = map(int, ts_match.groups())
                        found_time = datetime.datetime(y, m, d, H, M, S, ms * 1000)
            if found_url:
                if found_time:
                    time_str = found_time.strftime("%Y-%m-%d %H:%M:%S")
                    if (datetime.datetime.now() - found_time).total_seconds() > 1800:
                        self.msg_queue.put(("log", (f"  └─ ⚠️ 链接生成于 {time_str}，已超过30分钟，可能已过期", "warning")))
                        self.msg_queue.put(("log", (f"  └─ 请在游戏中重新打开抽卡记录以刷新链接", "warning")))
                    else:
                        self.msg_queue.put(("log", (f"  └─ 链接生成于 {time_str}，状态有效 (30分钟内)", "success")))
                else:
                    self.msg_queue.put(("log", (f"  └─ 未能解析链接时间，无法判断时效性", "warning")))
                return {"url": found_url, "time": found_time, "path": file_path}
        except Exception as e:
            self.msg_queue.put(("log", (f"  └─ 读取出错: {e}", "error")))
        return None

    def _select_latest_candidate(self, candidates):
        valid = []
        for c in candidates:
            t = c.get("time")
            if t is None:
                try:
                    m = os.path.getmtime(c.get("path", ""))
                    t = datetime.datetime.fromtimestamp(m)
                except Exception:
                    t = None
            valid.append({"url": c["url"], "time": t, "path": c["path"]})
        valid = [x for x in valid if x["time"] is not None]
        if not valid:
            return candidates[0] if candidates else None
        valid.sort(key=lambda x: x["time"], reverse=True)
        return valid[0]

    def extract_url(self, base_path):
        # 这是一个旧的兼容方法，如果还有其他地方调用它，可以保留或重定向
        # 目前 check_game_path 已经改为调用 extract_url_from_file
        # 为了安全起见，保留此方法但指向新逻辑 (只检查第一个存在的日志)
        paths_to_check = [
            os.path.join(base_path, LOG_FILE_REL_PATH),
            os.path.join(base_path, DEBUG_LOG_REL_PATH),
        ]
        for p in paths_to_check:
            if os.path.exists(p):
                return self.extract_url_from_file(p)
        return None

    # Registry Helpers
    def scan_mui_cache(self):
        key_path = (
            r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
        )
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                i = 0
                found_any = False
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        name = (
                            name.decode("utf-8", errors="ignore")
                            if isinstance(name, bytes)
                            else str(name)
                        )
                        value = (
                            value.decode("utf-8", errors="ignore")
                            if isinstance(value, bytes)
                            else str(value)
                        )
                        if (
                            "wuthering" in value.lower()
                            and "client-win64-shipping.exe" in name.lower()
                        ):
                            parts = re.split(
                                r"[\\/]client[\\/]", name, flags=re.IGNORECASE
                            )
                            if len(parts) > 1:
                                if self.check_game_path(parts[0]):
                                    found_any = True
                        i += 1
                    except OSError:
                        break
                    except Exception:
                        i += 1
                        continue
        except Exception:
            pass
        return found_any

    def scan_firewall(self):
        key_path = r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                i = 0
                found_any = False
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        value = (
                            value.decode("utf-8", errors="ignore")
                            if isinstance(value, bytes)
                            else str(value)
                        )
                        if (
                            "wuthering" in value.lower()
                            and "client-win64-shipping" in value.lower()
                        ):
                            parts = value.split("|")
                            app_path = next(
                                (p[4:] for p in parts if p.startswith("App=")), None
                            )
                            if app_path:
                                path_parts = re.split(
                                    r"[\\/]client[\\/]", app_path, flags=re.IGNORECASE
                                )
                                if len(path_parts) > 1:
                                    if self.check_game_path(path_parts[0]):
                                        found_any = True
                        i += 1
                    except OSError:
                        break
                    except Exception:
                        i += 1
                        continue
        except Exception:
            pass
        return found_any

    def scan_uninstall_registry(self):
        roots = [
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
        ]
        found_any = False
        for hkey, subkey_path in roots:
            try:
                with winreg.OpenKey(hkey, subkey_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            with winreg.OpenKey(key, winreg.EnumKey(key, i)) as sub_key:
                                try:
                                    dn = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                                    dn = (
                                        dn.decode("utf-8", errors="ignore")
                                        if isinstance(dn, bytes)
                                        else str(dn)
                                    )
                                    if "wuthering" in dn.lower():
                                        ip = winreg.QueryValueEx(
                                            sub_key, "InstallPath"
                                        )[0]
                                        ip = (
                                            ip.decode("utf-8", errors="ignore")
                                            if isinstance(ip, bytes)
                                            else str(ip)
                                        )
                                        if self.check_game_path(ip):
                                            found_any = True
                                except Exception:
                                    pass
                        except OSError:
                            continue
            except Exception:
                pass
        return found_any

    def scan_common_paths(self):
        drives = [
            f"{d}:/" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:/")
        ]
        common_subs = [
            r"Wuthering Waves Game",
            r"Wuthering Waves\Wuthering Waves Game",
            r"Games\Wuthering Waves Game",
            r"Games\Wuthering Waves\Wuthering Waves Game",
            r"Program Files\Epic Games\WutheringWavesj3oFh",
            r"Program Files\Epic Games\WutheringWavesj3oFh\Wuthering Waves Game",
            # WeGame
            r"Games\WeGameApps\rail_apps\Wuthering Waves(2002137)",
            r"WeGameApps\rail_apps\Wuthering Waves(2002137)",
        ]
        found_any = False
        for drive in drives:
            for sub in common_subs:
                if self.check_game_path(os.path.join(drive, sub)):
                    found_any = True
        return found_any


if __name__ == "__main__":
    # Enable High DPI Awareness
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    app = RoverGachaApp(root)
    root.mainloop()
