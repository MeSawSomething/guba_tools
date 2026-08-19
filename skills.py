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

APP_DIR_NAME = "CooldownTracker"


def _config_dir():
    """OS별로 표준적인 사용자 설정 저장 위치를 반환한다."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_DIR_NAME)
    elif sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP_DIR_NAME}")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return os.path.join(base, APP_DIR_NAME)


def _legacy_config_path():
    """예전 버전(main.py/exe와 같은 폴더에 저장하던 방식)의 config.json 위치.
    있으면 새 위치로 한 번만 옮겨서, 업데이트 후에도 기존에 입력해둔 스킬을
    잃어버리지 않게 한다."""
    try:
        if getattr(sys, "frozen", False):
            base = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "config.json")
    except Exception:
        return None


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
    legacy_path = _legacy_config_path()
    if not legacy_path or legacy_path == CONFIG_PATH:
        return
    if os.path.exists(legacy_path):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            shutil.copyfile(legacy_path, CONFIG_PATH)
        except Exception:
            pass


def load_skills():
    """config.json 에서 스킬 목록을 불러온다. 파일이 없으면 기본값으로 새로 만든다."""
    _migrate_legacy_config_if_needed()

    if not os.path.exists(CONFIG_PATH):
        save_skills(DEFAULT_SKILLS)
        return [dict(s) for s in DEFAULT_SKILLS]

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("config.json 형식이 올바르지 않습니다.")

        cleaned = []
        for item in data:
            name = str(item.get("name", "")).strip() or "이름없음"
            key = str(item.get("key", "")).strip()
            cooldown = float(item.get("cooldown", 0))
            sound = str(item.get("sound", "")).strip() or DEFAULT_SOUND
            if key and cooldown > 0:
                cleaned.append({"name": name, "key": key, "cooldown": cooldown, "sound": sound})
        return cleaned
    except Exception:
        # 파일이 손상된 경우 기본값으로 복구
        return [dict(s) for s in DEFAULT_SKILLS]


def save_skills(skills):
    """스킬 목록을 config.json 에 저장한다. (프로그램을 껐다 켜도, 컴퓨터를
    재부팅해도 유지됨 — 사용자 앱 데이터 폴더에 저장하기 때문)"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(skills, f, ensure_ascii=False, indent=2)
