# PhotoBlog 공통평가 02

공통평가 01과 분리한 작업 폴더입니다. Django 서버와 Android 앱의 검증된 소스를 기반으로 시작합니다.

Ch08 YOLO 강의자료와 공통평가 02 Word 양식을 기준으로 구현했습니다. 기본 YOLO 웹캠 검출, 검출 사진의 로컬 서버 전송, Android에서 같은 사진 표시는 실제로 확인했습니다. 클라우드 배포, 일부 화면 캡처와 제출 URL은 아직 남아 있습니다. 전체 항목 완료 상태는 아닙니다.

제출 저장소도 공통평가 01과 별도로 생성합니다. 관련증빙 칸에 캡처를 직접 삽입하고, 주소창과 동작 완료 결과를 포함합니다. 추가 기능은 Edge 전송 대기열과 재시도, 서버의 이벤트 중복 등록 방지 두 개입니다.

## 로컬 실행

PowerShell에서 프로젝트 루트를 열고 `scripts/setup.ps1`로 서버를 준비한 뒤 `scripts/start-server.ps1`로 실행합니다. 웹 주소는 `http://127.0.0.1:8002/`, Android 에뮬레이터 주소는 `http://10.0.2.2:8002`입니다.

Python 3.12 환경에서 `scripts/setup-edge.ps1`을 실행하면 CPU용 PyTorch와 YOLO 의존성 및 공식 모델을 준비합니다. `scripts/start-yolo.ps1 -Baseline`은 원본 detect.py를 별도 디렉터리에 복원해 실행합니다. `scripts/start-yolo.ps1`은 수정한 검출기를 실행하고 새 객체 종류가 나타날 때 검출 사진을 서버에 보냅니다. 검출 창에서 q를 누르면 종료합니다.

로컬 계정은 서버 초기화가 생성하며 인증정보는 Git에서 제외한 `.runtime/demo-credentials.json`에 저장합니다. 클라우드에 연결할 때는 `PHOTOBLOG_SERVER`, `PHOTOBLOG_USERNAME`, `PHOTOBLOG_PASSWORD` 또는 `PHOTOBLOG_TOKEN`을 별도로 설정합니다. 비밀번호와 토큰을 소스나 캡처에 넣지 않습니다.

기본 모델은 YOLOv5 v7.0이며 원본 출처와 체크섬은 `YOLOv5/UPSTREAM.json`에 기록했습니다. YOLOv5 소스에는 GPL-3.0 라이선스가 적용됩니다.

웹캠에서는 클래스의 출현과 사라짐이 3프레임 연속 확인된 뒤 상태를 바꿉니다. `--stability-frames 1`을 직접 detect.py에 전달하면 강의의 프레임 단위 전이와 동일하게 동작합니다. 같은 물체를 개체별로 추적하는 기능은 아니며 클래스의 유무를 비교합니다. 모델의 분류 오류까지 제거하는 기능은 아닙니다.

## 검증과 제출 준비

서버 자동 테스트 55개, Edge 자동 테스트 10개, Android 단위 테스트 9개가 통과했습니다. `scripts/verify_delivery.py`는 별도의 임시 DB와 실제 로컬 HTTP 서버로 연결 실패 후 복구, 대기열 재개, 이벤트 재전송의 중복 방지를 확인합니다. 실행은 `.venv-edge/Scripts/python.exe scripts/verify_delivery.py`이며 기존 로컬 게시글은 변경하지 않습니다. 결과는 `evidence/`에 있습니다.

Android APK는 `artifacts/PhotoViewer-debug.apk`, 클라우드 배포 소스 ZIP은 `artifacts/photoblog02-server.zip`입니다. 폴더 구조, 경로와 줄 번호를 포함한 코드, 기본 YOLO 검출, 로컬 API와 사진 조회, Android 동기화, 두 편의 기능의 검증 화면을 보고서에 넣었습니다. 클라우드 API 루트와 사진 목록 및 상세 화면은 주소창을 포함합니다. Edge에서 클라우드로 검출 이벤트 5건을 자동 전송했고 대기와 차단은 0건이었습니다. 게시글 2~6번과 사진 URL은 모두 HTTP 200으로 확인했습니다. 결과는 `evidence/cloud-edge-delivery.json`에 있습니다.

제출 저장소: https://github.com/sylee21c/PhotoBlogProject02

클라우드 서비스: https://blackponge.pythonanywhere.com/

학번과 이름은 요청에 따라 비워 두었으며 평가자 판정도 비워 두었습니다.
