import io
import tempfile
from datetime import timedelta
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from blog.models import Post

def image_upload(name='photo.png', image_format='PNG'):
    buffer = io.BytesIO(); Image.new('RGB', (24, 16), '#245f51').save(buffer, image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/' + image_format.lower())

class PhotoApiFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.temp.name)
        self.settings_override.enable(); self.addCleanup(self.settings_override.disable)
        self.owner = get_user_model().objects.create_user('owner', password='StrongPassword-137')
        self.other = get_user_model().objects.create_user('other', password='DifferentPassword-248')
        self.token = Token.objects.create(user=self.owner)
        self.post = Post.objects.create(author=self.owner, title='푸른 바다', text='해변의 오후', image=image_upload())
        self.url = '/api_root/Post/'

    def authenticate(self, user=None):
        token = Token.objects.get_or_create(user=user or self.owner)[0]
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

class PostApiTests(PhotoApiFixture, APITestCase):

    def test_public_list_contains_absolute_image_url(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['title'], '푸른 바다')
        self.assertTrue(response.json()[0]['image'].startswith('http://testserver/media/'))

    def test_detail_has_expected_contract(self):
        response = self.client.get(f'{self.url}{self.post.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {'id','title','text','image','author','author_name','created_date','published_date'})

    def test_future_posts_are_not_exposed(self):
        self.post.published_date = timezone.now() + timedelta(days=1); self.post.save()
        self.assertEqual(self.client.get(self.url).json(), [])
        self.assertEqual(self.client.get(f'{self.url}{self.post.pk}/').status_code, 404)

    def test_upload_requires_authentication(self):
        self.assertEqual(self.client.post(self.url, {'title':'new','text':'text','image':image_upload()}, format='multipart').status_code, 401)

    def test_invalid_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid')
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_multipart_upload_saves_original_image_and_authenticated_author(self):
        self.authenticate()
        photo = image_upload(); original = photo.read(); photo.seek(0)
        response = self.client.post(self.url, {'title':'새 사진','text':'한글 본문','author':self.other.pk,'image':photo}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        post = Post.objects.get(pk=response.json()['id'])
        self.assertEqual(post.author, self.owner)
        with post.image.open('rb') as saved: self.assertEqual(saved.read(), original)
        self.assertEqual(post.text, '한글 본문')

    def test_missing_image_rejected(self):
        self.authenticate(); self.assertEqual(self.client.post(self.url, {'title':'a','text':'b'}).status_code, 400)

    def test_non_image_bytes_rejected(self):
        self.authenticate()
        response = self.client.post(self.url, {'title':'a','text':'b','image':SimpleUploadedFile('fake.png', b'not an image')}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_gif_rejected_even_if_named_png(self):
        self.authenticate()
        self.assertEqual(self.client.post(self.url, {'title':'a','text':'b','image':image_upload('fake.png','GIF')}, format='multipart').status_code, 400)

    def test_html_filename_rejected_even_if_valid_image(self):
        self.authenticate()
        self.assertEqual(self.client.post(self.url, {'title':'a','text':'b','image':image_upload('photo.html')}, format='multipart').status_code, 400)

    def test_blank_title_and_oversized_text_rejected(self):
        self.authenticate()
        for fields in [{'title':'   ','text':'ok'}, {'title':'x'*201,'text':'ok'}, {'title':'ok','text':'x'*5001}]:
            fields['image'] = image_upload()
            self.assertEqual(self.client.post(self.url, fields, format='multipart').status_code, 400)

    def test_owner_can_update_and_delete(self):
        self.authenticate(); path=f'{self.url}{self.post.pk}/'
        self.assertEqual(self.client.patch(path, {'title':'수정된 제목'}).status_code, 200)
        self.post.refresh_from_db(); self.assertEqual(self.post.title,'수정된 제목')
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_other_user_cannot_modify_or_delete(self):
        self.authenticate(self.other); path=f'{self.url}{self.post.pk}/'
        self.assertEqual(self.client.patch(path, {'title':'wrong'}).status_code,403)
        self.assertEqual(self.client.delete(path).status_code,403)

    def test_search_matches_title_or_body(self):
        self.assertEqual(len(self.client.get(self.url, {'q':'바다'}).json()),1)
        self.assertEqual(len(self.client.get(self.url, {'q':'해변'}).json()),1)
        self.assertEqual(self.client.get(self.url, {'q':'없는검색어'}).json(),[])

    def test_ordering_and_unknown_order_fallback(self):
        second=Post.objects.create(author=self.owner,title='가나다',text='b',image=image_upload())
        self.assertEqual(self.client.get(self.url, {'ordering':'newest'}).json()[0]['id'],second.pk)
        self.assertEqual(self.client.get(self.url, {'ordering':'oldest'}).json()[0]['id'],self.post.pk)
        self.assertEqual(self.client.get(self.url, {'ordering':'title'}).json()[0]['title'],'가나다')
        self.assertEqual(self.client.get(self.url, {'ordering':'-evil'}).json()[0]['id'],second.pk)

    def test_token_login_success_and_failure(self):
        response=self.client.post('/api/token/', {'username':'owner','password':'StrongPassword-137'})
        self.assertEqual(response.status_code,200); self.assertEqual(response.json()['token'],self.token.key)
        self.assertEqual(self.client.post('/api/token/', {'username':'owner','password':'wrong'}).status_code,400)

    def test_health_and_api_root(self):
        self.assertEqual(self.client.get('/api/health/').json()['posts'],1)
        self.assertIn('Post',self.client.get('/api_root/').json())

    def test_options_lists_post_method(self):
        self.assertIn('POST',self.client.options(self.url)['Allow'])

    def test_model_publish_and_label(self):
        self.assertEqual(str(self.post),'푸른 바다')
        self.post.publish(); self.assertLessEqual(self.post.published_date,timezone.now())

    def test_web_list_detail_and_search(self):
        self.assertContains(self.client.get('/'),'푸른 바다')
        self.assertContains(self.client.get(f'/post/{self.post.pk}/'),'해변의 오후')
        self.assertNotContains(self.client.get('/', {'q':'없는사진'}),'푸른 바다')

    def test_web_editor_requires_login_and_creates_post(self):
        self.assertEqual(self.client.get('/post/new/').status_code,302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/post/new/').status_code,200)
        response=self.client.post('/post/new/', {'title':'웹 게시','text':'웹에서 작성','image':image_upload()},format='multipart')
        self.assertEqual(response.status_code,302)
        self.assertTrue(Post.objects.filter(title='웹 게시',author=self.owner).exists())

    def test_invalid_web_form_preserves_input_and_error(self):
        self.client.force_login(self.owner)
        response=self.client.post('/post/new/', {'title':'보존할 제목','text':'본문'},format='multipart')
        self.assertEqual(response.status_code,200); self.assertContains(response,'보존할 제목')
        self.assertFalse(Post.objects.filter(title='보존할 제목').exists())
