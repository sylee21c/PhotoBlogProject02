"""Select a newly detected public post; do not mark screenshots as completed."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
import requests

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--post-id',type=int,required=True)
    parser.add_argument('--server',default='http://127.0.0.1:8002')
    args=parser.parse_args()
    origin=args.server.rstrip('/')
    parsed=urlsplit(origin)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        parser.error('--server must be an http(s) origin without a path or credentials')
    if args.post_id < 1:parser.error('--post-id must be positive')
    plan_file=ROOT/'evidence/photo-plan.json'
    if plan_file.exists():
        plan=json.loads(plan_file.read_text(encoding='utf-8'))
        if origin==plan.get('temporary_local_server') and args.post_id<=plan.get('last_temporary_post_id',0):
            parser.error('This is an earlier temporary post. Capture a new scene and select its new post ID.')
    response=requests.get(f'{origin}/api_root/Post/{args.post_id}/',timeout=8,allow_redirects=False)
    if response.status_code!=200:raise RuntimeError(f'Post lookup returned HTTP {response.status_code}')
    post=response.json()
    if post['id']!=args.post_id:raise RuntimeError('Post ID mismatch')
    image_url=post['image']
    if urlsplit(image_url)[:2]!=parsed[:2]:raise RuntimeError('Image must be served by the selected server')
    payload=bytearray()
    with requests.get(image_url,timeout=8,allow_redirects=False,stream=True) as photo:
        if photo.status_code!=200:raise RuntimeError(f'Image returned HTTP {photo.status_code}')
        for chunk in photo.iter_content(65536):
            payload.extend(chunk)
            if len(payload)>10*1024*1024:raise RuntimeError('Image exceeds 10 MiB')
    with Image.open(io.BytesIO(payload)) as image:
        if image.format!='JPEG':raise RuntimeError('Select a JPEG created by the YOLO uploader')
        image.verify()
    out=ROOT/'evidence';out.mkdir(exist_ok=True)
    (out/'final-detected-photo.jpg').write_bytes(payload)
    manifest={'state':'selected_needs_web_and_android_captures','server':origin,
              'post':post,'image_file':'evidence/final-detected-photo.jpg',
              'image_sha256':hashlib.sha256(payload).hexdigest(),
              'web_detail_url':f'{origin}/post/{args.post_id}/',
              'baseline_screenshot_complete':False,'web_screenshot_complete':False,
              'android_screenshot_complete':False}
    (out/'final-photo-candidate.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Selected post:',args.post_id)
    print('Title:',post['title'])
    print('Web detail:',manifest['web_detail_url'])
    print('Image SHA256:',manifest['image_sha256'])
    print('Saved evidence/final-photo-candidate.json; web and Android captures still required.')


if __name__=='__main__':main()
