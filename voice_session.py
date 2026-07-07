"""
voice_session.py — In-memory session store for voice calls
===========================================================
Tracks per-call conversation history, silence strikes, and metadata.
"""

import time
import logging
from threading import Lock

log = logging.getLogger("SigmaVoice.Sessions")

MAX_TURNS   = 10     # keep last N Q&A pairs
SESSION_TTL = 3600   # 1 hour auto-expire


class VoiceSessionManager:

    def __init__(self):
        self._store: dict[str, dict] = {}
        self._lock  = Lock()

    def create(self, call_sid: str) -> dict:
        with self._lock:
            s = {
                "call_sid":       call_sid,
                "created_at":     time.time(),
                "last_active":    time.time(),
                "history":        [],
                "silence_strikes": 0,
                "turn_count":     0,
                "current_section": None,
            }
            self._store[call_sid] = s
            log.info("Session created: %s", call_sid[:8])
            return s

    def get(self, call_sid: str) -> dict:
        with self._lock:
            s = self._store.get(call_sid)
            if not s:
                log.warning("Session not found for %s — creating", call_sid[:8])
                s = self.create(call_sid)
            s["last_active"] = time.time()
            return dict(s)   # return copy

    def update(self, call_sid: str, **kwargs) -> None:
        with self._lock:
            if call_sid in self._store:
                self._store[call_sid].update(kwargs)
                self._store[call_sid]["last_active"] = time.time()

    def close(self, call_sid: str) -> None:
        with self._lock:
            s = self._store.pop(call_sid, None)
            if s:
                duration = time.time() - s["created_at"]
                log.info("Session closed: %s | turns=%d | duration=%.0fs",
                         call_sid[:8], s["turn_count"], duration)

    def get_history(self, call_sid: str) -> list[dict]:
        s = self.get(call_sid)
        return s.get("history", [])

    def add_turn(self, call_sid: str, user: str, assistant: str) -> None:
        with self._lock:
            s = self._store.get(call_sid)
            if not s:
                return
            s["history"].append({"role": "user",      "content": user})
            s["history"].append({"role": "assistant",  "content": assistant})
            max_msgs = MAX_TURNS * 2
            if len(s["history"]) > max_msgs:
                s["history"] = s["history"][-max_msgs:]
            s["turn_count"]      += 1
            s["silence_strikes"]  = 0

    @property
    def active_count(self) -> int:
        return len(self._store)
