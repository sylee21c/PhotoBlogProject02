import uuid
from pathlib import Path
from django.conf import settings
from django.db import models
from django.utils import timezone

def image_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f'photos/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{extension}'

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField('제목', max_length=200)
    text = models.TextField('내용', max_length=5000)
    image = models.ImageField('사진', upload_to=image_path)
    created_date = models.DateTimeField(default=timezone.now, editable=False)
    published_date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-published_date', '-pk']

    def __str__(self):
        return self.title

    def publish(self):
        self.published_date = timezone.now()
        self.save(update_fields=['published_date'])


class EdgeUploadReceipt(models.Model):
    """A retry identifies the same event, even after its photo is deleted."""
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event_id = models.UUIDField()
    payload_sha256 = models.CharField(max_length=64)
    post = models.ForeignKey(Post, null=True, on_delete=models.SET_NULL)
    created_date = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['author', 'event_id'], name='unique_author_edge_event')]
