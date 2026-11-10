"""Generate private, account-specific WSGI configuration on PythonAnywhere.

No passwords are generated or stored here. The Django secret is generated once
inside ignored .runtime, and a private WSGI file reads it at application startup.
"""
import argparse
import getpass
import json
import os
import re
import secrets
from pathlib import Path


def configure(project_root,domain):
    root=Path(project_root).resolve()
    if not (root/'PhotoBlogServer/manage.py').is_file():raise ValueError('Project root must contain PhotoBlogServer/manage.py')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.(?:eu\.)?pythonanywhere\.com',domain):
        raise ValueError('Use your PythonAnywhere hostname only, without https:// or a path.')
    private=root/'.runtime';private.mkdir(exist_ok=True)
    if os.name!='nt':private.chmod(0o700)
    secret_file=private/'cloud-secrets.json'
    if not secret_file.exists():
        # Exclusive creation avoids silently rotating the secret on reruns.
        with secret_file.open('x',encoding='utf-8') as stream:
            json.dump({'DJANGO_SECRET_KEY':secrets.token_urlsafe(48)},stream)
    if os.name!='nt':secret_file.chmod(0o600)
    values=json.loads(secret_file.read_text(encoding='utf-8'))
    if len(values.get('DJANGO_SECRET_KEY',''))<50:raise ValueError('Existing private secret is invalid; inspect it locally without publishing it.')
    server=root/'PhotoBlogServer'
    source=f'''# Generated private configuration. Copy this into PythonAnywhere Web > WSGI.
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, {str(server)!r})
private = json.loads(Path({str(secret_file)!r}).read_text(encoding="utf-8"))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DEBUG"] = "0"
os.environ["DJANGO_SECRET_KEY"] = private["DJANGO_SECRET_KEY"]
os.environ["DJANGO_ALLOWED_HOSTS"] = {domain!r}
os.environ["DJANGO_CSRF_TRUSTED_ORIGINS"] = {('https://'+domain)!r}
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
'''
    target=private/'pythonanywhere_wsgi.py';target.write_text(source,encoding='utf-8')
    if os.name!='nt':target.chmod(0o600)
    return {'domain':'https://'+domain,'source_code':str(server),'virtualenv':str(root/'.venv'),
            'wsgi_source':str(target),'static_url':'/static/','static_directory':str(server/'staticfiles'),
            'media_url':'/media/','media_directory':str(server/'media')}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--domain',default=getpass.getuser()+'.pythonanywhere.com')
    parser.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[2])
    args=parser.parse_args()
    print(json.dumps(configure(args.project_root,args.domain),ensure_ascii=False,indent=2))
