"""Package deployable server sources without DB, media or local credentials."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent.parent
target=ROOT/'artifacts/photoblog02-server.zip'
target.parent.mkdir(exist_ok=True)
excluded={'__pycache__','media','staticfiles','.runtime','.venv','.git'}
files=[p for p in (ROOT/'PhotoBlogServer').rglob('*') if p.is_file()
       and not excluded.intersection(p.relative_to(ROOT).parts)
       and p.suffix not in {'.pyc','.sqlite3','.log'} and p.name not in {'.env','.coverage'}]
files += [ROOT/'docs/PYTHONANYWHERE.md', ROOT/'docs/PHOTO_CREDITS.md']
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(files):archive.write(p,p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert 'PhotoBlogServer/blog/migrations/0002_edgeuploadreceipt.py' in archive.namelist()
    assert not any('/media/' in p or p.endswith('.sqlite3') or 'credentials' in p for p in archive.namelist())
manifest={'file':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
          'files':len(files),'excludes':['database','uploaded media','local credentials','YOLO weights']}
(ROOT/'artifacts/server-package.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
