"""
DESCRIPTION: Web Push notifications. Generates and stores a VAPID key pair on first
use, keeps the list of subscribed browsers, and sends notifications to all of them.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from datetime import datetime
from typing import List, Optional

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)

# Identifies the sender to push services; they only use it to contact the operator.
VAPID_SUBJECT = "mailto:pantry@localhost"

_lock = threading.Lock()


class PushStore:
    """VAPID keys and subscriptions, persisted as JSON files in `instance_dir`."""

    def __init__(self, instance_dir: str):
        self.keys_file = os.path.join(instance_dir, "vapid.json")
        self.subs_file = os.path.join(instance_dir, "push_subscriptions.json")
        self._vapid: Optional[Vapid] = None
        self._public_key: Optional[str] = None

    # ---- Keys -------------------------------------------------------------

    def _load_keys(self):
        if self._vapid:
            return
        with _lock:
            if os.path.exists(self.keys_file):
                with open(self.keys_file) as f:
                    data = json.load(f)
                vapid = Vapid.from_pem(data["private_key"].encode())
            else:
                vapid = Vapid()
                vapid.generate_keys()
                pem = vapid.private_pem().decode()
                os.makedirs(os.path.dirname(self.keys_file), exist_ok=True)
                fd = os.open(self.keys_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as f:
                    json.dump({"private_key": pem}, f)
                logger.info("Generated new VAPID key pair at %s", self.keys_file)
            raw = vapid.public_key.public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
            self._public_key = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
            self._vapid = vapid

    @property
    def public_key(self) -> str:
        """Application server key the browser needs to subscribe (base64url)."""
        self._load_keys()
        return self._public_key

    # ---- Subscriptions ----------------------------------------------------

    def subscriptions(self) -> List[dict]:
        if not os.path.exists(self.subs_file):
            return []
        with open(self.subs_file) as f:
            return json.load(f)

    def _write(self, subs: List[dict]):
        os.makedirs(os.path.dirname(self.subs_file), exist_ok=True)
        tmp = f"{self.subs_file}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(subs, f, indent=2)
        os.replace(tmp, self.subs_file)

    def add(self, subscription: dict, label: str = "") -> None:
        if not subscription.get("endpoint") or not subscription.get("keys"):
            raise ValueError("Invalid push subscription")
        with _lock:
            subs = [s for s in self.subscriptions() if s["endpoint"] != subscription["endpoint"]]
            subs.append({
                "endpoint": subscription["endpoint"],
                "keys": subscription["keys"],
                "label": label[:120],
                "created": datetime.now().isoformat(timespec="seconds"),
            })
            self._write(subs)

    def remove(self, endpoint: str) -> None:
        with _lock:
            self._write([s for s in self.subscriptions() if s["endpoint"] != endpoint])

    def has(self, endpoint: str) -> bool:
        return any(s["endpoint"] == endpoint for s in self.subscriptions())

    # ---- Sending ----------------------------------------------------------

    def send_all(self, title: str, body: str, url: str = "/", tag: str = "pantry") -> int:
        """Notify every subscribed device. Drops subscriptions the push service says are gone.
        Returns the number of devices notified."""
        self._load_keys()
        payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
        sent = 0
        for sub in self.subscriptions():
            try:
                webpush(
                    subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                    data=payload,
                    vapid_private_key=self._vapid,
                    vapid_claims={"sub": VAPID_SUBJECT},
                    ttl=24 * 3600,
                )
                sent += 1
            except WebPushException as e:
                status = getattr(e.response, "status_code", None)
                if status in (404, 410):
                    logger.info("Removing expired push subscription (%s)", sub.get("label") or status)
                    self.remove(sub["endpoint"])
                else:
                    logger.warning("Push to %s failed: %s", sub.get("label") or "device", e)
        return sent
