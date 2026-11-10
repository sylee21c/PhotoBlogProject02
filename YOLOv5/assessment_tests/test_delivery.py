import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import uuid

import cv2
import numpy as np
import requests
from changedetection import ChangeDetection, PresenceFilter
from edge_upload import ApiUploader, EventQueue, PermanentUploadError, QueueWorker, UploadConfig


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue = EventQueue(self.temp.name, 'http://127.0.0.1:8002', 'student')
        ok, image = cv2.imencode('.jpg', np.zeros((16,24,3), dtype=np.uint8))
        assert ok
        self.jpeg = image.tobytes()

    def test_pending_event_survives_reopening_queue(self):
        event_id = self.queue.enqueue('person', 'appeared', self.jpeg)
        reopened = EventQueue(self.temp.name, 'http://127.0.0.1:8002', 'student')
        self.assertEqual(reopened.due()['event_id'], event_id)
        self.assertEqual(Path(reopened.due()['image_path']).read_bytes(), self.jpeg)

    def test_other_servers_and_accounts_cannot_consume_this_queue(self):
        self.queue.enqueue('person', 'appeared', self.jpeg)
        other = EventQueue(self.temp.name, 'http://127.0.0.1:8003', 'student')
        self.assertIsNone(other.due())
        other = EventQueue(self.temp.name, 'http://127.0.0.1:8002', 'other')
        self.assertIsNone(other.due())

    def test_transport_failure_keeps_same_event_for_retry(self):
        event_id = self.queue.enqueue('person', 'appeared', self.jpeg)
        uploader = Mock()
        uploader.upload.side_effect = [requests.Timeout(), 17]
        worker = QueueWorker(self.queue, uploader, background=False)
        worker.process_one()
        self.assertEqual(self.queue.status()['counts']['pending'], 1)
        worker.process_one(now=float('inf'))
        state = self.queue.status()
        self.assertEqual(state['counts']['sent'], 1)
        self.assertEqual(state['events'][0]['post_id'], 17)
        self.assertEqual(uploader.upload.call_args_list[0].args[0]['event_id'], event_id)
        self.assertEqual(uploader.upload.call_args_list[1].args[0]['event_id'], event_id)

    def test_rejected_event_is_retained_but_not_retried_forever(self):
        self.queue.enqueue('person', 'appeared', self.jpeg)
        uploader = Mock()
        uploader.upload.side_effect = PermanentUploadError('HTTP 409')
        worker = QueueWorker(self.queue, uploader, background=False)
        worker.process_one()
        self.assertEqual(self.queue.status()['counts']['blocked'], 1)
        self.assertFalse(worker.process_one(now=float('inf')))

    def test_event_id_cannot_be_reused_for_different_payload(self):
        event_id = self.queue.enqueue('person', 'appeared', self.jpeg)
        self.assertEqual(self.queue.enqueue('person', 'appeared', self.jpeg, event_id), event_id)
        with self.assertRaises(ValueError):
            self.queue.enqueue('bus', 'different', self.jpeg, event_id)

    def test_credentials_are_not_persisted(self):
        self.queue.enqueue('person', 'appeared', self.jpeg)
        self.assertNotIn('token', json.dumps(self.queue.status()))
        with self.queue.connect() as db:
            columns=[r[1] for r in db.execute('PRAGMA table_info(events)')]
        self.assertNotIn('password',columns)
        self.assertNotIn('token',columns)


class TransitionTests(unittest.TestCase):
    def test_one_frame_dropout_does_not_rearm_appearance(self):
        presence = PresenceFilter(1, 3)
        self.assertEqual([presence.update('a',[1]) for _ in range(3)], [[0],[0],[1]])
        self.assertEqual(presence.update('a',[0]), [1])
        self.assertEqual(presence.update('a',[1]), [1])
        self.assertEqual([presence.update('a',[0]) for _ in range(3)], [[1],[1],[0]])
        self.assertEqual(presence.update('b',[1]), [0])

    def test_single_image_can_be_confirmed_immediately(self):
        self.assertEqual(PresenceFilter(2,1).update('image',[1,0]), [1,0])

    def test_same_class_only_uploads_on_zero_to_one_and_streams_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            config=UploadConfig('http://127.0.0.1:8002','test',token='test-only-token')
            cd=ChangeDetection({0:'person',1:'bus'},config,directory,background=False)
            frame=np.zeros((16,24,3),dtype=np.uint8)
            try:
                self.assertIsNone(cd.add(None,[0,0],None,frame))
                first=cd.add(None,[1,0],None,frame)
                self.assertIsNotNone(first)
                self.assertIsNone(cd.add(None,[1,0],None,frame))
                cd.add(None,[0,0],None,frame)
                second=cd.add(None,[1,0],None,frame)
                self.assertNotEqual(first,second)
                self.assertIsNotNone(cd.add(None,[1,0],None,frame,stream_id='camera-two'))
                self.assertEqual(cd.queue.status()['counts']['pending'],3)
            finally:cd.close(0)


class ProtocolTests(unittest.TestCase):
    setUp = QueueTests.setUp

    def test_post_requires_matching_event_acknowledgement(self):
        event_id=self.queue.enqueue('person','appeared',self.jpeg)
        response=Mock(status_code=201,headers={})
        response.json.return_value={'id':3}
        session=Mock();session.post.return_value=response
        client=ApiUploader(UploadConfig('http://127.0.0.1:8002','test',token='test-only-token'),session)
        with self.assertRaises(PermanentUploadError):client.upload(self.queue.due())
        response.headers={'X-Event-ID':event_id}
        self.assertEqual(client.upload(self.queue.due()),3)
        self.assertFalse(session.post.call_args.kwargs['allow_redirects'])


if __name__=='__main__':unittest.main()
