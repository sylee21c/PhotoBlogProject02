# 공통평가 02 변경 지점

공식 YOLOv5 v7.0 소스에 아래 부분을 추가했습니다. 공식 원본 detect.py는 `baseline/detect.py`에 보관했고, 원본 해시와 커밋은 `UPSTREAM.json`에 있습니다.

| 파일 | 역할 |
|---|---|
| detect.py | 클래스 벡터 구성, 검출 표시가 있는 프레임을 ChangeDetection에 전달 |
| changedetection.py | 3프레임 확인과 클래스의 0에서 1로 전이 판단, JPEG 생성 |
| edge_upload.py | 로그인과 multipart POST, 계정 및 서버별 SQLite 전송 대기열 |
| assessment_tests/test_delivery.py | 상태 전이, 순간적인 누락, 대기열 보존, 실패와 재전송 검증 |

서버 API는 `/api/token/`에서 토큰을 발급하고 `/api_root/Post/`로 사진을 받습니다. 이 프로젝트는 DRF TokenAuthentication을 쓰므로 강의 JWT 예제의 인증 헤더를 그대로 사용하지 않습니다. JPEG와 이벤트 ID는 로컬에 저장하고, 인증정보는 대기열에 저장하지 않습니다.

원본 실행은 프로젝트 루트에서 `scripts/start-yolo.ps1 -Baseline`로 합니다. 수정본은 `scripts/start-yolo.ps1`로 실행하며, `-MaxFrames 120`을 추가하면 일정 프레임만 확인하고 종료합니다. 이미지 파일은 `-Source YOLOv5/data/images/bus.jpg`로 지정할 수 있습니다. 모델 파일은 Git에 포함하지 않고 `scripts/setup-edge.ps1`이 공식 URL에서 내려받아 SHA256을 확인합니다.

`edge_upload.py`의 상태 조회 CLI는 `--state-dir .runtime/edge --server http://127.0.0.1:8002 --username student`로 사용할 수 있습니다. 출력은 pending, sent, blocked 상태와 이벤트 ID이며 비밀번호나 토큰은 출력하지 않습니다. 인증 실패나 잘못된 요청은 blocked로 보존하므로 해당 원인을 수정해야 합니다. 기존 blocked 이벤트를 자동으로 다시 전송하지 않습니다.
