"""Load the credited example photos bundled with the server."""
import json
from pathlib import Path
from django.conf import settings
from django.core.files.base import ContentFile
from blog.models import Post


def sample_photos():
    folder = settings.BASE_DIR / 'demo_photos'
    return [(photo, folder / photo['file']) for photo in json.loads(
        (folder / 'sources.json').read_text(encoding='utf-8'))]


def seed_photos(user):
    for photo, path in sample_photos():
        if Post.objects.filter(author=user, title=photo['title']).exists():
            continue
        post = Post(author=user, title=photo['title'], text=photo['text'])
        post.image.save(path.name, ContentFile(path.read_bytes()), save=True)
