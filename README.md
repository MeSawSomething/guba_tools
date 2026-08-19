# 쿨타임 트래커 (Cooldown Tracker)

키보드로 스킬을 쓰는 게임을 할 때, 지정한 키를 누르면 그 스킬의 쿨타임을
세어주는 작은 오버레이 창이 화면 위에 항상 떠 있는 프로그램입니다.
**Windows와 macOS 둘 다 지원**합니다.

- 여러 스킬(키)의 쿨타임을 한 창에서 막대 그래프 + 초 단위 숫자로 표시
- 쿨타임이 끝나면 **소리 + 화면 깜빡임**으로 알림
- **알림음은 스킬마다 다르게 선택** 가능 (기본 삐 / 높은 두번 삐삐 / 낮은 둥 /
  경고음 삐삐삐 / 시스템 알림음 3종 / 무음 중 선택, 설정 창에서 미리듣기 가능)
- 스킬 이름/키/쿨타임/알림음은 설정 창에서 자유롭게 추가·수정·삭제 가능
- 설정한 내용은 컴퓨터의 사용자 앱 데이터 폴더에 저장되어, **프로그램을 껐다
  켜는 것은 물론 컴퓨터를 완전히 재부팅해도 그대로 유지**됩니다 (자세한 저장
  위치는 아래 "5. 참고 / 주의사항" 참고).

## 1. 준비

### Windows

