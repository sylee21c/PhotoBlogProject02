"""Ch08: detect class appearance (0 -> 1), save the annotated frame and post it."""
import atexit
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import cv2
from edge_upload import ApiUploader, EventQueue, QueueWorker, UploadConfig

ROOT = Path(__file__).resolve().parent.parent


class PresenceFilter:
    """Confirm stream class presence/absence over consecutive frames."""
    def __init__(self, size, frames=3):
        if size < 1 or frames < 1:
            raise ValueError('Class count and confirmation frames must be positive.')
        self.size, self.frames, self.streams = size, frames, {}

    def update(self, stream_id, detected):
        if len(detected) != self.size:
            raise ValueError('Detection vector must match the model class count.')
        candidate, counts, stable = self.streams.setdefault(
            str(stream_id), ([0]*self.size, [0]*self.size, [0]*self.size))
        for i, value in enumerate(detected):
            value = int(bool(value))
            counts[i] = min(self.frames, counts[i]+1) if value == candidate[i] else 1
            candidate[i] = value
            if counts[i] >= self.frames:
                stable[i] = value
        return stable[:]


class ChangeDetection:
    def __init__(self, names, config=None, state_dir=None, background=True):
        self.names = [names[i] for i in range(len(names))]
        self.result_prev = {}
        if config is None:
            credential_file = Path(os.getenv('PHOTOBLOG_CREDENTIALS', ROOT / '.runtime/demo-credentials.json'))
            private = json.loads(credential_file.read_text(encoding='utf-8')) if credential_file.exists() else {}
            server = os.getenv('PHOTOBLOG_SERVER', 'http://127.0.0.1:8002').rstrip('/')
            # A local token must never silently be sent to a cloud server.
            if server != private.get('server', 'http://127.0.0.1:8002'):
                private = {}
            explicit_login = any(os.getenv(k) for k in ['PHOTOBLOG_USERNAME', 'PHOTOBLOG_PASSWORD'])
            config = UploadConfig(
                server=server,
                username=os.getenv('PHOTOBLOG_USERNAME', private.get('username', '')),
                password=os.getenv('PHOTOBLOG_PASSWORD', private.get('password', '')),
                token=os.getenv('PHOTOBLOG_TOKEN', '' if explicit_login else private.get('token', '')))
        self.queue = EventQueue(state_dir or ROOT/'.runtime/edge', config.server, config.username)
        self.worker = QueueWorker(self.queue, ApiUploader(config), background=background)
        self.closed = False
        atexit.register(self.close, 0)

    def add(self, names, detected_current, save_dir, image, stream_id='default'):
        if len(detected_current) != len(self.names):
            raise ValueError('Detection vector must match the model class count.')
        current = [int(bool(v)) for v in detected_current]
        previous = self.result_prev.get(str(stream_id), [0] * len(current))
        appeared = [self.names[i] for i, state in enumerate(current) if state and not previous[i]]
        self.result_prev[str(stream_id)] = current[:]
        if not appeared:
            return None
        # Keep the annotated frame and its original aspect ratio for later proof.
        ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            raise ValueError('Could not encode the detection frame as JPEG.')
        title = (', '.join(appeared) + ' 출현')[:200]
        observed = datetime.now(timezone.utc).isoformat()
        text = '새로 검출된 객체: %s\n검출 시각: %s' % (', '.join(appeared), observed)
        event_id = self.queue.enqueue(title, text, encoded.tobytes())
        self.worker.wake.set()
        print('EDGE appearance=%s event=%s' % (','.join(appeared), event_id), flush=True)
        return event_id

    def close(self, wait_seconds=5):
        if not self.closed:
            self.closed = True
            self.worker.close(wait_seconds)
            counts = self.queue.status()['counts']
            print('EDGE delivery sent=%s pending=%s blocked=%s' % (counts['sent'], counts['pending'], counts['blocked']), flush=True)
