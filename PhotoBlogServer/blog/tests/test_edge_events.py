import uuid
from rest_framework.test import APITestCase
from .test_api import PhotoApiFixture, image_upload
from blog.models import EdgeUploadReceipt, Post


class EdgeEventTests(PhotoApiFixture, APITestCase):
    def setUp(self):
        super().setUp()
        self.authenticate()
        self.event_id = str(uuid.uuid4())

    def send(self, title='person', event_id=None):
        return self.client.post(self.url, {'title': title, 'text': 'YOLOv5 appearance', 'image': image_upload()},
                                format='multipart', HTTP_X_EVENT_ID=event_id or self.event_id)

    def test_replayed_event_returns_same_post_without_duplicate_file(self):
        first = self.send()
        second = self.send()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['id'], second.json()['id'])
        self.assertEqual(second['X-Event-Replayed'], 'true')
        self.assertEqual(EdgeUploadReceipt.objects.count(), 1)
        self.assertEqual(Post.objects.count(), 2)  # fixture + new event
        from pathlib import Path
        self.assertEqual(len(list(Path(self.temp.name).rglob('*.png'))), 2)

    def test_reuse_of_id_with_different_content_is_rejected(self):
        self.send()
        response = self.send(title='different')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Post.objects.count(), 2)

    def test_same_event_id_is_scoped_to_authenticated_author(self):
        one = self.send()
        self.authenticate(self.other)
        two = self.send()
        self.assertEqual(two.status_code, 201)
        self.assertNotEqual(one.json()['id'], two.json()['id'])

    def test_retry_does_not_restore_an_intentionally_deleted_post(self):
        result = self.send()
        Post.objects.get(pk=result.json()['id']).delete()
        self.assertEqual(self.send().status_code, 410)

    def test_malformed_uuid_does_not_create_post(self):
        self.assertEqual(self.send(event_id='invalid').status_code, 400)
        self.assertEqual(EdgeUploadReceipt.objects.count(), 0)

    def test_event_upload_still_requires_authentication(self):
        self.client.credentials()
        self.assertEqual(self.send().status_code, 401)

    def test_invalid_image_does_not_claim_event_id(self):
        response = self.client.post(self.url, {'title':'person', 'text':'text'},
                                    format='multipart', HTTP_X_EVENT_ID=self.event_id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(EdgeUploadReceipt.objects.count(), 0)
