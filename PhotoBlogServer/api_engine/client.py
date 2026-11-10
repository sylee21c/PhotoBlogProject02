"""Small, testable HTTP engine shared by command-line API verification tests."""
import json
import mimetypes
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

class ApiError(RuntimeError):
    def __init__(self, status, detail):
        self.status = status
        self.detail = detail
        super().__init__(f'HTTP {status}: {detail}')

def multipart(fields, image_path):
    boundary = 'PhotoBlog' + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        if not name.replace('_', '').isalnum():
            raise ValueError('Invalid multipart field name')
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    path = Path(image_path)
    filename = path.name.replace('"', '_').replace('\r', '_').replace('\n', '_')
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode(),
                   path.read_bytes(), f'\r\n--{boundary}--\r\n'.encode()])
    return b''.join(chunks), f'multipart/form-data; boundary={boundary}'

class PhotoBlogClient:
    def __init__(self, base_url, token='', timeout=15):
        parsed = urlsplit(base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
            raise ValueError('Use an http(s) server root URL without credentials, query or fragment.')
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout

    def request(self, method, path, data=None, content_type=None):
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Token ' + self.token
        if content_type:
            headers['Content-Type'] = content_type
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except HTTPError as exc:
            raw = exc.read().decode('utf-8', errors='replace')
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = raw
            raise ApiError(exc.code, detail) from exc

    def login(self, username, password):
        _, result = self.request('POST', '/api/token/', json.dumps({'username': username, 'password': password}).encode(), 'application/json')
        self.token = result['token']
        return self.token

    def posts(self, query='', ordering='newest'):
        return self.request('GET', '/api_root/Post/?' + urlencode({'q': query, 'ordering': ordering}))[1]

    def upload(self, title, text, image_path):
        data, content_type = multipart({'title': title, 'text': text}, image_path)
        return self.request('POST', '/api_root/Post/', data, content_type)[1]
