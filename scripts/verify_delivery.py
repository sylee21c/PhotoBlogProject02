"""Real HTTP recovery/replay test using a temporary DB and a private local port.

Run with .venv-edge/Scripts/python.exe. No webcam or production data is used.
"""
import hashlib
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'YOLOv5'))
from edge_upload import ApiUploader, EventQueue, QueueWorker, UploadConfig


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary',action='store_true',help='print a compact screen-capture summary')
    args=parser.parse_args()
    server_python = ROOT/'.venv/Scripts/python.exe'
    manage = ROOT/'PhotoBlogServer/manage.py'
    receipt = {'scenario': 'isolated real HTTP recovery and event replay', 'steps': []}
    with tempfile.TemporaryDirectory(prefix='photoblog02-delivery-') as directory:
        work = Path(directory)
        env = dict(os.environ, PYTHONUTF8='1', DJANGO_DB_PATH=str(work/'db.sqlite3'),
                   DJANGO_MEDIA_ROOT=str(work/'media'))
        def django(*args):
            return subprocess.run([str(server_python), str(manage), *args], env=env,
                cwd=ROOT, check=True, capture_output=True, text=True, encoding='utf-8').stdout
        django('migrate', '--noinput')
        account = django('shell', '--no-imports', '-c',
            "import json; from django.contrib.auth import get_user_model; "
            "from rest_framework.authtoken.models import Token; "
            "u=get_user_model().objects.create_user(username='edge_validation'); "
            "print(json.dumps({'token':Token.objects.create(user=u).key}))")
        token = json.loads(account.strip().splitlines()[-1])['token']
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        config = UploadConfig(origin, 'edge_validation', token=token, timeout=(1,3))
        queue = EventQueue(work/'queue', origin, config.username)
        image = (ROOT/'YOLOv5/data/images/bus.jpg').read_bytes()
        event_id = queue.enqueue('전송 복구 검증', '실제 연결 실패 후 저장된 이벤트 재전송', image)
        worker = QueueWorker(queue, ApiUploader(config), background=False)
        worker.process_one()
        state = queue.status()
        assert state['counts']['pending'] == 1 and state['events'][0]['attempts'] == 1, state
        receipt['steps'].append({'step':'server offline', 'pending':1, 'attempts':1,
                                 'event_id':event_id, 'error':state['events'][0]['last_error']})
        worker.close(0)
        del worker, queue
        queue = EventQueue(work/'queue', origin, config.username)
        assert queue.due(float('inf'))['event_id'] == event_id
        receipt['steps'].append({'step':'reopened persistent queue', 'same_event_id':True})
        with (work/'server.log').open('w', encoding='utf-8') as log:
            server = subprocess.Popen([str(server_python),str(manage),'runserver',
                f'127.0.0.1:{port}','--noreload'], cwd=ROOT, env=env, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError('Isolated server exited before startup.')
                    try:
                        if requests.get(origin+'/api/health/', timeout=1).status_code == 200:
                            break
                    except requests.RequestException:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError('Isolated server did not become ready.')
                event = queue.due(float('inf'))
                worker = QueueWorker(queue, ApiUploader(config), background=False)
                worker.process_one(float('inf'))
                state = queue.status()
                assert state['counts']['sent'] == 1 and state['counts']['pending'] == 0, state
                post_id = state['events'][0]['post_id']
                receipt['steps'].append({'step':'server recovered', 'sent':1, 'pending':0,
                                         'post_id':post_id, 'same_event_id':True})
                def post(title):
                    return requests.post(origin+'/api_root/Post/',
                        headers={'Authorization':'Token '+token,'X-Event-ID':event_id},
                        data={'title':title,'text':event['text']},
                        files={'image':('bus.jpg',image,'image/jpeg')}, timeout=4)
                replay = post(event['title'])
                assert replay.status_code == 200 and replay.json()['id'] == post_id
                assert replay.headers['X-Event-Replayed'] == 'true'
                conflict = post('변경된 내용')
                assert conflict.status_code == 409
                posts = requests.get(origin+'/api_root/Post/',timeout=4).json()
                assert len(posts) == 1
                stored = requests.get(posts[0]['image'], timeout=4)
                assert stored.status_code == 200 and stored.content == image
                receipt['steps'].append({'step':'same event replay', 'http_status':200,
                    'replayed':True,'same_post_id':True,'post_count':1})
                receipt['steps'].append({'step':'event ID reused for changed payload', 'http_status':409})
                receipt['image_sha256'] = hashlib.sha256(image).hexdigest()
                worker.close(0)
            finally:
                server.terminate()
                server.wait(timeout=10)
    receipt['passed'] = True
    receipt['verified_at'] = datetime.now(timezone.utc).isoformat()
    output = ROOT/'evidence/delivery-integration.json'
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT/'evidence/delivery-integration.txt').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    if args.summary:
        print('\nASSESSMENT 02 - REAL HTTP DELIVERY CHECK')
        print('Verified at: '+receipt['verified_at'])
        print('Event ID: '+event_id)
        print('10-1 Offline: pending=1, attempts=1')
        print('10-1 Reopened queue: same_event_id=true')
        print('10-1 Recovered: sent=1, pending=0')
        print('10-2 Replay: HTTP 200, same_post_id=true')
        print('10-2 Post count after replay: 1')
        print('10-2 Changed payload: HTTP 409')
        print('RESULT: PASS (real isolated HTTP server, no mock transport)')
        print('Full receipt: evidence/delivery-integration.json')
    else:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
