# PhotoBlog 공통평가 02

YOLOv5가 웹캠에서 새로 검출한 객체의 사진을 Django 서버에 등록하고 Android 앱에서 조회하는 프로젝트입니다.

저장소: https://github.com/sylee21c/PhotoBlogProject02

클라우드: https://blackponge.pythonanywhere.com/

## 구성

| 경로 | 내용 |
|---|---|
| PhotoBlogServer | Django API와 사진 조회 웹 화면 |
| PhotoViewer | Android 동기화와 사진 조회 앱 |
| YOLOv5 | 웹캠 검출과 서버 자동 전송 |
| evidence | 항목별 캡처와 테스트 결과 |
| artifacts | Android APK와 서버 배포 ZIP |

수행 결과 보고서는 루트의 `모바일웹서비스 프로젝트 공통평가 02_수행 결과 보고서.docx`입니다.

## 실행

프로젝트 루트의 PowerShell에서 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-server.ps1
```

웹 주소는 `http://127.0.0.1:8002/`, Android 에뮬레이터의 서버 주소는 `http://10.0.2.2:8002`입니다. 앱은 `artifacts/PhotoViewer-debug.apk`로 설치합니다.

별도 PowerShell에서 Python 3.12 기반 Edge 환경을 준비하고 웹캠 검출기를 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-edge.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-yolo.ps1
```

`start-yolo.ps1 -Baseline`은 원본 detect.py를 실행합니다. 검출 창에서 q를 누르면 종료합니다.

웹캠은 객체 종류의 유무를 비교하고 3프레임 연속 검출로 출현을 판정합니다. 새로 출현하면 검출 상자가 포함된 사진을 서버에 전송합니다.

로컬 인증정보는 `.runtime/demo-credentials.json`에 생성됩니다. 클라우드 연결에는 `PHOTOBLOG_SERVER`와 `PHOTOBLOG_USERNAME`, `PHOTOBLOG_PASSWORD` 또는 `PHOTOBLOG_TOKEN`을 설정합니다. 배포 절차는 [PythonAnywhere 설정](docs/PYTHONANYWHERE.md)에 있습니다.

## 검증 결과

| 항목 | 결과 |
|---|---|
| Django 자동 테스트 | 55개 통과 |
| Edge 자동 테스트 | 10개 통과 |
| Android 단위 테스트 | 9개 통과 |
| 로컬 연동 | 웹캠 사진 자동 등록과 Android 조회 확인 |
| 클라우드 연동 | 검출 이벤트 5건 자동 전송, 대기 0건, 차단 0건 |
| 클라우드 사진 조회 | 게시글 2~6번 API와 사진 모두 HTTP 200 |

추가 기능은 두 가지입니다.

- 전송 대기열과 재시도: 실패한 사진과 이벤트 ID를 SQLite에 보관하고 서버 복구 후 이어서 전송합니다.
- 중복 등록 방지: 같은 이벤트를 재전송하면 기존 게시글을 반환하고, 같은 ID로 내용이 바뀌면 HTTP 409를 반환합니다.

아래 명령으로 연결 실패 후 복구와 중복 등록 방지를 실제 로컬 HTTP 서버에서 검증합니다.

```powershell
.\.venv-edge\Scripts\python.exe .\scripts\verify_delivery.py --summary
```

결과는 `evidence/delivery-integration.json`, 클라우드 전송 기록은 `evidence/cloud-edge-delivery.json`에 있습니다.

YOLOv5 v7.0의 출처와 체크섬은 `YOLOv5/UPSTREAM.json`에 기록했습니다. YOLOv5 소스에는 GPL-3.0 라이선스가 적용됩니다.
