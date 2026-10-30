"""Firestore claims serialize chat mutations across processes.

The API response, message pair and turn state commit together. A retry after a
lost response replays the stored payload; an expired worker cannot commit.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from google.cloud import firestore


class ChatRequestConflict(Exception):
    pass


class ChatRequestRepository:
    def __init__(self, db):
        self.db = db

    def claim(self, assessment_id, user_id, client_id, operation, message=""):
        lock = self.db.collection("emotion_chat_operations").document(assessment_id)
        request = lock.collection("requests").document(
            hashlib.sha256(f"{operation}:{client_id}".encode()).hexdigest()
        )
        fingerprint = hashlib.sha256(f"{user_id}:{operation}:{message}".encode()).hexdigest()
        owner = uuid4().hex
        now = datetime.now(timezone.utc)

        @firestore.transactional
        def acquire(tx):
            previous = request.get(transaction=tx).to_dict() or {}
            active = lock.get(transaction=tx).to_dict() or {}
            if previous and previous.get("fingerprint") != fingerprint:
                raise ChatRequestConflict("MESSAGE_ID_REUSED")
            if previous.get("status") == "completed":
                return {"response": previous["response"]}
            until = active.get("expires_at")
            if until and until > now:
                raise ChatRequestConflict("CHAT_REQUEST_PENDING")
            tx.set(lock, {"owner": owner, "expires_at": now + timedelta(minutes=3)})
            tx.set(request, {"owner": owner, "status": "pending", "fingerprint": fingerprint})
            return {"lock": lock, "request": request, "owner": owner}

        return acquire(self.db.transaction())

    def complete(self, claim, response, writes=(), expected_session=None):
        """All reads precede writes; failed validation leaves no partial turn."""
        @firestore.transactional
        def commit(tx):
            active = claim["lock"].get(transaction=tx).to_dict() or {}
            if active.get("owner") != claim["owner"]:
                raise ChatRequestConflict("CHAT_REQUEST_EXPIRED")
            if expected_session:
                ref, expected_turn = expected_session
                data = ref.get(transaction=tx).to_dict() or {}
                if data.get("status") != "active" or data.get("user_turn_count", 0) != expected_turn:
                    raise ChatRequestConflict("CHAT_SESSION_CHANGED")
            for ref, data, merge in writes:
                tx.set(ref, data, merge=merge)
            tx.update(claim["request"], {"status": "completed", "response": response})
            tx.delete(claim["lock"])

        commit(self.db.transaction())

    def release(self, claim):
        @firestore.transactional
        def unlock(tx):
            active = claim["lock"].get(transaction=tx).to_dict() or {}
            if active.get("owner") == claim["owner"]:
                tx.delete(claim["lock"])
        unlock(self.db.transaction())
