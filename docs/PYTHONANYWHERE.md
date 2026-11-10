# PythonAnywhere 배포

공통평가 01과 다른 GitHub 저장소를 만든 후 아래 절차를 실행합니다. 이미 운영 중인 01 서버를 바꿀 때는 기존 소스와 DB를 먼저 보관합니다. 이 문서는 배포 절차이며 실제 클라우드 동작 증빙을 대신하지 않습니다.

## 소스와 환경

PythonAnywhere Bash 콘솔에서 새 저장소를 clone하거나 `artifacts/photoblog02-server.zip`을 업로드해 압축을 풉니다. ZIP에는 DB, 인증정보, 웹캠 사진, YOLO 모델이 포함되지 않습니다.

```bash
cd ~/PhotoBlogProject02
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r PhotoBlogServer/requirements-lock.txt
python PhotoBlogServer/manage.py migrate
python PhotoBlogServer/manage.py collectstatic --noinput
python PhotoBlogServer/manage.py createsuperuser
```

Python 3.13을 사용할 수 없다면 PythonAnywhere에서 제공하는 Python 3.12로 가상환경과 Web 앱의 Python 버전을 일치시킵니다. `createsuperuser`의 사용자 이름과 비밀번호는 직접 정합니다. 로컬 계정과 토큰은 복사하지 않습니다.

## Web 앱 설정

Manual configuration으로 Django 앱을 설정합니다. 가상환경 경로는 `/home/계정/PhotoBlogProject02/.venv`입니다. WSGI 파일에는 아래 내용을 넣고 계정 및 비밀키를 본인의 값으로 바꿉니다.

```python
import os
import sys
sys.path.insert(0, '/home/계정/PhotoBlogProject02/PhotoBlogServer')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DJANGO_DEBUG'] = '0'
os.environ['DJANGO_SECRET_KEY'] = '직접 생성한 충분히 긴 비밀키'
os.environ['DJANGO_ALLOWED_HOSTS'] = '계정.pythonanywhere.com'
os.environ['DJANGO_CSRF_TRUSTED_ORIGINS'] = 'https://계정.pythonanywhere.com'
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Static files에서 `/static/`을 서버의 `staticfiles/`에, `/media/`를 서버의 `media/`에 연결합니다. 위 예시라면 실제 디렉터리는 각각 `/home/계정/PhotoBlogProject02/PhotoBlogServer/staticfiles`와 `/home/계정/PhotoBlogProject02/PhotoBlogServer/media`입니다. Web 앱을 Reload합니다. 비밀키나 WSGI 인증정보 화면을 캡처하거나 GitHub에 올리지 않습니다.

## Edge 연결과 최종 확인

PC PowerShell에서 `PHOTOBLOG_SERVER`를 본인의 HTTPS 원점 주소로 지정하고 `PHOTOBLOG_USERNAME`, `PHOTOBLOG_PASSWORD` 또는 `PHOTOBLOG_TOKEN`을 별도로 설정합니다. 현재 구현의 로그인 엔드포인트는 `/api/token/`, 인증 헤더는 `Authorization: Token ...`입니다. 강의 예제의 JWT 경로를 그대로 쓰지 않습니다.

`scripts/start-yolo.ps1 -MaxFrames 120`으로 검출 사진을 보낸 후 아래를 직접 확인합니다.

- `/api/health/`가 정상 응답합니다.
- `/api_root/`와 `/api_root/Post/`에서 새 게시글이 조회됩니다.
- `/`의 목록과 게시글 상세에서 검출 사진이 표시됩니다.
- Android 설정을 같은 HTTPS 주소로 바꾸고 동기화하면 같은 사진이 표시됩니다.

보고서 ID 8에는 주소창이 보이는 클라우드 API 화면을, ID 9에는 목록과 검출 사진 화면을 넣습니다. 기존 01 서버가 열린다는 사실만으로 02 배포 완료로 판단하지 않습니다.
