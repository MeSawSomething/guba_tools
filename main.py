"""
키보드 베이스 게임용 쿨타임 트래커 (Windows / macOS 지원)
- 지정한 키를 누르면 그 키(스킬)의 쿨타임 카운트다운을 별도의 항상-위 오버레이 창에 표시
- 쿨타임이 끝나면 소리 + 화면 깜빡임으로 알림
- 스킬(이름/키/쿨타임/알림음)은 설정 창에서 추가/수정/삭제할 수 있고, config.json 에
  저장되어 프로그램을 껐다 켜도 그대로 유지됩니다.

실행 전: pip install -r requirements.txt
실행: python main.py   (macOS는 python3 main.py)

주의: 전역 키 입력을 감지하기 위해 `pynput` 라이브러리를 사용합니다.
- Windows: 게임을 관리자 권한으로 실행 중이라면 이 프로그램도 관리자 권한으로
  실행해야 키 입력이 정상적으로 감지됩니다.
- macOS: 시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용(Accessibility) /
  입력 모니터링(Input Monitoring)에서 이 프로그램(또는 터미널)에 권한을 허용해야
  전역 키 입력이 감지됩니다.
일부 안티치트가 적용된 게임에서는 전역 키 후킹이 차단될 수 있습니다.
"""

import glob
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from pynput import keyboard as pynput_keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

from skills import (
    load_skills,
    save_skills,
    load_window_position,
    save_window_position,
    DEFAULT_SOUND,
)

# 프로그램이 이미 실행 중일 때 exe를 다시 클릭해도 중복 실행되지 않도록
# 막기 위한 이름 있는 뮤텍스(Windows) / 락 파일(그 외 OS).
_SINGLE_INSTANCE_NAME = "CooltimeTracker-SingleInstance-Mutex-3F2C9B7E"
_single_instance_handle = None


