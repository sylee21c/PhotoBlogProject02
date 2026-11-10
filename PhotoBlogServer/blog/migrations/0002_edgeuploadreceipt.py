from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('blog', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='EdgeUploadReceipt',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('event_id', models.UUIDField()),
            ('payload_sha256', models.CharField(max_length=64)),
            ('created_date', models.DateTimeField(default=django.utils.timezone.now)),
            ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ('post', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='blog.post')),
        ],
        options={'constraints': [models.UniqueConstraint(fields=('author', 'event_id'), name='unique_author_edge_event')]},
    )]
