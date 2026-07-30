from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Phase5Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MetricsSnapshot(Phase5Model):
    requests_total: int = 0
    requests_in_flight: int = 0
    responses_by_status: dict[str, int] = Field(default_factory=dict)
    requests_by_method: dict[str, int] = Field(default_factory=dict)
    requests_by_route: dict[str, int] = Field(default_factory=dict)
    latency_p50_ms: float = 0
    latency_p95_ms: float = 0
    idempotent_replays_total: int = 0
    rate_limited_total: int = 0
    payload_rejections_total: int = 0
    capacity_rejections_total: int = 0
    unhandled_errors_total: int = 0


class AuditVerification(Phase5Model):
    valid: bool
    checked_records: int
    first_invalid_record_id: str | None = None
    reason: str | None = None


class ComponentStatus(Phase5Model):
    name: str
    status: Literal["ready", "degraded"]
    detail: str


class OperationalStatus(Phase5Model):
    status: Literal["ready", "degraded"]
    phases: list[int]
    shared_agent_count: int
    phase4_agent_count: int
    components: list[ComponentStatus]
    audit: AuditVerification
    metrics: MetricsSnapshot


class SecurityPolicyRead(Phase5Model):
    max_request_bytes: int
    rate_limit_requests: int
    auth_rate_limit_requests: int
    rate_limit_window_seconds: int
    max_inflight_requests: int
    idempotency_ttl_seconds: int
    trusted_host_count: int
    trust_proxy_headers: bool
    production_transport_security: bool