def acquire_single_instance_lock():
    """이미 실행 중인 인스턴스가 있으면 True, 없으면(=이번이 최초 실행) False."""
    global _single_instance_handle

    if sys.platform == "win32":
        import ctypes

        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, _SINGLE_INSTANCE_NAME)
        already_running = kernel32.GetLastError() == ERROR_ALREADY_EXISTS
        if handle and not already_running:
            _single_instance_handle = handle  # GC/뮤텍스 해제 방지를 위해 보관
        return already_running

    # macOS 등: 임시 디렉터리의 락 파일로 대체
    import os
    import tempfile

    lock_path = os.path.join(tempfile.gettempdir(), _SINGLE_INSTANCE_NAME + ".lock")
    try:
        import fcntl

        _single_instance_handle = open(lock_path, "w")
        try:
            fcntl.flock(_single_instance_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except OSError:
            return True
    except ImportError:
        return False


def find_icon_png():
    """exe(또는 main.py)와 같은 폴더에 있는 png 파일을 찾아 앱 아이콘으로 쓴다.
    여러 개면 이름순으로 첫 번째, 없으면 None(기본 아이콘 유지)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    try:
        pngs = sorted(glob.glob(os.path.join(base, "*.png")))
    except Exception:
        return None
    return pngs[0] if pngs else None

# ---- 색상 테마 ----
BG_COLOR = "#1e1e1e"
ACCENT = "#2d2d2d"
BAR_BG = "#3a3a3a"
BAR_COOLDOWN = "#5b7fff"
BAR_READY = "#39d353"
BAR_FLASH = "#ff9800"
TEXT_COLOR = "#ffffff"
MUTED_TEXT = "#aaaaaa"

BAR_WIDTH = 150
BAR_HEIGHT = 18

# 여러 키보드 표기 방식(tkinter keysym / pynput key 이름)을 하나의 표기로
# 통일하기 위한 별칭 매핑
KEY_ALIASES = {
    "return": "enter",
    "escape": "esc",
    "prior": "page up",
    "next": "page down",
    "control_l": "ctrl", "control_r": "ctrl",
    "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "shift_l": "shift", "shift_r": "shift",
    "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
    "cmd": "cmd", "cmd_l": "cmd", "cmd_r": "cmd",
    "meta_l": "cmd", "meta_r": "cmd",
}


def normalize_key_name(name):
    low = str(name).lower()
    return KEY_ALIASES.get(low, low)


def normalize_keysym(keysym):
    """설정 창에서 tkinter로 키를 캡처할 때 쓰는 정규화."""
    return normalize_key_name(keysym)


def pynput_key_to_name(key):
    """pynput이 전달하는 키 객체를 우리가 저장하는 문자열 형식으로 변환."""
    try:
        char = getattr(key, "char", None)
        if char:
            return normalize_key_name(char)
        name = getattr(key, "name", None)
        if name:
            return normalize_key_name(name)
    except Exception:
        pass
    return None


# ---- 알림음 목록 ----
# id: 저장/식별용 키, label: 설정 창 드롭다운에 보이는 이름
SOUND_CHOICES = [
    ("beep_default", "기본 알림음 (삐)"),
    ("beep_double", "높은 두번 알림음 (삐삐)"),
    ("beep_low", "낮은 알림음 (둥)"),
    ("beep_alarm", "경고음 (삐삐삐)"),
    ("system_asterisk", "시스템 알림음 1"),
    ("system_exclamation", "시스템 알림음 2"),
    ("system_hand", "시스템 알림음 3"),
    ("none", "무음 (화면 깜빡임만)"),
]
SOUND_LABELS = dict(SOUND_CHOICES)
SOUND_IDS = [sid for sid, _ in SOUND_CHOICES]

# macOS 알림음 매핑: (System 폴더에 내장된 aiff 파일명, 반복 재생 횟수)
MAC_SOUND_FILES = {
    "beep_default": ("Tink.aiff", 1),
    "beep_double": ("Pop.aiff", 2),
    "beep_low": ("Basso.aiff", 1),
    "beep_alarm": ("Sosumi.aiff", 3),
    "system_asterisk": ("Glass.aiff", 1),
    "system_exclamation": ("Ping.aiff", 1),
    "system_hand": ("Funk.aiff", 1),
}


def play_sound(sound_id):
    """스킬별로 선택된 알림음을 재생한다. 별도 스레드에서 실행되어 UI를 막지 않는다."""

    def worker():
        try:
            if sound_id == "none":
                return

            if sys.platform == "win32" and HAS_WINSOUND:
                if sound_id == "beep_default":
                    winsound.Beep(880, 180)
                elif sound_id == "beep_double":
                    winsound.Beep(1046, 110)
                    time.sleep(0.04)
                    winsound.Beep(1318, 110)
                elif sound_id == "beep_low":
                    winsound.Beep(330, 220)
                elif sound_id == "beep_alarm":
                    for _ in range(3):
                        winsound.Beep(988, 90)
                        time.sleep(0.03)
                elif sound_id == "system_asterisk":
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
                elif sound_id == "system_exclamation":
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                elif sound_id == "system_hand":
                    winsound.PlaySound("SystemHand", winsound.SND_ALIAS)
                else:
                    winsound.Beep(880, 180)

            elif sys.platform == "darwin":
                # macOS에는 winsound가 없으므로 내장 시스템 사운드(aiff)를 afplay로 재생
                filename, repeat = MAC_SOUND_FILES.get(sound_id, ("Tink.aiff", 1))
                path = f"/System/Library/Sounds/{filename}"
                for i in range(repeat):
                    subprocess.run(
                        ["afplay", path], check=False,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    if repeat > 1:
                        time.sleep(0.05)

            else:
                # 그 외 환경(Linux 등)에서는 시스템 벨로 대체
                print("\a", end="", flush=True)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


def position_near(win, ref, width=None, height=None, gap=10):
    """win을 ref 위젯 근처(오른쪽, 화면 밖이면 왼쪽)에 배치한다."""
    win.update_idletasks()
    if width is None:
        width = win.winfo_reqwidth()
    if height is None:
        height = win.winfo_reqheight()

    ref_x = ref.winfo_rootx()
    ref_y = ref.winfo_rooty()
    ref_w = ref.winfo_width()
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()

    x = ref_x + ref_w + gap
    if x + width > screen_w:
        x = ref_x - width - gap
    if x < 0:
        x = ref_x
    y = ref_y
    if y + height > screen_h:
        y = max(0, screen_h - height)

    win.geometry(f"{width}x{height}+{x}+{y}")


class SkillRuntime:
    """실행 중에만 쓰이는 스킬의 상태(카운트다운 진행 상황 등)."""

    def __init__(self, definition):
        self.name = definition["name"]
        self.key = definition["key"]
        self.cooldown = float(definition["cooldown"])
        self.sound = definition.get("sound", DEFAULT_SOUND)
        self.active = False
        self.start_time = 0.0
        self.remaining = 0.0
        self.notified = True  # 아직 "다 됐다" 알림을 안 보낸 상태인지


class CooldownOverlay:
    def __init__(self):
        self.key_queue = queue.Queue()
        self.skills = [SkillRuntime(d) for d in load_skills()]

        self.root = tk.Tk()
        self.root.withdraw()  # 실제 보이는 창은 아래의 Toplevel
        self._apply_app_icon()

        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)  # 제목표시줄 없는 오버레이 창
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        self.win.configure(bg=BG_COLOR)
        self._apply_saved_position()
        self.win.protocol("WM_DELETE_WINDOW", self.quit)

        self._drag_data = {"x": 0, "y": 0}
        self.rows = {}
        self._listener = None

        self._build_ui()
        self._start_key_hook()

        self.root.after(100, self._tick)

    # ---------------- UI 구성 ----------------

    def _build_ui(self):
        header = tk.Frame(self.win, bg=ACCENT, cursor="fleur")
        header.pack(fill="x")

        title = tk.Label(
            header, text="쿨타임", bg=ACCENT, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), padx=8, pady=4,
        )
        title.pack(side="left")

        btn_frame = tk.Frame(header, bg=ACCENT)
        btn_frame.pack(side="right")

        settings_btn = tk.Label(
            btn_frame, text="⚙", bg=ACCENT, fg=TEXT_COLOR,
            font=("Segoe UI", 10), padx=6, cursor="hand2",
        )
        settings_btn.pack(side="left")
        settings_btn.bind("<Button-1>", lambda e: self.open_settings())

        close_btn = tk.Label(
            btn_frame, text="✕", bg=ACCENT, fg=TEXT_COLOR,
            font=("Segoe UI", 10), padx=6, cursor="hand2",
        )
        close_btn.pack(side="left")
        close_btn.bind("<Button-1>", lambda e: self.quit())

        for widget in (header, title):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)

        self.body = tk.Frame(self.win, bg=BG_COLOR)
        self.body.pack(fill="both", expand=True, padx=6, pady=6)

        self._rebuild_rows()

        if not HAS_PYNPUT:
            warn = tk.Label(
                self.win,
                text="'pynput' 모듈이 없습니다.\npip install -r requirements.txt 실행 후 다시 켜주세요.",
                bg=BG_COLOR, fg="#ff8080", font=("Segoe UI", 8), justify="left",
            )
            warn.pack(padx=6, pady=(0, 6))

    def _rebuild_rows(self):
        for child in self.body.winfo_children():
            child.destroy()
        self.rows = {}

        if not self.skills:
            empty = tk.Label(
                self.body, text="설정(⚙)에서 스킬을 추가하세요",
                bg=BG_COLOR, fg=MUTED_TEXT, font=("Segoe UI", 9),
            )
            empty.pack(pady=10)
            return

        for skill in self.skills:
            row = tk.Frame(self.body, bg=BG_COLOR)
            row.pack(fill="x", pady=3)

            label = tk.Label(
                row, text=f"{skill.name} [{skill.key.upper()}]",
                bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 9),
                width=16, anchor="w",
            )
            label.pack(side="left")

            canvas = tk.Canvas(
                row, width=BAR_WIDTH, height=BAR_HEIGHT, bg=BAR_BG, highlightthickness=0
            )
            canvas.pack(side="left", padx=(4, 0))
            bar = canvas.create_rectangle(0, 0, BAR_WIDTH, BAR_HEIGHT, fill=BAR_READY, width=0)
            text_id = canvas.create_text(
                BAR_WIDTH / 2, BAR_HEIGHT / 2, text="준비", fill=TEXT_COLOR,
                font=("Segoe UI", 8, "bold"),
            )

            self.rows[id(skill)] = (canvas, bar, text_id)

    # ---------------- 아이콘 ----------------

    def _apply_app_icon(self):
        icon_path = find_icon_png()
        if not icon_path:
            return
        try:
            # PhotoImage 참조를 인스턴스에 보관해야 함 (안 그러면 가비지 컬렉션되어
            # 아이콘이 사라짐)
            self._icon_image = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, self._icon_image)
        except Exception:
            pass

    # ---------------- 창 드래그 / 위치 저장 ----------------

    def _apply_saved_position(self):
        x, y = 40, 40
        pos = load_window_position()
        if pos is not None:
            saved_x, saved_y = pos
            screen_w = self.win.winfo_screenwidth()
            screen_h = self.win.winfo_screenheight()
            # 저장 당시와 화면 해상도/모니터 구성이 달라져 창이 화면 밖으로
            # 완전히 벗어나는 경우에만 기본 위치로 되돌린다.
            if -100 <= saved_x <= screen_w - 50 and -100 <= saved_y <= screen_h - 50:
                x, y = saved_x, saved_y
        self.win.geometry(f"+{x}+{y}")

    def _start_drag(self, event):
        self._drag_data["x"] = event.x_root - self.win.winfo_x()
        self._drag_data["y"] = event.y_root - self.win.winfo_y()

    def _on_drag(self, event):
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self.win.geometry(f"+{x}+{y}")

    def _end_drag(self, event):
        save_window_position(self.win.winfo_x(), self.win.winfo_y())

    # ---------------- 전역 키 감지 ----------------

    def _start_key_hook(self):
        if not HAS_PYNPUT:
            return

        def on_press(key):
            name = pynput_key_to_name(key)
            if name:
                self.key_queue.put(name)

        try:
            self._listener = pynput_keyboard.Listener(on_press=on_press)
            self._listener.start()
        except Exception as ex:
            if sys.platform == "darwin":
                hint = (
                    "macOS: 시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용(또는 "
                    "입력 모니터링)에서 이 프로그램(혹은 터미널/Python)에 권한을 "
                    "허용한 뒤 다시 실행해보세요."
                )
            else:
                hint = (
                    "게임을 관리자 권한으로 실행 중이라면 이 프로그램도 관리자 권한으로 "
                    "다시 실행해보세요."
                )
            messagebox.showwarning(
                "경고",
                f"전역 키 입력을 감지할 수 없습니다.\n{hint}\n\n({ex})",
            )

    # ---------------- 메인 루프 ----------------

    def _tick(self):
        try:
            while True:
                key_name = self.key_queue.get_nowait()
                self._handle_key(key_name)
        except queue.Empty:
            pass

        now = time.time()
        for skill in self.skills:
            entry = self.rows.get(id(skill))
            if entry is None:
                continue
            canvas, bar, text_id = entry

            if skill.active:
                elapsed = now - skill.start_time
                remaining = skill.cooldown - elapsed
                if remaining <= 0:
                    skill.active = False
                    skill.remaining = 0
                    canvas.coords(bar, 0, 0, BAR_WIDTH, BAR_HEIGHT)
                    canvas.itemconfig(text_id, text="준비")
                    if not skill.notified:
                        skill.notified = True
                        self._on_ready(skill)
                    else:
                        canvas.itemconfig(bar, fill=BAR_READY)
                else:
                    skill.remaining = remaining
                    ratio = max(0.0, 1 - remaining / skill.cooldown)
                    canvas.coords(bar, 0, 0, BAR_WIDTH * ratio, BAR_HEIGHT)
                    canvas.itemconfig(bar, fill=BAR_COOLDOWN)
                    canvas.itemconfig(text_id, text=f"{remaining:0.1f}s")
            else:
                canvas.coords(bar, 0, 0, BAR_WIDTH, BAR_HEIGHT)
                canvas.itemconfig(text_id, text="준비")

        self.root.after(100, self._tick)

    def _handle_key(self, key_name):
        for skill in self.skills:
            if skill.key.lower() == key_name.lower():
                # 이미 쿨타임 중이면 무시 (게임에서도 쿨타임 중엔 다시 못 씀)
                if not skill.active:
                    skill.active = True
                    skill.start_time = time.time()
                    skill.remaining = skill.cooldown
                    skill.notified = False

    # ---------------- 쿨타임 완료 알림 ----------------

    def _on_ready(self, skill):
        self._flash(skill, 0)
        play_sound(skill.sound)

    def _flash(self, skill, count):
        entry = self.rows.get(id(skill))
        if not entry or count >= 10:
            if entry:
                canvas, bar, _ = entry
                canvas.itemconfig(bar, fill=BAR_READY)
            return
        canvas, bar, _ = entry
        color = BAR_FLASH if count % 2 == 0 else BAR_READY
        canvas.itemconfig(bar, fill=color)
        self.root.after(450, lambda: self._flash(skill, count + 1))

    def flash_skill_preview(self, skill):
        """알림음 미리듣기 테스트용: 해당 스킬의 '준비' 표시줄을 실제 알림과 같은 방식으로 깜빡인다."""
        self._flash(skill, 0)

    # ---------------- 설정 ----------------

    def open_settings(self):
        SettingsWindow(self)

    def apply_new_skills(self, definitions):
        save_skills(definitions)
        self.skills = [SkillRuntime(d) for d in definitions]
        self._rebuild_rows()

    def quit(self):
        try:
            save_window_position(self.win.winfo_x(), self.win.winfo_y())
        except Exception:
            pass
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


class SkillDialog:
    """스킬 추가/수정용 팝업. self.result 에 dict 또는 None 이 담긴다."""

    def __init__(self, parent, initial=None, app=None, skill=None):
        self.result = None
        self.app = app
        self.skill = skill
        self.top = tk.Toplevel(parent)
        self.top.title("스킬 추가" if initial is None else "스킬 수정")
        self.top.attributes("-topmost", True)
        self.top.resizable(False, False)
        self.top.grab_set()

        tk.Label(self.top, text="이름").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.name_var = tk.StringVar(value=initial["name"] if initial else "")
        tk.Entry(self.top, textvariable=self.name_var, width=18).grid(row=0, column=1, padx=8, columnspan=2)

        tk.Label(self.top, text="키").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.key_var = tk.StringVar(value=initial["key"] if initial else "")
        self.key_entry = tk.Entry(self.top, textvariable=self.key_var, width=12, state="readonly")
        self.key_entry.grid(row=1, column=1, padx=(8, 4), sticky="w")

        tk.Button(self.top, text="키 입력", command=self._capture_key).grid(row=1, column=2, padx=(0, 8))

        tk.Label(self.top, text="쿨타임(초)").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self.cd_var = tk.StringVar(value=str(initial["cooldown"]) if initial else "60")
        tk.Entry(self.top, textvariable=self.cd_var, width=18).grid(row=2, column=1, padx=8, columnspan=2)

        tk.Label(self.top, text="알림음").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        initial_sound = initial["sound"] if initial and initial.get("sound") in SOUND_IDS else DEFAULT_SOUND
        self.sound_var = tk.StringVar(value=SOUND_LABELS[initial_sound])
        sound_combo = ttk.Combobox(
            self.top, textvariable=self.sound_var, width=16, state="readonly",
            values=[label for _, label in SOUND_CHOICES],
        )
        sound_combo.grid(row=3, column=1, padx=(8, 4), sticky="w")
        tk.Button(self.top, text="▶ 미리듣기", command=self._preview_sound).grid(row=3, column=2, padx=(0, 8))

        btns = tk.Frame(self.top)
        btns.grid(row=4, column=0, columnspan=3, pady=10)
        tk.Button(btns, text="확인", width=8, command=self._ok).pack(side="left", padx=6)
        tk.Button(btns, text="취소", width=8, command=self.top.destroy).pack(side="left", padx=6)

        position_near(self.top, parent)

        self.top.wait_window()

    def _selected_sound_id(self):
        label = self.sound_var.get()
        for sid, lbl in SOUND_CHOICES:
            if lbl == label:
                return sid
        return DEFAULT_SOUND

    def _preview_sound(self):
        play_sound(self._selected_sound_id())
        if self.app is not None and self.skill is not None:
            self.app.flash_skill_preview(self.skill)

    def _capture_key(self):
        self.key_var.set("키를 누르세요...")

        def on_key(event):
            key_name = normalize_keysym(event.keysym)
            self.key_var.set(key_name)
            self.top.unbind("<Key>")

        self.top.bind("<Key>", on_key)
        self.top.focus_set()

    def _ok(self):
        name = self.name_var.get().strip()
        key = self.key_var.get().strip()
        try:
            cooldown = float(self.cd_var.get())
        except ValueError:
            messagebox.showerror("오류", "쿨타임은 숫자로 입력하세요.")
            return
        if not name or not key or key == "키를 누르세요..." or cooldown <= 0:
            messagebox.showerror("오류", "이름, 키, 쿨타임을 모두 입력하세요.")
            return
        self.result = {
            "name": name,
            "key": key,
            "cooldown": cooldown,
            "sound": self._selected_sound_id(),
        }
        self.top.destroy()


class SettingsWindow:
    def __init__(self, app: CooldownOverlay):
        self.app = app
        self.win = tk.Toplevel(app.win)
        self.win.title("쿨타임 트래커 설정")
        self.win.attributes("-topmost", True)
        position_near(self.win, app.win, width=380, height=360)

        self.tree = ttk.Treeview(
            self.win, columns=("name", "key", "cooldown", "sound"), show="headings", height=8
        )
        self.tree.heading("name", text="이름")
        self.tree.heading("key", text="키")
        self.tree.heading("cooldown", text="쿨타임(초)")
        self.tree.heading("sound", text="알림음")
        self.tree.column("name", width=110)
        self.tree.column("key", width=60, anchor="center")
        self.tree.column("cooldown", width=80, anchor="center")
        self.tree.column("sound", width=110)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", self._on_row_double_click)

        self._reload_tree()

        btns = tk.Frame(self.win)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(btns, text="추가", command=self.add_skill).pack(side="left", padx=2)
        tk.Button(btns, text="수정", command=self.edit_skill).pack(side="left", padx=2)
        tk.Button(btns, text="삭제", command=self.delete_skill).pack(side="left", padx=2)
        tk.Button(btns, text="닫기", command=self.win.destroy).pack(side="right", padx=2)

    def _reload_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, skill in enumerate(self.app.skills):
            sound_label = SOUND_LABELS.get(skill.sound, skill.sound)
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(skill.name, skill.key, skill.cooldown, sound_label),
            )

    def _current_definitions(self):
        return [
            {"name": s.name, "key": s.key, "cooldown": s.cooldown, "sound": s.sound}
            for s in self.app.skills
        ]

    def add_skill(self):
        dlg = SkillDialog(self.win, app=self.app)
        if dlg.result:
            definitions = self._current_definitions()
            definitions.append(dlg.result)
            self.app.apply_new_skills(definitions)
            self._reload_tree()

    def _on_row_double_click(self, event):
        # 더블클릭한 행을 우선 선택 상태로 만든 뒤 수정 창을 연다.
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.edit_skill()

    def edit_skill(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("안내", "수정할 스킬을 목록에서 선택하세요.")
            return
        idx = int(sel[0])
        current = self.app.skills[idx]
        dlg = SkillDialog(
            self.win,
            initial={
                "name": current.name,
                "key": current.key,
                "cooldown": current.cooldown,
                "sound": current.sound,
            },
            app=self.app,
            skill=current,
        )
        if dlg.result:
            definitions = self._current_definitions()
            definitions[idx] = dlg.result
            self.app.apply_new_skills(definitions)
            self._reload_tree()

    def delete_skill(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("안내", "삭제할 스킬을 목록에서 선택하세요.")
            return
        idx = int(sel[0])
        definitions = self._current_definitions()
        del definitions[idx]
        self.app.apply_new_skills(definitions)
        self._reload_tree()


if __name__ == "__main__":
    if acquire_single_instance_lock():
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("쿨타임 트래커", "쿨타임 트래커가 이미 실행 중입니다.")
        sys.exit(0)

    app = CooldownOverlay()
    app.run()
