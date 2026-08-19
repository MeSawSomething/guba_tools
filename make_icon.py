"""빌드 전에 실행되는 아이콘 생성 스크립트.

이 폴더에 .png 이미지 파일을 하나 넣어두면, 그 이미지로 아이콘을 만들어
exe(icon.ico)/macOS 앱(icon.icns) 아이콘으로 자동 사용합니다.
PNG 파일이 없으면 아무것도 하지 않고 조용히 넘어갑니다(기존 기본 아이콘 사용).
"""

import glob
import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Pillow가 설치되어 있지 않아 아이콘 생성을 건너뜁니다.")
    sys.exit(0)

HERE = os.path.dirname(os.path.abspath(__file__))
ICO_PATH = os.path.join(HERE, "icon.ico")
ICNS_PATH = os.path.join(HERE, "icon.icns")

ICON_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def find_source_png():
    pngs = sorted(glob.glob(os.path.join(HERE, "*.png")))
    return pngs[0] if pngs else None


def main():
    png_path = find_source_png()
    if not png_path:
        print("PNG 아이콘 파일이 없어 기본 아이콘을 사용합니다.")
        return

    print(f"'{os.path.basename(png_path)}' 파일로 아이콘을 생성합니다...")
    img = Image.open(png_path).convert("RGBA")

    img.save(ICO_PATH, format="ICO", sizes=ICON_SIZES)
    print(f"  -> {os.path.basename(ICO_PATH)} 생성 완료")

    try:
        img.save(ICNS_PATH, format="ICNS")
        print(f"  -> {os.path.basename(ICNS_PATH)} 생성 완료")
    except Exception as ex:
        print(f"  (icns 생성 건너뜀: {ex})")


if __name__ == "__main__":
    main()
