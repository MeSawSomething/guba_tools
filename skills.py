"""스킬(키/쿨타임/알림음) 설정을 config.json 에 저장하고 불러오는 모듈.

중요: config.json은 OS별 "사용자 앱 데이터" 폴더에 저장합니다 (아래
_config_dir() 참고). main.py 옆이 아닌 이유는, PyInstaller로 만든
exe(onefile)/app을 실행하면 프로그램이 매번 임시 폴더에 압축을 풀고 그
안에서 실행되기 때문입니다 — 만약 config.json을 그 임시 폴더 기준으로
저장하면, 컴퓨터를 껐다 켜거나 프로그램을 다시 실행할 때마다 임시 폴더가
새로 생겨서 저장한 내용이 매번 사라집니다. 그래서 실행 위치와 무관하게
항상 같은 자리를 가리키는 사용자 폴더에 저장해야 진짜로 영구 보존됩니다.
"""

import json
import os
import shutil
import sys

APP_DIR_NAME = "CooltimeTracker"
# 예전 이름(CooldownTracker)으로 저장돼 있던 설정을 한 번 옮겨오기 위한 이름.
_LEGACY_APP_DIR_NAMES = ["CooldownTracker"]


def _app_data_dir(app_dir_name):
    """OS별로 표준적인 사용자 설정 저장 위치를 반환한다."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, app_dir_name)
    elif sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/Application Support/{app_dir_name}")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return os.path.join(base, app_dir_name)


def _config_dir():
    return _app_data_dir(APP_DIR_NAME)


def _legacy_config_paths():
    """예전 버전의 config.json 위치들(있으면 새 위치로 한 번만 옮겨서, 업데이트
    후에도 기존에 입력해둔 스킬/창 위치를 잃어버리지 않게 한다).
    1) main.py/exe와 같은 폴더에 저장하던 아주 옛날 방식
    2) 프로그램 이름이 CooldownTracker였을 때의 사용자 앱 데이터 폴더
    """
    paths = []
    try:
        if getattr(sys, "frozen", False):
            base = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        paths.append(os.path.join(base, "config.json"))
    except Exception:
        pass

    for old_name in _LEGACY_APP_DIR_NAMES:
        paths.append(os.path.join(_app_data_dir(old_name), "config.json"))

    return paths


CONFIG_DIR = _config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_SOUND = "beep_default"

# 프로그램을 처음 실행했을 때 보여줄 예시 스킬 (사용자가 설정 창에서 자유롭게 수정 가능)
DEFAULT_SKILLS = [
    {"name": "스킬1", "key": "3", "cooldown": 60, "sound": DEFAULT_SOUND},
]


def _migrate_legacy_config_if_needed():
    if os.path.exists(CONFIG_PATH):
        return
    for legacy_path in _legacy_config_paths():
        if not legacy_path or legacy_path == CONFIG_PATH:
            continue
        if os.path.exists(legacy_path):
            try:
                os.makedirs(CONFIG_DIR, exist_ok=True)
                shutil.copyfile(legacy_path, CONFIG_PATH)
            except Exception:
                pass
            return


def _read_config_file():
    """config.json 을 dict 형태로 읽어온다. 예전 버전(배열만 저장)과도 호환."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if isinstance(data, list):
        return {"skills": data}
    if isinstance(data, dict):
        return data
    return {}


def _write_config_file(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_key_field(raw_key):
    """"key" 필드를 스텝 리스트(각 스텝 = {"mods": [...], "key": "..."})로 정규화한다.

    하위호환: 예전 버전은 "key"에 문자열 하나(예: "3")만 저장했다. 이 경우
    "보조키 없는 스텝 1개"로 취급한다. 새 버전은 조합/순서 입력(예:
    shift+z 다음 shift+i)을 표현하기 위해 리스트를 저장한다.
    """
    if isinstance(raw_key, str):
        key = raw_key.strip()
        return [{"mods": [], "key": key}] if key else []

    if isinstance(raw_key, list):
        steps = []
        for item in raw_key:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            if not key:
                continue
            mods = item.get("mods", [])
            if not isinstance(mods, list):
                mods = []
            mods = sorted({str(m).strip() for m in mods if str(m).strip()})
            steps.append({"mods": mods, "key": key})
        return steps

    return []


def load_skills():
    """config.json 에서 스킬 목록을 불러온다. 파일이 없으면 기본값으로 새로 만든다."""
    _migrate_legacy_config_if_needed()

    if not os.path.exists(CONFIG_PATH):
        save_skills(DEFAULT_SKILLS)
        return [dict(s) for s in DEFAULT_SKILLS]

    try:
        raw_skills = _read_config_file().get("skills", [])
        cleaned = []
        for item in raw_skills:
            name = str(item.get("name", "")).strip() or "이름없음"
            steps = normalize_key_field(item.get("key"))
            cooldown = float(item.get("cooldown", 0))
            sound = str(item.get("sound", "")).strip() or DEFAULT_SOUND
            if steps and cooldown > 0:
                cleaned.append({"name": name, "key": steps, "cooldown": cooldown, "sound": sound})
        return cleaned
    except Exception:
        # 파일이 손상된 경우 기본값으로 복구
        return [dict(s) for s in DEFAULT_SKILLS]


def save_skills(skills):
    """스킬 목록을 config.json 에 저장한다. (프로그램을 껐다 켜도, 컴퓨터를
    재부팅해도 유지됨 — 사용자 앱 데이터 폴더에 저장하기 때문)"""
    data = _read_config_file()
    data["skills"] = skills
    _write_config_file(data)


def load_window_position():
    """마지막으로 저장된 오버레이 창 위치 (x, y) 를 반환한다. 없으면 None."""
    pos = _read_config_file().get("window_position")
    if not isinstance(pos, dict):
        return None
    try:
        return int(pos["x"]), int(pos["y"])
    except (KeyError, TypeError, ValueError):
        return None


def save_window_position(x, y):
    """오버레이 창 위치를 config.json 에 저장한다."""
    data = _read_config_file()
    data["window_position"] = {"x": int(x), "y": int(y)}
    _write_config_file(data)


DEFAULT_UI_SCALE = 1.0


def load_ui_scale():
    """마지막으로 저장된 오버레이 UI 크기 배율을 반환한다. 없거나 잘못됐으면 기본값(1.0)."""
    try:
        scale = float(_read_config_file().get("ui_scale", DEFAULT_UI_SCALE))
        if scale > 0:
            return scale
    except (TypeError, ValueError):
        pass
    return DEFAULT_UI_SCALE


def save_ui_scale(scale):
    """오버레이 UI 크기 배율을 config.json 에 저장한다."""
    data = _read_config_file()
    data["ui_scale"] = float(scale)
    _write_config_file(data)


def load_overlay_width():
    """마지막으로 저장된 오버레이 창 너비(px)를 반환한다. 없으면 None(자동 너비)."""
    try:
        width = _read_config_file().get("overlay_width")
        if width is None:
            return None
        width = int(width)
        return width if width > 0 else None
    except (TypeError, ValueError):
        return None


def save_overlay_width(width):
    """오버레이 창 너비(px)를 config.json 에 저장한다."""
    data = _read_config_file()
    data["overlay_width"] = int(width)
    _write_config_file(data)
