"""
키보드 베이스 게임용 쿨타임 트래커 (Windows / macOS 지원)
- 지정한 키(또는 shift+z → shift+i 같은 조합/순서 입력)를 누르면 그 스킬의
  쿨타임 카운트다운을 별도의 항상-위 오버레이 창에 표시
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
    load_ui_scale,
    save_ui_scale,
    load_overlay_width,
    save_overlay_width,
    DEFAULT_SOUND,
)

# 조합키(예: shift+z+shift+i)의 스텝 사이에 허용하는 최대 간격(초).
# 이 시간 안에 다음 스텝이 들어오지 않으면 진행 상태를 리셋한다 —
# "1시간 전에 우연히 눌렀던 z" 같은 걸 기억하지 않기 위함.
STEP_TIMEOUT = 1.0

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

# 위/아래 테두리 드래그(세로) 시 폰트·막대 높이에 적용하는 배율의 허용 범위.
UI_SCALE_MIN = 0.7
UI_SCALE_MAX = 2.2

# 배율이 아무리 커져도 글자 크기는 이 값(px)을 넘지 않는다.
FONT_SIZE_MAX = 14

# 왼쪽/오른쪽 테두리 드래그(가로) 시 조절하는 창 너비(px)의 허용 범위.
# 가로 조절은 글씨 크기를 바꾸지 않고 막대만 늘였다 줄였다 한다.
OVERLAY_WIDTH_MIN = 220
OVERLAY_WIDTH_MAX = 900

# 창 가장자리에서 이 픽셀 이내로 마우스가 들어오면 "테두리"로 간주해서
# 커서가 바뀌고 드래그로 크기 조절이 시작된다.
RESIZE_MARGIN = 6

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


# 조합키의 "보조키"로 취급하는 키 이름들. 이 키들은 자체로 메인 키가 되는 게
# 아니라, 눌려있는 상태(held)만 추적해서 다른 메인 키와 함께 매칭에 쓰인다.
MODIFIER_NAMES = {"shift", "ctrl", "alt"}


def normalize_key_name(name):
    low = str(name).lower()
    return KEY_ALIASES.get(low, low)


def normalize_keysym(keysym):
    """설정 창에서 tkinter로 키를 캡처할 때 쓰는 정규화."""
    return normalize_key_name(keysym)


def pynput_key_to_name(key):
    """pynput이 전달하는 키 객체를 우리가 저장하는 문자열 형식으로 변환.

    문자는 항상 소문자로 정규화한다 — Shift 여부는 대소문자가 아니라 별도로
    추적하는 held-보조키 상태로 판단하므로(키보드 레이아웃에 따라 shift+숫자
    등은 아예 다른 문자가 나오기도 함), 여기서는 대소문자를 신경 쓰지 않는다.
    """
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


def steps_to_display(steps):
    """스텝 목록(각 스텝 = (보조키 집합, 메인 키))을 사람이 읽는 문자열로 변환.
    예: [({shift}, z), ({shift}, i)] -> "SHIFT+Z → SHIFT+I" """
    parts = []
    for mods, key in steps:
        mod_list = sorted(mods) if mods else []
        parts.append("+".join([m.upper() for m in mod_list] + [str(key).upper()]))
    return " → ".join(parts)


def steps_from_storage(raw_steps):
    """skills.py가 돌려주는 저장 형식(dict 리스트)을 런타임 형식
    (frozenset, key) 튜플 리스트로 변환."""
    result = []
    for item in raw_steps:
        mods = frozenset(normalize_key_name(m) for m in item.get("mods", []))
        key = normalize_key_name(item.get("key", ""))
        if key:
            result.append((mods, key))
    return result


def steps_to_storage(steps):
    """런타임 형식 (frozenset, key) 튜플 리스트를 config.json 저장 형식으로 변환."""
    return [{"mods": sorted(mods), "key": key} for mods, key in steps]


# tkinter 이벤트의 state 비트마스크에서 보조키 여부를 읽어올 때 쓰는 비트.
# Alt는 플랫폼마다 다른 비트를 쓰는데, Windows에서 Mod1(0x0008)은 Num Lock
# 토글 상태라서 그대로 쓰면 Num Lock이 켜져있을 때마다 Alt가 눌린 걸로
# 오판하게 된다 — 그래서 플랫폼별로 분기한다.
_STATE_SHIFT = 0x0001
_STATE_CONTROL = 0x0004
_STATE_ALT = 0x20000 if sys.platform == "win32" else (0x20000 | 0x0008)


_DEBUG_LOG_PATH = os.path.join(
    os.environ.get("TEMP") or os.environ.get("TMP") or ".", "cooltime_tracker_capture_debug.log"
)


def _debug_log(msg, truncate=False):
    try:
        with open(_DEBUG_LOG_PATH, "w" if truncate else "a", encoding="utf-8") as f:
            f.write(f"{time.time():.3f} {msg}\n")
    except Exception:
        pass


def tk_event_modifiers(event):
    """tkinter 키 이벤트가 발생한 "그 순간" 실제로 눌려있던 보조키 집합을
    event.state 비트마스크로 판단한다.

    별도의 Shift/Ctrl/Alt keydown을 우리가 직접 추적해서 만드는 것보다 훨씬
    안정적이다 — event.state는 OS가 그 키 이벤트와 함께 실어 보내주는 "그
    순간의" 실제 보조키 상태라서, 짧은 시간 안에 보조키를 뗐다 다시 누를 때
    발생할 수 있는 이벤트 순서 꼬임/유실의 영향을 받지 않는다.
    """
    state = getattr(event, "state", 0)
    mods = set()
    if state & _STATE_SHIFT:
        mods.add("shift")
    if state & _STATE_CONTROL:
        mods.add("ctrl")
    if state & _STATE_ALT:
        mods.add("alt")
    return mods


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
        # steps: [(보조키 frozenset, 메인 키), ...] — 순서대로 눌러야 완주되는 시퀀스.
        self.steps = steps_from_storage(definition["key"])
        self.cooldown = float(definition["cooldown"])
        self.sound = definition.get("sound", DEFAULT_SOUND)
        self.active = False
        self.start_time = 0.0
        self.remaining = 0.0
        self.notified = True  # 아직 "다 됐다" 알림을 안 보낸 상태인지

        # 시퀀스 진행 상태: 지금까지 몇 번째 스텝까지 맞았는지, 마지막으로
        # 스텝이 맞은 시각(타임아웃 판정용).
        self.progress = 0
        self.last_step_time = 0.0


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
        self._resize_edges = None
        self._resize_data = {"x_root": 0, "y_root": 0, "scale": 1.0}
        self.rows = {}
        self._listener = None
        self.ui_scale = load_ui_scale()
        self.overlay_width = load_overlay_width()  # None이면 내용에 맞춘 자동 너비

        self._build_ui()
        self._start_key_hook()

        self.root.after(100, self._tick)

        # macOS: 게임 창이 포커스를 가져가면 -topmost 가 밀려서 오버레이가
        # 게임 뒤로 숨는 경우가 있어, 주기적으로 다시 맨 앞으로 끌어올린다.
        if sys.platform == "darwin":
            self.root.after(700, self._reassert_topmost)

    # ---------------- UI 구성 / 크기 조절 ----------------

    def _font(self, base_size, bold=False):
        size = max(6, min(FONT_SIZE_MAX, round(base_size * self.ui_scale)))
        return ("Segoe UI", size, "bold") if bold else ("Segoe UI", size)

    def _bar_height(self):
        # 막대 높이/폰트는 세로 리사이즈(ui_scale)를 따른다. 너비는 가로
        # 리사이즈로 창이 넓어지면 막대가 늘어나는 식으로 별도 처리한다
        # (canvas를 fill="x"로 채워서 늘어나므로 여기서 배율을 곱하지 않는다).
        return round(BAR_HEIGHT * self.ui_scale)

    def _reapply_overlay_width(self):
        """가로로 직접 지정해둔 창 너비가 있으면(overlay_width), 방금
        _rebuild_rows()로 자식 위젯이 새로 만들어지며 리셋됐을 자동 크기맞춤을
        덮어써서 사용자가 정한 너비를 유지한다."""
        if self.overlay_width is None:
            return
        self.win.update_idletasks()
        width = max(OVERLAY_WIDTH_MIN, min(OVERLAY_WIDTH_MAX, self.overlay_width))
        height = self.win.winfo_reqheight()
        x, y = self.win.winfo_x(), self.win.winfo_y()
        self.win.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self):
        self.header = tk.Frame(self.win, bg=ACCENT, cursor="fleur")
        self.header.pack(fill="x")

        self.title_label = tk.Label(
            self.header, text="쿨타임", bg=ACCENT, fg=TEXT_COLOR,
            font=self._font(9, bold=True), padx=8, pady=4,
        )
        self.title_label.pack(side="left")

        btn_frame = tk.Frame(self.header, bg=ACCENT)
        btn_frame.pack(side="right")

        self.settings_btn = tk.Label(
            btn_frame, text="⚙", bg=ACCENT, fg=TEXT_COLOR,
            font=self._font(10), padx=6, cursor="hand2",
        )
        self.settings_btn.pack(side="left")
        self.settings_btn.bind("<Button-1>", lambda e: self.open_settings())

        self.close_btn = tk.Label(
            btn_frame, text="✕", bg=ACCENT, fg=TEXT_COLOR,
            font=self._font(10), padx=6, cursor="hand2",
        )
        self.close_btn.pack(side="left")
        self.close_btn.bind("<Button-1>", lambda e: self.quit())

        for widget in (self.header, self.title_label):
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

        # overrideredirect 창은 OS의 기본 리사이즈 테두리가 없어서, 창 가장자리
        # 근처에서 커서를 바꾸고 드래그로 크기를 조절하는 것도 직접 구현한다.
        # self.win에 바인딩해두면 bindtag 전파로 모든 자식 위젯 위에서도 동작한다.
        self.win.bind("<Motion>", self._on_window_motion)
        self.win.bind("<Button-1>", self._on_window_press)
        self.win.bind("<B1-Motion>", self._on_border_drag)
        self.win.bind("<ButtonRelease-1>", self._on_window_release)

    def _rebuild_rows(self):
        for child in self.body.winfo_children():
            child.destroy()
        self.rows = {}

        bar_height = self._bar_height()

        if not self.skills:
            empty = tk.Label(
                self.body, text="설정(⚙)에서 스킬을 추가하세요",
                bg=BG_COLOR, fg=MUTED_TEXT, font=self._font(9),
            )
            empty.pack(pady=10)
            self._reapply_overlay_width()
            return

        for skill in self.skills:
            row = tk.Frame(self.body, bg=BG_COLOR)
            row.pack(fill="x", pady=3)

            label = tk.Label(
                row, text=f"{skill.name} [{steps_to_display(skill.steps)}]",
                bg=BG_COLOR, fg=TEXT_COLOR, font=self._font(9),
                width=16, anchor="w",
            )
            label.pack(side="left")

            # 막대(canvas)는 fill="x"+expand로 남은 가로 공간을 채운다 — 가로
            # 테두리 드래그로 창이 넓어지면 이 막대가 늘어나는 방식.
            canvas = tk.Canvas(
                row, width=BAR_WIDTH, height=bar_height, bg=BAR_BG, highlightthickness=0
            )
            canvas.pack(side="left", fill="x", expand=True, padx=(4, 0))
            bar = canvas.create_rectangle(0, 0, BAR_WIDTH, bar_height, fill=BAR_READY, width=0)
            text_id = canvas.create_text(
                BAR_WIDTH / 2, bar_height / 2, text="준비", fill=TEXT_COLOR,
                font=self._font(8, bold=True),
            )

            self.rows[id(skill)] = (canvas, bar, text_id)

        self._reapply_overlay_width()

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
        if self._resize_edges:
            return  # 테두리 리사이즈 중이면 창 이동은 무시
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self.win.geometry(f"+{x}+{y}")

    def _end_drag(self, event):
        if self._resize_edges:
            return
        save_window_position(self.win.winfo_x(), self.win.winfo_y())

    # ---------------- 테두리 드래그 크기 조절 ----------------

    def _edge_zone(self, rel_x, rel_y, width, height):
        edges = set()
        if rel_x <= RESIZE_MARGIN:
            edges.add("left")
        elif rel_x >= width - RESIZE_MARGIN:
            edges.add("right")
        if rel_y <= RESIZE_MARGIN:
            edges.add("top")
        elif rel_y >= height - RESIZE_MARGIN:
            edges.add("bottom")
        return edges

    @staticmethod
    def _cursor_for_edges(edges):
        if edges in ({"top", "left"}, {"bottom", "right"}):
            return "size_nw_se"
        if edges in ({"top", "right"}, {"bottom", "left"}):
            return "size_ne_sw"
        if edges:
            return "size_we" if ("left" in edges or "right" in edges) else "size_ns"
        return ""

    def _on_window_motion(self, event):
        if self._resize_edges is not None:
            return  # 드래그 중에는 _on_border_drag가 처리
        rel_x = event.x_root - self.win.winfo_rootx()
        rel_y = event.y_root - self.win.winfo_rooty()
        edges = self._edge_zone(rel_x, rel_y, self.win.winfo_width(), self.win.winfo_height())
        cursor = self._cursor_for_edges(edges)
        self.win.config(cursor=cursor)
        # header/title은 기본적으로 "fleur"(이동) 커서를 쓰는데, 가장자리
        # 근처에서는 리사이즈 커서가 우선하도록 덮어쓴다.
        move_cursor = cursor or "fleur"
        self.header.config(cursor=move_cursor)
        self.title_label.config(cursor=move_cursor)

    def _on_window_press(self, event):
        rel_x = event.x_root - self.win.winfo_rootx()
        rel_y = event.y_root - self.win.winfo_rooty()
        edges = self._edge_zone(rel_x, rel_y, self.win.winfo_width(), self.win.winfo_height())
        if not edges:
            self._resize_edges = None
            return
        self._resize_edges = edges
        self._resize_data["x_root"] = event.x_root
        self._resize_data["y_root"] = event.y_root
        self._resize_data["scale"] = self.ui_scale
        self._resize_data["width"] = self.win.winfo_width()
        self._resize_data["win_x"] = self.win.winfo_x()
        self._resize_data["win_y"] = self.win.winfo_y()

    def _on_border_drag(self, event):
        if not self._resize_edges:
            return
        dx = event.x_root - self._resize_data["x_root"]
        dy = event.y_root - self._resize_data["y_root"]

        # 가로(왼쪽/오른쪽): 글씨 크기는 그대로 두고 창 너비(막대 길이)만
        # 실제 드래그한 픽셀만큼 그대로 늘였다 줄인다.
        if "left" in self._resize_edges:
            width = self._resize_data["width"] - dx
            width = max(OVERLAY_WIDTH_MIN, min(OVERLAY_WIDTH_MAX, width))
            new_x = self._resize_data["win_x"] + (self._resize_data["width"] - width)
            self.overlay_width = width
            self.win.geometry(f"{width}x{self.win.winfo_height()}+{new_x}+{self._resize_data['win_y']}")
        elif "right" in self._resize_edges:
            width = self._resize_data["width"] + dx
            width = max(OVERLAY_WIDTH_MIN, min(OVERLAY_WIDTH_MAX, width))
            self.overlay_width = width
            self.win.geometry(
                f"{width}x{self.win.winfo_height()}+{self._resize_data['win_x']}+{self._resize_data['win_y']}"
            )

        # 세로(위/아래): 기존처럼 배율(폰트/막대 높이)을 조절한다.
        if "top" in self._resize_edges or "bottom" in self._resize_edges:
            signed_dy = -dy if "top" in self._resize_edges else dy
            new_scale = self._resize_data["scale"] + signed_dy / 200.0
            new_scale = max(UI_SCALE_MIN, min(UI_SCALE_MAX, new_scale))
            if new_scale != self.ui_scale:
                self._apply_ui_scale(new_scale)

    def _on_window_release(self, event):
        if self._resize_edges:
            if "left" in self._resize_edges or "right" in self._resize_edges:
                save_overlay_width(self.overlay_width)
            if "top" in self._resize_edges or "bottom" in self._resize_edges:
                save_ui_scale(self.ui_scale)
            save_window_position(self.win.winfo_x(), self.win.winfo_y())
        self._resize_edges = None

    def _apply_ui_scale(self, scale):
        self.ui_scale = scale
        self.title_label.config(font=self._font(9, bold=True))
        self.settings_btn.config(font=self._font(10))
        self.close_btn.config(font=self._font(10))
        self._rebuild_rows()

    # ---------------- 전역 키 감지 ----------------

    def _start_key_hook(self):
        # 현재 눌려있는 보조키(shift/ctrl/alt) 집합. on_press에서 추가, on_release에서
        # 제거해서 "그 순간 눌려있어야 하는 보조키 집합"을 실시간으로 추적한다.
        self._held_mods = set()

        if not HAS_PYNPUT:
            return

        def on_press(key):
            name = pynput_key_to_name(key)
            if not name:
                return
            if name in MODIFIER_NAMES:
                self._held_mods.add(name)
                return
            self.key_queue.put((frozenset(self._held_mods), name))

        def on_release(key):
            name = pynput_key_to_name(key)
            if name in MODIFIER_NAMES:
                self._held_mods.discard(name)

        try:
            self._listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
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

    # ---------------- macOS: 항상 위 유지 ----------------

    def _reassert_topmost(self):
        try:
            # 껐다 켜야 macOS 창 서버가 쌓임 순서를 다시 계산해서 앞으로 나온다.
            self.win.attributes("-topmost", False)
            self.win.attributes("-topmost", True)
            self.win.lift()
        except tk.TclError:
            pass
        self.root.after(700, self._reassert_topmost)

    # ---------------- 메인 루프 ----------------

    def _tick(self):
        try:
            while True:
                mods, key_name = self.key_queue.get_nowait()
                self._handle_key(mods, key_name)
        except queue.Empty:
            pass

        now = time.time()
        for skill in self.skills:
            entry = self.rows.get(id(skill))
            if entry is None:
                continue
            canvas, bar, text_id = entry
            # 가로 리사이즈로 canvas가 fill="x"로 늘어날 수 있으므로, 설정값이
            # 아니라 실제 렌더링된 크기를 읽어야 한다.
            bar_width, bar_height = canvas.winfo_width(), canvas.winfo_height()
            canvas.coords(text_id, bar_width / 2, bar_height / 2)

            if skill.active:
                elapsed = now - skill.start_time
                remaining = skill.cooldown - elapsed
                if remaining <= 0:
                    skill.active = False
                    skill.remaining = 0
                    canvas.coords(bar, 0, 0, bar_width, bar_height)
                    canvas.itemconfig(text_id, text="준비")
                    if not skill.notified:
                        skill.notified = True
                        self._on_ready(skill)
                    else:
                        canvas.itemconfig(bar, fill=BAR_READY)
                else:
                    skill.remaining = remaining
                    ratio = max(0.0, 1 - remaining / skill.cooldown)
                    canvas.coords(bar, 0, 0, bar_width * ratio, bar_height)
                    canvas.itemconfig(bar, fill=BAR_COOLDOWN)
                    canvas.itemconfig(text_id, text=f"{remaining:0.1f}s")
            else:
                canvas.coords(bar, 0, 0, bar_width, bar_height)
                canvas.itemconfig(text_id, text="준비")

        self.root.after(100, self._tick)

    def _handle_key(self, mods, key_name):
        now = time.time()
        for skill in self.skills:
            self._advance_skill(skill, mods, key_name, now)

    def _advance_skill(self, skill, mods, key_name, now):
        """스킬의 시퀀스 진행 상태를 이번에 눌린 (보조키 집합, 메인 키)와 비교해서
        전진시키거나 리셋한다. 끝까지 다 맞으면 쿨타임을 시작한다."""
        if not skill.steps:
            return

        # 스텝 사이 허용 간격을 넘겼으면 진행 상태를 리셋 (오래 전에 눌렀던
        # 키를 기억하지 않기 위함).
        if skill.progress > 0 and (now - skill.last_step_time) > STEP_TIMEOUT:
            skill.progress = 0

        expected_mods, expected_key = skill.steps[skill.progress]
        matched = (mods == expected_mods and key_name == expected_key)

        if not matched and skill.progress > 0:
            # 다음 기대 스텝과는 안 맞아도, 시퀀스의 첫 스텝과는 맞을 수 있음 —
            # 그 경우 처음부터 즉시 재시작할 수 있게 한다.
            skill.progress = 0
            first_mods, first_key = skill.steps[0]
            matched = (mods == first_mods and key_name == first_key)

        if not matched:
            return

        skill.progress += 1
        skill.last_step_time = now

        if skill.progress >= len(skill.steps):
            skill.progress = 0
            # 이미 쿨타임 중이면 무시 (게임에서도 쿨타임 중엔 다시 못 씀)
            if not skill.active:
                skill.active = True
                skill.start_time = now
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
        # 시퀀스(런타임 형식): [(보조키 frozenset, 메인 키), ...]
        self._steps = steps_from_storage(initial["key"]) if initial else []
        self._capturing = False
        self._capture_last_key = None

        self.top = tk.Toplevel(parent)
        self.top.title("스킬 추가" if initial is None else "스킬 수정")
        self.top.attributes("-topmost", True)
        self.top.resizable(False, False)
        self.top.grab_set()
        self.top.protocol("WM_DELETE_WINDOW", self._cancel)

        tk.Label(self.top, text="이름").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.name_var = tk.StringVar(value=initial["name"] if initial else "")
        self.name_var.trace_add(
            "write",
            lambda *a: _debug_log(f"NAME_VAR -> {self.name_var.get()!r} (capturing={self._capturing})"),
        )
        self.name_entry = tk.Entry(self.top, textvariable=self.name_var, width=18)
        self.name_entry.grid(row=0, column=1, padx=8, columnspan=3, sticky="w")
        self.name_entry.bind("<FocusIn>", self._stop_capture_on_other_field_focus)

        tk.Label(self.top, text="키").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.key_var = tk.StringVar(value=steps_to_display(self._steps))
        self.key_entry = tk.Entry(self.top, textvariable=self.key_var, width=20, state="readonly")
        self.key_entry.grid(row=1, column=1, padx=(8, 4), sticky="w")

        self.capture_btn = tk.Button(self.top, text="키 입력", command=self._toggle_capture)
        self.capture_btn.grid(row=1, column=2, padx=(0, 4))
        tk.Button(self.top, text="지우기", command=self._clear_capture).grid(row=1, column=3, padx=(0, 8))

        tk.Label(
            self.top, text="여러 키를 순서대로 눌러 조합/연계 입력을 만들 수 있어요. (예: Shift+Z → I)",
            fg="#777777", font=("Segoe UI", 7),
        ).grid(row=2, column=0, columnspan=4, sticky="w", padx=8)

        tk.Label(self.top, text="쿨타임(초)").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        self.cd_var = tk.StringVar(value=str(initial["cooldown"]) if initial else "60")
        self.cd_var.trace_add(
            "write",
            lambda *a: _debug_log(f"CD_VAR -> {self.cd_var.get()!r} (capturing={self._capturing})"),
        )
        self.cd_entry = tk.Entry(self.top, textvariable=self.cd_var, width=18)
        self.cd_entry.grid(row=3, column=1, padx=8, columnspan=3, sticky="w")
        self.cd_entry.bind("<FocusIn>", self._stop_capture_on_other_field_focus)

        tk.Label(self.top, text="알림음").grid(row=4, column=0, sticky="w", padx=8, pady=6)
        initial_sound = initial["sound"] if initial and initial.get("sound") in SOUND_IDS else DEFAULT_SOUND
        self.sound_var = tk.StringVar(value=SOUND_LABELS[initial_sound])
        sound_combo = ttk.Combobox(
            self.top, textvariable=self.sound_var, width=16, state="readonly",
            values=[label for _, label in SOUND_CHOICES],
        )
        sound_combo.grid(row=4, column=1, padx=(8, 4), sticky="w")
        tk.Button(self.top, text="▶ 미리듣기", command=self._preview_sound).grid(row=4, column=2, columnspan=2, padx=(0, 8))

        btns = tk.Frame(self.top)
        btns.grid(row=5, column=0, columnspan=4, pady=10)
        tk.Button(btns, text="확인", width=8, command=self._ok).pack(side="left", padx=6)
        tk.Button(btns, text="취소", width=8, command=self._cancel).pack(side="left", padx=6)

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

    # ---------------- 키(조합/순서) 캡처 ----------------

    def _toggle_capture(self):
        if self._capturing:
            self._finish_capture()
        else:
            self._start_capture()

    def _start_capture(self):
        _debug_log("=== START CAPTURE ===", truncate=True)
        _debug_log(f"focus before start: {self.top.focus_get()!r}")
        self._capturing = True
        self._steps = []
        self._capture_last_key = None
        self.key_var.set("입력 대기 중... (다 누르면 완료를 클릭)")
        self.capture_btn.config(text="완료")
        # 캡처 중 눌리는 키가 (포커스가 실제로 어디 있든) 이름/쿨타임 칸으로
        # 새서 텍스트가 입력되지 않도록, 아예 편집 불가 상태로 잠근다.
        self.name_entry.config(state="disabled")
        self.cd_entry.config(state="disabled")
        _debug_log(f"name_entry state={self.name_entry.cget('state')} cd_entry state={self.cd_entry.cget('state')}")
        self.top.bind("<KeyPress>", self._on_capture_keydown)
        self.top.bind("<KeyRelease>", self._on_capture_keyup)
        # 캡처 도중 포커스가 (윈도우 IME 전환 등 OS 사정으로) 다른 창으로
        # 빠지면 그 이후 키 입력이 전부 유실된다 — 즉시 되찾아오도록 감시한다.
        self.top.bind("<FocusOut>", self._on_capture_focus_out)
        self.top.lift()
        self.top.focus_force()
        _debug_log(f"focus after focus_force: {self.top.focus_get()!r}")

    def _on_capture_focus_out(self, event):
        if self._capturing:
            self.top.after(10, self._reclaim_capture_focus)

    def _reclaim_capture_focus(self):
        if not self._capturing:
            return
        try:
            self.top.lift()
            self.top.focus_force()
        except tk.TclError:
            pass

    def _on_capture_keydown(self, event):
        keysym = normalize_keysym(event.keysym)
        _debug_log(
            f"KEYDOWN raw={event.keysym!r} norm={keysym!r} widget={event.widget!r} "
            f"focus={self.top.focus_get()!r} name_state={self.name_entry.cget('state')} "
            f"cd_state={self.cd_entry.cget('state')}"
        )
        if not keysym:
            return
        if keysym in MODIFIER_NAMES:
            return  # 보조키 단독 입력은 스텝으로 기록하지 않는다
        if keysym == self._capture_last_key:
            return  # 키를 계속 누르고 있을 때의 OS 자동 반복 입력은 무시
        self._capture_last_key = keysym
        # 보조키 집합은 우리가 직접 추적한 press/release가 아니라, 이 키
        # 이벤트에 OS가 실어 보낸 그 순간의 실제 상태(event.state)로 판단한다.
        mods = tk_event_modifiers(event)
        self._steps.append((frozenset(mods), keysym))
        self.key_var.set(steps_to_display(self._steps) + " …")

    def _on_capture_keyup(self, event):
        keysym = normalize_keysym(event.keysym)
        if keysym and keysym == self._capture_last_key:
            self._capture_last_key = None

    def _finish_capture(self):
        self._capturing = False
        self.top.unbind("<KeyPress>")
        self.top.unbind("<KeyRelease>")
        self.top.unbind("<FocusOut>")
        self.name_entry.config(state="normal")
        self.cd_entry.config(state="normal")
        self.capture_btn.config(text="키 입력")
        self.key_var.set(steps_to_display(self._steps))

    def _clear_capture(self):
        if self._capturing:
            self._finish_capture()
        self._steps = []
        self.key_var.set("")

    def _stop_capture_on_other_field_focus(self, event):
        # 캡처 중에 "완료"를 안 누르고 이름/쿨타임 입력칸으로 넘어가면, 거기
        # 타이핑하는 키(한글 입력 등 포함)가 전부 스텝으로 잘못 기록돼버린다
        # — 다른 입력칸에 포커스가 가면 캡처를 자동으로 끝낸다.
        if self._capturing:
            self._finish_capture()

    def _cancel(self):
        if self._capturing:
            self._finish_capture()
        self.top.destroy()

    def _ok(self):
        if self._capturing:
            self._finish_capture()

        name = self.name_var.get().strip()
        try:
            cooldown = float(self.cd_var.get())
        except ValueError:
            messagebox.showerror("오류", "쿨타임은 숫자로 입력하세요.")
            return
        if not name or not self._steps or cooldown <= 0:
            messagebox.showerror("오류", "이름, 키, 쿨타임을 모두 입력하세요.")
            return
        self.result = {
            "name": name,
            "key": steps_to_storage(self._steps),
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
        position_near(self.win, app.win, width=440, height=360)

        self.tree = ttk.Treeview(
            self.win, columns=("name", "key", "cooldown", "sound"), show="headings", height=8
        )
        self.tree.heading("name", text="이름")
        self.tree.heading("key", text="키")
        self.tree.heading("cooldown", text="쿨타임(초)")
        self.tree.heading("sound", text="알림음")
        self.tree.column("name", width=100)
        self.tree.column("key", width=130, anchor="center")
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
                values=(skill.name, steps_to_display(skill.steps), skill.cooldown, sound_label),
            )

    def _current_definitions(self):
        return [
            {"name": s.name, "key": steps_to_storage(s.steps), "cooldown": s.cooldown, "sound": s.sound}
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
                "key": steps_to_storage(current.steps),
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
