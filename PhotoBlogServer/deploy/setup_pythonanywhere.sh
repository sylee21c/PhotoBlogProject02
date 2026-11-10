#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,10), "Choose Python 3.10 or newer, matching the Web tab"'
if [[ ! -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$PROJECT_ROOT/.venv"
fi
"$PROJECT_ROOT/.venv/bin/python" -m pip install -r "$PROJECT_ROOT/PhotoBlogServer/requirements-lock.txt"
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/PhotoBlogServer/manage.py" migrate --noinput
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/PhotoBlogServer/manage.py" collectstatic --noinput
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/PhotoBlogServer/manage.py" check
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/PhotoBlogServer/deploy/configure_pythonanywhere.py" "$@"
printf '\nNext: configure Web > WSGI, virtualenv, static/media mappings and Reload.\n'
printf 'Create your own cloud account with: %s/.venv/bin/python %s/PhotoBlogServer/manage.py createsuperuser\n' "$PROJECT_ROOT" "$PROJECT_ROOT"
