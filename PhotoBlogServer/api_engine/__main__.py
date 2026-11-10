import argparse
import json
import os
from pathlib import Path
from .client import PhotoBlogClient

parser = argparse.ArgumentParser(description='API GET / multipart POST verifier (never prints credentials).')
parser.add_argument('--server', default='http://127.0.0.1:8000')
parser.add_argument('--query', default='')
parser.add_argument('--image', type=Path)
parser.add_argument('--title', default='API 업로드 검증')
parser.add_argument('--text', default='Python API 검증 엔진에서 전송했습니다.')
parser.add_argument('--output', type=Path)
args = parser.parse_args()
client = PhotoBlogClient(args.server, os.getenv('PHOTOBLOG_TOKEN', ''))
result = client.upload(args.title, args.text, args.image) if args.image else client.posts(args.query)
text = json.dumps(result, ensure_ascii=False, indent=2)
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding='utf-8')
print(text)
