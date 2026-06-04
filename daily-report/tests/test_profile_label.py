"""get_profile / get_label 응답 정형 로직 커버리지(고유)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import GmailClient  # noqa: E402


class _Exec:
    def __init__(self, val):
        self._val = val

    def execute(self):
        return self._val


class _Svc:
    def __init__(self, profile=None, label=None):
        self._profile, self._label = profile, label

    def users(self):
        svc = self

        class _U:
            def getProfile(self, userId):
                return _Exec(svc._profile)

            def labels(self):
                class _L:
                    def get(self, userId, id):
                        return _Exec(svc._label)
                return _L()
        return _U()


def _client(svc):
    c = GmailClient.__new__(GmailClient)
    c._service = svc
    c._quota_manager = None
    return c


def test_get_profile_maps_fields():
    svc = _Svc(profile={"emailAddress": "me@x.com", "messagesTotal": 1200,
                        "threadsTotal": 300, "historyId": "h99"})
    out = _client(svc).get_profile()
    assert out["email"] == "me@x.com"
    assert out["messages_total"] == 1200
    assert out["threads_total"] == 300
    assert out["history_id"] == "h99"


def test_get_profile_defaults_missing_counts():
    svc = _Svc(profile={"emailAddress": "me@x.com"})
    out = _client(svc).get_profile()
    assert out["messages_total"] == 0 and out["threads_total"] == 0


def test_get_label_maps_fields_and_defaults():
    svc = _Svc(label={"id": "L1", "name": "작업", "type": "user"})
    out = _client(svc).get_label("L1")
    assert out["id"] == "L1" and out["name"] == "작업" and out["type"] == "user"
    assert out["messages_total"] == 0 and out["threads_unread"] == 0  # 누락 기본값
