import io
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, override_settings
from PIL import Image
from api_engine.client import ApiError, PhotoBlogClient, multipart
from tools.socket_capture import receive_request, save_request, serve

class HttpEngineTests(LiveServerTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.override=override_settings(MEDIA_ROOT=self.temp.name);self.override.enable();self.addCleanup(self.override.disable)
        self.user=get_user_model().objects.create_user('engine-user',password='EnginePassword-902')
        self.photo=Path(self.temp.name)/'fixture.png';Image.new('RGB',(20,20),'teal').save(self.photo)
        self.engine=PhotoBlogClient(self.live_server_url)

    def test_real_http_login_upload_query_and_delete(self):
        self.assertTrue(self.engine.login('engine-user','EnginePassword-902'))
        result=self.engine.upload('HTTP 사진 검증','실제 네트워크 multipart',self.photo)
        self.assertEqual(result['author'],self.user.pk)
        self.assertEqual(self.engine.posts('HTTP')[0]['id'],result['id'])
        status,_=self.engine.request('DELETE',f'/api_root/Post/{result["id"]}/')
        self.assertEqual(status,204);self.assertEqual(self.engine.posts(),[])

    def test_http_errors_have_machine_readable_status(self):
        with self.assertRaises(ApiError) as error: self.engine.upload('a','b',self.photo)
        self.assertEqual(error.exception.status,401)
        with self.assertRaises(ApiError) as error: self.engine.login('engine-user','wrong')
        self.assertEqual(error.exception.status,400)

    def test_non_json_error_is_reported(self):
        with self.assertRaises(ApiError) as error:self.engine.request('GET','/nonexistent-page/')
        self.assertEqual(error.exception.status,404)

class EngineUnitTests(unittest.TestCase):
    def test_rejects_unsafe_base_addresses(self):
        for address in ['file:///tmp/a','https://user:pass@host','http://','https://host?q=x','https://host#fragment']:
            with self.assertRaises(ValueError):PhotoBlogClient(address)

    def test_binary_multipart_preserves_image(self):
        with tempfile.TemporaryDirectory() as temp:
            image=Path(temp)/'image.png';binary=bytes(range(256))+b'\r\n';image.write_bytes(binary)
            data,content_type=multipart({'title':'한글'},image)
            self.assertIn(binary,data);self.assertIn('한글'.encode(),data)
            self.assertTrue(data.endswith(('--'+content_type.split('boundary=')[1]+'--\r\n').encode()))
            with self.assertRaises(ValueError):multipart({'bad\r\nfield':'x'},image)

class CaptureTests(unittest.TestCase):
    def test_socket_server_captures_real_get_post_and_extracts_exact_image(self):
        with tempfile.TemporaryDirectory() as temp:
            image=Path(temp)/'photo.png';Image.new('RGB',(12,12),'green').save(image)
            output=Path(temp)/'captures';ready=threading.Event();stop=threading.Event()
            thread=threading.Thread(target=serve,args=('127.0.0.1',0,output,ready,stop),daemon=True);thread.start()
            self.assertTrue(ready.wait(3))
            try:
                engine=PhotoBlogClient(f'http://127.0.0.1:{ready.port}',token='private-test-token')
                self.assertEqual(engine.posts(),[])
                self.assertTrue(engine.upload('캡처','내용',image)['received'])
                self.assertEqual(len(list(output.glob('*.bin'))),2)
                self.assertEqual(next(output.glob('*-image.png')).read_bytes(),image.read_bytes())
                self.assertNotIn(b'private-test-token',b''.join(p.read_bytes() for p in output.glob('*.bin')))
                self.assertIn('캡처',''.join(p.read_text(encoding='utf-8') for p in output.glob('*.txt')))
            finally:stop.set();thread.join(3)

    def test_truncated_request_is_rejected(self):
        first,second=socket.socketpair()
        with first,second:
            second.sendall(b'POST / HTTP/1.1\r\nContent-Length: 9\r\n\r\nabc');second.shutdown(socket.SHUT_WR)
            with self.assertRaisesRegex(ValueError,'Incomplete HTTP body'):receive_request(first)

    def test_chunked_request_rejected(self):
        first,second=socket.socketpair()
        with first,second:
            second.sendall(b'POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n')
            with self.assertRaisesRegex(ValueError,'Content-Length'):receive_request(first)
