"""Capture real HTTP request bytes and multipart images for assessment ID 7.

Authorization headers are redacted before saving; multipart binary bytes are preserved.
This diagnostic server is separate from Django and must not be deployed publicly.
"""
import argparse
import hashlib
import json
import re
import socket
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

MAX_BODY = 12 * 1024 * 1024

def receive_request(connection):
    data = bytearray()
    while b'\r\n\r\n' not in data:
        chunk = connection.recv(4096)
        if not chunk:
            raise ValueError('Incomplete HTTP headers')
        data.extend(chunk)
        if len(data) > 65536:
            raise ValueError('HTTP headers too large')
    headers, body = bytes(data).split(b'\r\n\r\n', 1)
    lengths = re.findall(br'^Content-Length:\s*(\d+)\s*$', headers, re.I | re.M)
    if re.search(br'^Transfer-Encoding:', headers, re.I | re.M):
        raise ValueError('Use Content-Length; chunked encoding is not supported by this diagnostic server.')
    length = int(lengths[0]) if lengths else 0
    if len(lengths) > 1 or length > MAX_BODY:
        raise ValueError('Invalid Content-Length')
    while len(body) < length:
        chunk = connection.recv(min(65536, length - len(body)))
        if not chunk:
            raise ValueError('Incomplete HTTP body')
        body += chunk
    return headers + b'\r\n\r\n' + body[:length]

def save_request(raw, output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    header, body = raw.split(b'\r\n\r\n', 1)
    header = re.sub(br'^(Authorization|Cookie):[^\r\n]*', br'\1: [REDACTED]', header, flags=re.I | re.M)
    path = output / (stem + '.bin')
    path.write_bytes(header + b'\r\n\r\n' + body)
    # Parse MIME parts using the standard library, so binary boundary-like bytes survive.
    mime_headers = b'\r\n'.join(header.split(b'\r\n')[1:])
    message = BytesParser(policy=default).parsebytes(mime_headers + b'\r\n\r\n' + body)
    lines = [header.decode('utf-8', errors='replace'), '', '--- Body inspection ---']
    if message.is_multipart():
        for part in message.iter_parts():
            name = part.get_param('name', header='content-disposition')
            data = part.get_payload(decode=True) or b''
            if part.get_filename():
                digest = hashlib.sha256(data).hexdigest()
                lines.append(f'File field={name}, name={part.get_filename()}, type={part.get_content_type()}, bytes={len(data)}, sha256={digest}')
                if name == 'image' and part.get_content_type() in {'image/png', 'image/jpeg', 'image/webp'}:
                    suffix = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[part.get_content_type()]
                    (output / (stem + '-image' + suffix)).write_bytes(data)
            else:
                lines.append(f'{name}: {data.decode("utf-8", errors="replace")}')
    else:
        lines.append(body.decode('utf-8', errors='replace'))
    (output / (stem + '.txt')).write_text('\n'.join(lines), encoding='utf-8')
    return path

def serve(host='127.0.0.1', port=8001, output='../evidence/socket', ready=None, stop=None):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port)); listener.listen(8); listener.settimeout(.25)
        if ready is not None:
            ready.port = listener.getsockname()[1]; ready.set()
        print(f'Socket capture listening on http://{host}:{listener.getsockname()[1]}', flush=True)
        while stop is None or not stop.is_set():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            with connection:
                connection.settimeout(10)
                try:
                    raw = receive_request(connection)
                    saved = save_request(raw, output)
                    is_post = raw.startswith(b'POST ')
                    payload = json.dumps({'received': True} if is_post else []).encode()
                    status = b'201 Created' if is_post else b'200 OK'
                    print(f'Saved: {saved.name} ({len(raw)} bytes)', flush=True)
                except (ValueError, OSError) as error:
                    status = b'400 Bad Request'; payload = json.dumps({'error': str(error)}).encode()
                connection.sendall(b'HTTP/1.1 ' + status + b'\r\nContent-Type: application/json\r\nContent-Length: ' + str(len(payload)).encode() + b'\r\nConnection: close\r\n\r\n' + payload)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1'); parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--output', default='../evidence/socket')
    args = parser.parse_args()
    try:
        serve(args.host, args.port, args.output)
    except KeyboardInterrupt:
        pass
