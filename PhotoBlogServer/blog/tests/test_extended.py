import io
from unittest.mock import patch
from pathlib import Path
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.db import transaction
from rest_framework.test import APITestCase, APITransactionTestCase
from .test_api import PhotoApiFixture, image_upload
from blog.models import Post
from blog.validation import validate_photo


class ExtendedPostTests(PhotoApiFixture, APITestCase):
    def test_pagination_is_opt_in_and_preserves_lecture_contract(self):
        self.assertIsInstance(self.client.get(self.url).json(),list)
        response=self.client.get(self.url,{'page':1,'page_size':1})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['count'],1)
        self.assertEqual(len(response.json()['results']),1)
        self.assertIsNone(response.json()['next'])

    def test_pagination_navigation_sorting_and_page_size_cap(self):
        for i in range(32):Post.objects.create(author=self.owner,title=f'写真 {i:02}',text='page fixture',image=self.post.image.name)
        first=self.client.get(self.url,{'page':1,'page_size':2,'ordering':'oldest'}).json()
        self.assertEqual(first['count'],33);self.assertEqual(first['results'][0]['id'],self.post.pk)
        self.assertIsNotNone(first['next']);self.assertIsNone(first['previous'])
        second=self.client.get(self.url,{'page':2,'page_size':2,'ordering':'oldest'}).json()
        self.assertIsNotNone(second['previous']);self.assertNotEqual(first['results'][0]['id'],second['results'][0]['id'])
        self.assertEqual(len(self.client.get(self.url,{'page_size':999}).json()['results']),30)
        self.assertEqual(self.client.get(self.url,{'page':999}).status_code,404)

    def test_search_applies_before_pagination(self):
        Post.objects.create(author=self.owner,title='별빛',text='다른 사진',image=self.post.image.name)
        result=self.client.get(self.url,{'page':1,'q':'바다'}).json()
        self.assertEqual(result['count'],1);self.assertEqual(result['results'][0]['id'],self.post.pk)

    def test_account_profile_requires_auth_and_identifies_token_owner(self):
        self.assertEqual(self.client.get('/api/me/').status_code,401)
        self.authenticate()
        self.assertEqual(self.client.get('/api/me/').json(),{'id':self.owner.pk,'username':'owner'})

    def test_api_delete_removes_file_after_commit(self):
        self.authenticate();path=Path(self.post.image.path)
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.delete(f'{self.url}{self.post.pk}/')
            self.assertTrue(path.exists(),'File removed before database commit')
        self.assertEqual(response.status_code,204);self.assertFalse(path.exists())

    def test_rolled_back_deletion_retains_database_row_and_image(self):
        pk=self.post.pk;image=Path(self.post.image.path)
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaisesRegex(RuntimeError,'rollback'):
                with transaction.atomic():
                    self.post.delete()
                    raise RuntimeError('rollback')
        self.assertTrue(Post.objects.filter(pk=pk).exists());self.assertTrue(image.exists())

    def test_storage_cleanup_failure_is_logged_after_successful_delete(self):
        self.authenticate();pk=self.post.pk;image=Path(self.post.image.path)
        with patch.object(self.post.image.storage,'delete',side_effect=OSError('storage unavailable')):
            with self.assertLogs('blog.signals',level='WARNING'):
                with self.captureOnCommitCallbacks(execute=True):response=self.client.delete(f'{self.url}{pk}/')
        self.assertEqual(response.status_code,204)
        self.assertFalse(Post.objects.filter(pk=pk).exists());self.assertTrue(image.exists())

    def test_api_replacing_photo_removes_previous_file_but_retains_new(self):
        self.authenticate();previous=Path(self.post.image.path)
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.patch(f'{self.url}{self.post.pk}/',{'image':image_upload('replacement.png')},format='multipart')
            self.assertTrue(previous.exists())
        self.assertEqual(response.status_code,200,response.data)
        self.post.refresh_from_db();self.assertTrue(Path(self.post.image.path).exists());self.assertFalse(previous.exists())

    def test_deleting_one_shared_reference_does_not_delete_shared_image(self):
        second=Post.objects.create(author=self.owner,title='shared',text='shared',image=self.post.image.name)
        image=Path(self.post.image.path)
        with self.captureOnCommitCallbacks(execute=True):self.post.delete()
        self.assertTrue(image.exists())
        with self.captureOnCommitCallbacks(execute=True):second.delete()
        self.assertFalse(image.exists())

    def test_api_edit_text_does_not_delete_or_change_image(self):
        self.authenticate();before=self.post.image.name
        with self.captureOnCommitCallbacks(execute=True):response=self.client.patch(f'{self.url}{self.post.pk}/',{'title':'새로운 제목'})
        self.assertEqual(response.status_code,200);self.post.refresh_from_db()
        self.assertEqual(self.post.image.name,before);self.assertTrue(Path(self.post.image.path).exists())

    def test_web_owner_edits_without_selecting_new_image(self):
        self.client.force_login(self.owner);path=f'/post/{self.post.pk}/edit/'
        response=self.client.post(path,{'title':'웹 수정','text':'사진은 유지'},format='multipart')
        self.assertEqual(response.status_code,302)
        self.post.refresh_from_db();self.assertEqual(self.post.title,'웹 수정');self.assertTrue(Path(self.post.image.path).exists())

    def test_other_user_cannot_edit_or_delete_through_web(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(f'/post/{self.post.pk}/edit/',{'title':'wrong','text':'wrong'}).status_code,403)
        self.assertEqual(self.client.post(f'/post/{self.post.pk}/delete/').status_code,403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
    def test_delete_get_is_only_confirmation_and_post_deletes(self):
        self.client.force_login(self.owner);path=f'/post/{self.post.pk}/delete/'
        response=self.client.get(path)
        self.assertContains(response,'삭제 확인');self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
        with self.captureOnCommitCallbacks(execute=True):response=self.client.post(path)
        self.assertEqual(response.status_code,302);self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_rejected_image_replacement_keeps_existing_image(self):
        self.authenticate();previous=Path(self.post.image.path)
        response=self.client.patch(f'{self.url}{self.post.pk}/',{'image':SimpleUploadedFile('invalid.png',b'bad')},format='multipart')
        self.assertEqual(response.status_code,400);self.assertTrue(previous.exists())

    def test_file_over_10mb_is_rejected(self):
        photo=SimpleUploadedFile('oversized.png',b'0'*(10*1024*1024+1))
        with self.assertRaisesRegex(ValidationError,'10 MB'):validate_photo(photo)

    def test_web_mutation_requires_csrf_even_for_owner(self):
        browser=Client(enforce_csrf_checks=True);browser.force_login(self.owner)
        url=f'/post/{self.post.pk}/delete/'
        self.assertEqual(browser.post(url).status_code,403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
        browser.get(url)
        csrf=browser.cookies['csrftoken'].value
        with self.captureOnCommitCallbacks(execute=True):response=browser.post(url,{'csrfmiddlewaretoken':csrf})
        self.assertEqual(response.status_code,302);self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_web_mutations_reject_unsupported_methods(self):
        self.client.force_login(self.owner)
        for action in ['edit','delete']:
            self.assertEqual(self.client.put(f'/post/{self.post.pk}/{action}/').status_code,405)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())


class AutocommitImageTests(PhotoApiFixture, APITransactionTestCase):
    def test_replacement_in_real_autocommit_removes_old_photo(self):
        self.authenticate();previous=Path(self.post.image.path)
        self.assertTrue(transaction.get_autocommit())
        response=self.client.patch(f'{self.url}{self.post.pk}/',{'image':image_upload('autocommit.png')},format='multipart')
        self.assertEqual(response.status_code,200)
        self.post.refresh_from_db()
        self.assertTrue(Path(self.post.image.path).exists())
        self.assertFalse(previous.exists())