1. [python.org](https://www.python.org/downloads/) 에서 Python 3.9 이상 설치
   (설치 시 "Add python.exe to PATH" 체크)
2. 이 폴더(`cooldown_tracker`)를 원하는 위치에 저장
3. 폴더에서 명령 프롬프트(또는 PowerShell)를 열고 아래 명령 실행:

   ```
   pip install -r requirements.txt
   ```

### macOS

1. Python 3가 없다면 [python.org](https://www.python.org/downloads/) 에서 설치하거나,
   Homebrew가 있다면 `brew install python` 실행 (macOS엔 python3가 기본 내장된
   경우도 있지만 버전이 오래됐을 수 있어 새로 설치하는 걸 권장합니다)
2. 이 폴더(`cooldown_tracker`)를 원하는 위치에 저장
3. 터미널(Terminal)을 열고 이 폴더로 이동한 뒤 아래 명령 실행:

   ```
   python3 -m pip install -r requirements.txt
   ```

4. **중요 — 권한 허용**: 전역 키 입력을 감지하려면 macOS가 이 프로그램(정확히는
   터미널 또는 Python)에 권한을 줘야 합니다. 처음 실행하면 자동으로 권한 요청
   팝업이 뜨거나, 안 뜨면 직접 아래 경로에서 켜주세요.

   `시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용(Accessibility)` 와
   `입력 모니터링(Input Monitoring)` 두 곳 모두에서 **터미널**(또는 나중에
   만든 `CooldownTracker.app`)을 체크/허용해야 합니다.

## 2. 실행

Windows:

```
python main.py
```

macOS:

```
python3 main.py
```

화면 좌측 상단에 반투명한 작은 창이 뜹니다. 이 창을 게임 화면 위로
드래그해서(위쪽 "⋮⋮ 쿨타임 트래커" 부분을 잡고 이동) 원하는 위치에 두세요.

## 3. 스킬 설정하기

1. 오버레이 창 우측 상단의 **⚙(톱니바퀴)** 클릭 → 설정 창이 열립니다.
2. **추가** 버튼 → 이름 입력 → **키 입력** 버튼을 누른 뒤 원하는 키(예: `3`, `q`, `f1` 등)를
   실제로 눌러 등록 → 쿨타임(초) 입력 → **알림음** 드롭다운에서 원하는 소리 선택
   (**▶ 미리듣기**로 미리 들어볼 수 있음) → 확인.
3. 목록에서 스킬을 선택한 뒤 **수정** / **삭제**로 편집할 수 있습니다.
   (목록의 스킬을 더블클릭해도 바로 수정 창이 열립니다.)
4. 저장은 자동으로 이루어지며, 프로그램을 다시 켜도 등록한 스킬(알림음 포함)이 그대로 남아 있습니다.

기본으로 예시 스킬 하나(`스킬1`, 키 `3`, 쿨타임 60초)가 들어있으니, 필요 없으면
삭제하고 원하는 스킬로 바꿔서 쓰시면 됩니다.

## 4. 사용 방법

게임 안에서 스킬 키(예: `3`)를 누르면, 오버레이 창의 해당 스킬 막대가
파란색으로 차오르며 남은 초를 보여줍니다. 쿨타임이 끝나면 막대가 하얗게
깜빡이면서 그 스킬에 설정된 알림음이 울립니다. (스킬마다 다른 소리를
쓰고 있으면, 어떤 스킬이 끝났는지 소리만 듣고도 구분할 수 있습니다.)

- 이미 쿨타임 중인 키를 다시 눌러도 무시됩니다 (게임에서도 쿨타임 중엔
  다시 쓸 수 없으니까요).
- 창을 닫으려면 우측 상단의 **✕** 를 클릭하세요.

## 5. 참고 / 주의사항

- 전역(다른 창에서도) 키 입력을 감지하기 위해 `pynput` 라이브러리를 사용합니다.
  - **Windows**: 게임을 관리자 권한으로 실행 중이라면 이 프로그램도 관리자
    권한으로 실행해야 키 입력이 정상적으로 감지됩니다.
  - **macOS**: 위 "1. 준비"에서 설명한 손쉬운 사용 / 입력 모니터링 권한을
    허용해야 키 입력이 감지됩니다. 권한을 껐다 켜면 앱을 재시작해야 반영됩니다.
- 일부 게임(특히 안티치트가 적용된 온라인 게임)은 전역 키 후킹 프로그램의
  실행을 감지하거나 차단할 수 있습니다. 해당 게임의 이용약관을 확인한 뒤
  자기 책임 하에 사용하세요. 걱정되면 싱글플레이/연습 게임에서만 사용하는
  것을 권장합니다.
- 알림음은 Windows와 macOS 모두에서 실제 소리로 재생됩니다(Windows는
  `winsound`, macOS는 내장된 시스템 사운드 파일을 재생). 다만 두 OS의 사운드
  라이브러리가 달라서 같은 스킬이라도 Windows와 macOS에서 소리 느낌이 조금
  다를 수 있습니다. macOS/Windows가 아닌 환경(Linux 등)에서는 시스템
  벨(터미널 비프음)로 대체됩니다.
- **스킬 설정 저장 위치**: `config.json`은 exe/app이 어디 있든 상관없이 항상
  아래의 고정된 사용자 폴더에 저장됩니다.
  - Windows: `%APPDATA%\CooldownTracker\config.json`
  - macOS: `~/Library/Application Support/CooldownTracker/config.json`
  - Linux: `~/.config/CooldownTracker/config.json`

  exe나 app을 다른 폴더로 옮기거나, 컴퓨터를 재부팅해도 이 폴더는 그대로라서
  설정이 사라지지 않습니다. (이전 버전에서 main.py/exe와 같은 폴더에
  `config.json`을 만들어 쓰고 계셨다면, 처음 실행할 때 그 내용을 자동으로 이
  새 위치로 한 번 옮겨줍니다.)

## 6. 실행 파일(Windows exe / macOS dmg)로 만들기

> 참고: exe(Windows)와 dmg(macOS)는 각각 해당 OS 위에서만 빌드할 수 있습니다.
> dmg를 만드는 `hdiutil`은 Apple이 macOS에만 넣어둔 도구라 Linux/Windows에는
> 아예 존재하지 않습니다. 그래서 지금 이 대화를 처리하는 클라우드 환경(Linux)
> 에서는 여기서 직접 만들어 드릴 수 없고, 아래 방법 중 하나로 만들어 쓰시면
> 됩니다. 필요한 파일은 이미 이 폴더 안에 준비해 두었습니다.

### 방법 A. 내 PC에서 바로 빌드 (Python이 설치되어 있다면, 가장 빠름)

- **Windows**: `build_exe.bat` 더블클릭 → `dist\CooldownTracker.exe` 생성
- **macOS**: `build_mac.command` 더블클릭 →
  `dist/CooldownTracker.app`을 만든 뒤, 그걸 `hdiutil`로 감싸서
  `dist/CooldownTracker.dmg`까지 자동으로 만들어줍니다.
  (처음 더블클릭 시 "확인되지 않은 개발자" 경고가 뜨면 파인더에서 파일을
  마우스 우클릭(또는 Control-클릭) → **열기** → **열기**를 선택하세요)

수동으로 하고 싶다면 (패키지 이름은 `pyinstaller`이지만 실제 모듈 이름은
`PyInstaller`이며 대소문자를 구분하므로 아래와 같이 정확히 입력):

```
# Windows
pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --noconsole --name CooldownTracker main.py

# macOS
python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --onefile --windowed --name CooldownTracker main.py
mkdir dist/dmg_staging
cp -R dist/CooldownTracker.app dist/dmg_staging/
ln -s /Applications dist/dmg_staging/Applications
hdiutil create -volname "CooldownTracker" -srcfolder dist/dmg_staging -ov -format UDZO dist/CooldownTracker.dmg
```

`dist` 폴더에 생성된 `CooldownTracker.exe`(Windows) 또는
`CooldownTracker.dmg`(macOS)를 실행하면 됩니다. dmg는 더블클릭하면 창이 열리고,
그 안의 앱 아이콘을 같이 보이는 Applications 바로가기로 드래그하면 설치됩니다.
스킬 설정은 exe/app 위치와 무관하게 사용자 앱 데이터 폴더에 저장되므로,
앱을 옮기거나 재설치해도 계속 유지됩니다 (정확한 위치는 위 "5. 참고 /
주의사항" 참고).

### 방법 B. GitHub Actions로 자동 빌드 (내 PC에 Python/Mac이 없어도 됨)

이 폴더를 GitHub 저장소에 올리면(`.github/workflows/build.yml` 포함) GitHub가
제공하는 실제 Windows 서버와 macOS 서버에서 **exe와 dmg를 동시에** 자동으로
빌드해 줍니다. macOS 쪽은 GitHub의 진짜 macOS 서버에서 `hdiutil`로 dmg까지
만들어주기 때문에, 본인이 Mac을 갖고 있지 않아도 정식 dmg 파일을 받을 수
있습니다.

1. GitHub에 새 저장소를 만들고 이 폴더 전체를 push 합니다.
2. 저장소의 **Actions** 탭 → "Build Windows EXE and macOS DMG" 워크플로우가
   자동 실행됩니다 (또는 "Run workflow"로 수동 실행).
3. 완료되면 해당 실행 결과 페이지 하단의 **Artifacts** 에서
   `CooldownTracker-windows-exe`와 `CooldownTracker-macos-dmg`를 각각
   내려받으면 됩니다.

### 참고

- Windows: PyInstaller로 빌드한 exe는 Windows Defender/백신에서 "알 수 없는
  게시자" 경고나 드물게 오탐(false positive)이 뜰 수 있습니다. 직접 만든
  소스코드이므로 안심하고 "추가 정보 → 실행"을 선택하시면 됩니다.
- macOS: dmg 안의 앱은 서명(코드사이닝)되지 않은 상태라 Gatekeeper가 처음
  실행을 막습니다. 위에서 설명한 대로 우클릭 → 열기로 한 번 허용하면 이후엔
  정상적으로 실행됩니다. (Apple Developer 유료 계정으로 서명·공증하면 이
  경고 자체를 없앨 수 있지만, 개인용으로 쓰기엔 필수는 아닙니다.)
