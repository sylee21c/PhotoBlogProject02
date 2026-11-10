from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import Post
from .validation import validate_photo

class PostSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)
    author = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Post
        fields = ['id', 'author', 'author_name', 'title', 'text', 'created_date', 'published_date', 'image']
        read_only_fields = ['id', 'author', 'created_date', 'published_date']
        extra_kwargs = {'title': {'allow_blank': False, 'trim_whitespace': True},
                        'text': {'allow_blank': False, 'max_length': 5000}}

    def validate_image(self, value):
        try:
            return validate_photo(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
