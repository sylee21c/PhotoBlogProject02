from django import forms
from .models import Post
from .validation import validate_photo

class PostForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['image'].required = False

    class Meta:
        model = Post
        fields = ['title', 'text', 'image']
        widgets = {'title': forms.TextInput(attrs={'placeholder': '사진의 제목', 'maxlength': 200}),
                   'text': forms.Textarea(attrs={'rows': 5, 'maxlength': 5000, 'placeholder': '내용을 입력하세요.'}),
                   'image': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'})}

    def clean_title(self):
        value = self.cleaned_data['title'].strip()
        if not value:
            raise forms.ValidationError('제목을 입력하세요.')
        return value

    def clean_image(self):
        if self.instance.pk and not self.files.get('image'):
            return self.instance.image
        return validate_photo(self.cleaned_data['image'])
