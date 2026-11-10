"""Add credited sample photos without creating a usable login credential."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from blog.management.sample_photos import seed_photos


class Command(BaseCommand):
    help = 'Add three credited sample photos; an absent author is inactive.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='gallery_demo')

    def handle(self, *args, **options):
        user, created = get_user_model().objects.get_or_create(
            username=options['username'], defaults={'is_active': False})
        if created:
            user.set_unusable_password()
            user.save()
        seed_photos(user)
        self.stdout.write('Sample photos ready.')
