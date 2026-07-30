import hashlib
import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from astrapath.config import Settings
from astrapath.phase5.metrics import MetricsRegistry

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_MUTATING_METHODS = {"POST", "PUT", "PATCH"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class SlidingWindowRateLimiter:
    def __init__(self, window_seconds: int) -> None:
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, limit: int) -> RateDecision:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= limit:
                retry_after = max(int(self.window_seconds - (now - requests[0])) + 1, 1)
                return RateDecision(False, limit, 0, retry_after)
            requests.append(now)
            return RateDecision(True, limit, limit - len(requests), 0)


class AdmissionController:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._lock = threading.Lock()
        self._active = 0

    def acquire(self) -> bool:
        with self._lock:
            if self._active >= self.limit:
                return False
            self._active += 1
            return True

    def release(self) -> None:
        with self._lock:
            self._active = max(self._active - 1, 0)


@dataclass(frozen=True)
class StoredResponse:
    request_hash: str
    status_code: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes
    expires_at: float


class IdempotencyStore:
    def __init__(self, *, ttl_seconds: int, max_entries: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: dict[str, StoredResponse] = {}
        self._inflight: dict[str, str] = {}

    def begin(
        self,
        key: str,
        request_hash: str,
    ) -> tuple[str, StoredResponse | None]:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            existing = self._entries.get(key)
            if existing:
                if existing.request_hash != request_hash:
                    return "conflict", None
                return "replay", existing
            inflight_hash = self._inflight.get(key)
            if inflight_hash is not None:
                if inflight_hash != request_hash:
                    return "conflict", None
                return "inflight", None
            self._inflight[key] = request_hash
            return "new", None

    def complete(
        self,
        key: str,
        request_hash: str,
        *,
        status_code: int,
        headers: list[tuple[bytes, bytes]],
        body: bytes,
    ) -> None:
        with self._lock:
            self._inflight.pop(key, None)
            if len(self._entries) >= self.max_entries:
                oldest_key = min(
                    self._entries,
                    key=lambda item: self._entries[item].expires_at,
                )
                self._entries.pop(oldest_key, None)
            self._entries[key] = StoredResponse(
                request_hash=request_hash,
                status_code=status_code,
                headers=tuple(headers),
                body=body,
                expires_at=time.monotonic() + self.ttl_seconds,
            )

    def abandon(self, key: str) -> None:
        with self._lock:
            self._inflight.pop(key, None)

    def _prune(self, now: float) -> None:
        expired = [
            key for key, value in self._entries.items() if value.expires_at <= now
        ]
        for key in expired:
            self._entries.pop(key, None)


class OperationalMiddleware:
    """Security, reliability, idempotency, and request metrics boundary."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: Settings,
        metrics: MetricsRegistry,
        rate_limiter: SlidingWindowRateLimiter,
        admission: AdmissionController,
        idempotency: IdempotencyStore,
    ) -> None:
        self.app = app
        self.settings = settings
        self.metrics = metrics
        self.rate_limiter = rate_limiter
        self.admission = admission
        self.idempotency = idempotency

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = time.perf_counter()
        method = scope["method"].upper()
        path = scope["path"]
        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id") or str(uuid.uuid4())
        correlation_id = headers.get("x-correlation-id")
        scope.setdefault("state", {})["request_id"] = request_id
        self.metrics.begin()

        invalid_identifier = next(
            (
                name
                for name, value in (
                    ("X-Request-ID", request_id),
                    ("X-Correlation-ID", correlation_id),
                )
                if value and not _SAFE_IDENTIFIER.fullmatch(value)
            ),
            None,
        )
        if invalid_identifier:
            await self._error(
                scope,
                receive,
                send,
                status_code=400,
                code="invalid_request_identifier",
                message=f"{invalid_identifier} contains unsupported characters or is too long",
                request_id=str(uuid.uuid4()),
                started_at=started_at,
            )
            return

        content_length = headers.get("content-length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = self.settings.max_request_bytes + 1
            if declared_length > self.settings.max_request_bytes:
                self.metrics.rejected("payload")
                await self._error(
                    scope,
                    receive,
                    send,
                    status_code=413,
                    code="payload_too_large",
                    message="Request payload exceeds the configured limit",
                    request_id=request_id,
                    started_at=started_at,
                )
                return

        client_key = self._client_key(scope, headers)
        is_auth = path.startswith(f"{self.settings.api_prefix}/auth/")
        rate_limit = (
            self.settings.auth_rate_limit_requests
            if is_auth
            else self.settings.rate_limit_requests
        )
        decision = self.rate_limiter.check(
            f"{'auth' if is_auth else 'api'}:{client_key}",
            limit=rate_limit,
        )
        if not decision.allowed:
            self.metrics.rejected("rate_limit")
            await self._error(
                scope,
                receive,
                send,
                status_code=429,
                code="rate_limit_exceeded",
                message="Too many requests; retry after the indicated delay",
                request_id=request_id,
                started_at=started_at,
                extra_headers={"Retry-After": str(decision.retry_after)},
            )
            return

        if not self.admission.acquire():
            self.metrics.rejected("capacity")
            await self._error(
                scope,
                receive,
                send,
                status_code=503,
                code="service_at_capacity",
                message="The service is at capacity; retry shortly",
                request_id=request_id,
                started_at=started_at,
                extra_headers={"Retry-After": "1"},
            )
            return

        idempotency_scope: str | None = None
        request_hash: str | None = None
        try:
            body, body_too_large = await self._read_body(receive)
            if body_too_large:
                self.metrics.rejected("payload")
                await self._error(
                    scope,
                    self._body_receiver(b""),
                    send,
                    status_code=413,
                    code="payload_too_large",
                    message="Request payload exceeds the configured limit",
                    request_id=request_id,
                    started_at=started_at,
                )
                return

            idempotency_key = headers.get("idempotency-key")
            if idempotency_key and method not in _MUTATING_METHODS:
                await self._error(
                    scope,
                    self._body_receiver(body),
                    send,
                    status_code=400,
                    code="idempotency_not_supported",
                    message="Idempotency-Key is supported only for POST, PUT, and PATCH",
                    request_id=request_id,
                    started_at=started_at,
                )
                return
            if idempotency_key and is_auth:
                await self._error(
                    scope,
                    self._body_receiver(body),
                    send,
                    status_code=400,
                    code="idempotency_not_supported",
                    message="Authentication responses cannot be replay-cached",
                    request_id=request_id,
                    started_at=started_at,
                )
                return
            if idempotency_key and not _SAFE_IDENTIFIER.fullmatch(idempotency_key):
                await self._error(
                    scope,
                    self._body_receiver(body),
                    send,
                    status_code=400,
                    code="invalid_idempotency_key",
                    message="Idempotency-Key contains unsupported characters or is too long",
                    request_id=request_id,
                    started_at=started_at,
                )
                return

            if idempotency_key:
                request_hash = hashlib.sha256(body).hexdigest()
                idempotency_scope = self._idempotency_scope(
                    method,
                    path,
                    client_key,
                    idempotency_key,
                )
                state, stored = self.idempotency.begin(
                    idempotency_scope,
                    request_hash,
                )
                if state == "replay" and stored:
                    self.metrics.replayed()
                    await self._replay(
                        scope,
                        receive,
                        send,
                        stored,
                        request_id=request_id,
                        started_at=started_at,
                    )
                    return
                if state in {"conflict", "inflight"}:
                    await self._error(
                        scope,
                        self._body_receiver(body),
                        send,
                        status_code=409,
                        code=(
                            "idempotency_conflict"
                            if state == "conflict"
                            else "idempotency_in_progress"
                        ),
                        message=(
                            "Idempotency-Key was reused with different request content"
                            if state == "conflict"
                            else "An identical request is already in progress"
                        ),
                        request_id=request_id,
                        started_at=started_at,
                    )
                    return

            await self._dispatch(
                scope,
                self._body_receiver(body),
                send,
                request_id=request_id,
                rate_decision=decision,
                started_at=started_at,
                idempotency_scope=idempotency_scope,
                request_hash=request_hash,
            )
        except Exception:
            if idempotency_scope:
                self.idempotency.abandon(idempotency_scope)
            logger.exception("Unhandled request failure", extra={"request_id": request_id})
            self.metrics.rejected("unhandled")
            await self._error(
                scope,
                self._body_receiver(b""),
                send,
                status_code=500,
                code="internal_error",
                message="The service could not complete the request",
                request_id=request_id,
                started_at=started_at,
            )
        finally:
            self.admission.release()

    async def _dispatch(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        request_id: str,
        rate_decision: RateDecision,
        started_at: float,
        idempotency_scope: str | None,
        request_hash: str | None,
    ) -> None:
        response_start: Message | None = None
        response_chunks: list[bytes] = []
        status_code = 500

        async def guarded_send(message: Message) -> None:
            nonlocal response_start, status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                self._set_response_headers(
                    message,
                    scope=scope,
                    request_id=request_id,
                    rate_decision=rate_decision,
                )
                if idempotency_scope:
                    response_start = message
                    return
            elif message["type"] == "http.response.body" and idempotency_scope:
                response_chunks.append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                return
            await send(message)

        await self.app(scope, receive, guarded_send)
        duration_ms = (time.perf_counter() - started_at) * 1000
        route = self._route_name(scope)
        self.metrics.complete(
            method=scope["method"],
            route=route,
            status_code=status_code,
            duration_ms=duration_ms,
        )

        if idempotency_scope and request_hash and response_start:
            response_body = b"".join(response_chunks)
            if status_code < 500:
                self.idempotency.complete(
                    idempotency_scope,
                    request_hash,
                    status_code=status_code,
                    headers=list(response_start.get("headers", [])),
                    body=response_body,
                )
            else:
                self.idempotency.abandon(idempotency_scope)
            await send(response_start)
            await send(
                {
                    "type": "http.response.body",
                    "body": response_body,
                    "more_body": False,
                }
            )

    async def _read_body(self, receive: Receive) -> tuple[bytes, bool]:
        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.settings.max_request_bytes:
                return b"", True
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        return b"".join(chunks), False

    @staticmethod
    def _body_receiver(body: bytes) -> Receive:
        sent = False

        async def receive() -> Message:
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        return receive

    async def _error(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        code: str,
        message: str,
        request_id: str,
        started_at: float,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": None,
                    "request_id": request_id,
                }
            },
            separators=(",", ":"),
        ).encode()
        response_headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ]
        for name, value in (extra_headers or {}).items():
            response_headers.append((name.lower().encode(), value.encode()))
        start: Message = {
            "type": "http.response.start",
            "status": status_code,
            "headers": response_headers,
        }
        self._set_response_headers(
            start,
            scope=scope,
            request_id=request_id,
            rate_decision=None,
        )
        await send(start)
        await send({"type": "http.response.body", "body": body, "more_body": False})
        self.metrics.complete(
            method=scope["method"],
            route=scope["path"],
            status_code=status_code,
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )

    async def _replay(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        stored: StoredResponse,
        *,
        request_id: str,
        started_at: float,
    ) -> None:
        del receive
        headers = [
            (name, value)
            for name, value in stored.headers
            if name.lower() not in {b"x-request-id", b"content-length"}
        ]
        headers.extend(
            [
                (b"x-request-id", request_id.encode()),
                (b"x-idempotent-replay", b"true"),
                (b"content-length", str(len(stored.body)).encode()),
            ]
        )
        await send(
            {
                "type": "http.response.start",
                "status": stored.status_code,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": stored.body,
                "more_body": False,
            }
        )
        self.metrics.complete(
            method=scope["method"],
            route=self._route_name(scope),
            status_code=stored.status_code,
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )

    def _set_response_headers(
        self,
        message: Message,
        *,
        scope: Scope,
        request_id: str,
        rate_decision: RateDecision | None,
    ) -> None:
        headers = MutableHeaders(scope=message)
        headers["X-Request-ID"] = request_id
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["Referrer-Policy"] = "no-referrer"
        headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
            "form-action 'self'"
        )
        if scope["path"].startswith(
            (f"{self.settings.api_prefix}/auth", f"{self.settings.api_prefix}/admin")
        ):
            headers["Cache-Control"] = "no-store"
        if self.settings.environment in {"staging", "production"}:
            headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        if rate_decision:
            headers["X-RateLimit-Limit"] = str(rate_decision.limit)
            headers["X-RateLimit-Remaining"] = str(rate_decision.remaining)

    @staticmethod
    def _route_name(scope: Scope) -> str:
        route: Any = scope.get("route")
        route_path = getattr(route, "path", None)
        return str(route_path or scope["path"])

    @staticmethod
    def _client_key(scope: Scope, headers: Headers) -> str:
        authorization = headers.get("authorization")
        if authorization:
            return hashlib.sha256(authorization.encode()).hexdigest()[:24]
        client = scope.get("client")
        return str(client[0] if client else "unknown")

    @staticmethod
    def _idempotency_scope(
        method: str,
        path: str,
        client_key: str,
        idempotency_key: str,
    ) -> str:
        raw = f"{client_key}:{method}:{path}:{idempotency_key}"
        return hashlib.sha256(raw.encode()).hexdigest()
