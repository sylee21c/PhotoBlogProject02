from django.core.exceptions import ValidationError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}

def validate_photo(image):
    """Validate decoded format as well as length, rather than trusting MIME headers."""
    if image.size > MAX_IMAGE_BYTES:
        raise ValidationError('사진은 10 MB 이하로 선택하세요.')
    from pathlib import Path
    if Path(image.name).suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
        raise ValidationError('파일 확장자는 jpg, jpeg, png, webp 중 하나여야 합니다.')
    from PIL import Image, UnidentifiedImageError
    try:
        image.seek(0)
        with Image.open(image) as photo:
            if photo.format not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError('JPEG, PNG, WebP 사진만 지원합니다.')
            if photo.width * photo.height > 40_000_000:
                raise ValidationError('사진은 4천만 화소 이하로 선택하세요.')
            photo.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError('올바른 이미지 파일을 선택하세요.') from exc
    finally:
        image.seek(0)
    return image
