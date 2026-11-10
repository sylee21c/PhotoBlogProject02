"""Create an isolated local demo account and three explicitly labelled fixtures."""
import json
import os
import secrets
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token
from blog.management.sample_photos import seed_photos

class Command(BaseCommand):
    help = 'Create a local demo user and credited sample photos; credentials stay in ignored .runtime.'
    def add_arguments(self, parser):
        parser.add_argument('--username', default='student')
        parser.add_argument('--no-images', action='store_true')

    def handle(self, *args, **options):
        from django.conf import settings
        runtime = settings.BASE_DIR.parent / '.runtime'
        runtime.mkdir(exist_ok=True)
        credential_file = runtime / 'demo-credentials.json'
        if credential_file.exists():
            credentials = json.loads(credential_file.read_text(encoding='utf-8'))
        else:
            credentials = {'username': options['username'], 'password': secrets.token_urlsafe(18)}
        user, created = get_user_model().objects.get_or_create(username=credentials['username'])
        if created:
            user.set_password(credentials['password'])
            user.save()
        token, _ = Token.objects.get_or_create(user=user)
        credentials['token'] = token.key
        credential_file.write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding='utf-8')
        if not options['no_images']:
            seed_photos(user)
        self.stdout.write(self.style.SUCCESS(f'Demo ready. Private credentials: {credential_file}'))
