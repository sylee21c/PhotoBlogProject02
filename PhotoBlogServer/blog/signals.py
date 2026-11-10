"""Remove replaced/deleted image files only after the database commits."""
import logging
from django.db import transaction
from django.db.models.signals import post_delete, pre_save, post_save
from django.dispatch import receiver
from .models import Post
logger = logging.getLogger(__name__)


def remove_unreferenced_image(storage, name):
    if name and not Post.objects.filter(image=name).exists():
        try:
            storage.delete(name)
        except OSError:
            # The DB mutation has committed. Report cleanup failure without returning
            # an ambiguous failed mutation to a client that might retry it.
            logger.warning('Committed post change; image cleanup failed for %s', name, exc_info=True)


@receiver(pre_save, sender=Post)
def cleanup_replaced_image(sender, instance, **kwargs):
    instance._previous_image = None
    if not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).values_list('image', flat=True).first()
    if previous and previous != instance.image.name:
        instance._previous_image = previous


@receiver(post_save, sender=Post)
def schedule_replaced_image_cleanup(sender, instance, **kwargs):
    # post_save is essential: on_commit executes immediately in autocommit mode.
    # Scheduling in pre_save would still see the old image referenced in the DB.
    previous = getattr(instance, '_previous_image', None)
    if previous:
        storage = instance.image.storage
        transaction.on_commit(lambda: remove_unreferenced_image(storage, previous))


@receiver(post_delete, sender=Post)
def cleanup_deleted_image(sender, instance, **kwargs):
    storage, name = instance.image.storage, instance.image.name
    transaction.on_commit(lambda: remove_unreferenced_image(storage, name))
