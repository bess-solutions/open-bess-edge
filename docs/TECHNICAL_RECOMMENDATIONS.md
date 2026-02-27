# Technical Recommendations — BESSAI Edge Gateway

**Status:** Living document · Last updated: 2026-02  
**Scope:** Engineering improvements identified during production operation and code review.  
**Priority:** P1 (critical) → P3 (nice to have).

---

## REQ-001 · Local Write-Ahead Buffer for telemetry (P1)

### Problem

When the upstream MQTT broker or cloud endpoint is unavailable, telemetry data is silently dropped.
In a 200kWh BESS operating in spot arbitrage, a 5-minute data gap during a price spike can cause
revenue miscalculation and incorrect audit trails.

### Recommendation

Implement a local SQLite-based write-ahead log (WAL) in `src/interfaces/mqtt_broker.py`:

```python
# Proposed interface
class TelemetryBuffer:
    def write(self, record: TelemetryRecord) -> None: ...
    def flush(self, broker: MQTTBroker) -> int: ...    # returns flushed count
    def oldest_pending_age(self) -> timedelta: ...
```

- Buffer location: `data/telemetry_buffer.db` (configurable via `config.yaml`)
- Max size: 72h of data (configurable, default 72h × 288 pts/h = ~20k rows)
- Flush strategy: exponential backoff with max 30s interval
- Alert via Prometheus gauge `bess_buffer_pending_records` when > 1000 records

### Acceptance criteria

- No data loss during broker outage of up to 72h.
- Automatic flush on reconnection.
- `GET /health` reports buffer status.
- Tests: `tests/interfaces/test_telemetry_buffer.py` — at least 5 scenarios including graceful degradation.

### References

- BEP-0302 (Write Authority Protocol)
- `src/interfaces/mqtt_broker.py`

---

## REQ-002 · Circuit Breaker for hardware driver calls (P1)

### Problem

When hardware communication fails (dropped Modbus connection, device reboot), the gateway
currently retries indefinitely, which can cause CPU saturation and delays in safety decisions.

### Recommendation

Implement the Circuit Breaker pattern in `src/drivers/base.py`:

```python
class CircuitBreaker:
    """Half-open → open → closed state machine for hardware calls."""
    FAILURE_THRESHOLD = 5       # consecutive failures → open
    RECOVERY_TIMEOUT = 30.0     # seconds before half-open attempt
    SUCCESS_THRESHOLD = 2       # successes in half-open → closed

    def call(self, fn: Callable[[], T], fallback: T) -> T: ...
```

**State transition:**

```
CLOSED ──(5 failures)──► OPEN ──(30s timeout)──► HALF-OPEN ──(2 successes)──► CLOSED
                                                      │
                                              (1 failure)──► OPEN
```

- Metric: `bess_circuit_breaker_state{driver="modbus_tcp"}` gauge (0=closed, 1=half-open, 2=open)
- Dashboard: add panel in Grafana showing circuit state per driver
- When OPEN: `read_state()` returns the last known safe state (stale data) and logs a `WARNING`

### Acceptance criteria

- Circuit opens after 5 consecutive failures within 60s.
- Circuit attempts recovery after 30s.
- SafetyGuard falls back to conservative defaults when circuit is OPEN.
- Tests: at least 8 scenarios covering all state transitions.

### References

- Martin Fowler — Circuit Breaker pattern
- BEP-0200 (SafetyGuard)
- `src/drivers/base.py`, `src/drivers/modbus.py`

---

## REQ-003 · Dashboard API — SHAP explainability endpoint (P2)

### Problem

The `/shap/{timestamp}` endpoint is listed in the API spec but not yet implemented.
Partners and asset managers need to understand why a specific dispatch decision was made,
especially for regulatory audits and the OpenSSF explainability requirement (BEP-0301).

### Recommendation

Implement `GET /shap/{ts}` in `src/interfaces/dashboard.py`:

```python
@router.get("/shap/{ts}")
async def shap_values(ts: datetime) -> SHAPResponse:
    """Return SHAP feature importance for the dispatch decision at timestamp ts."""
```

**Response schema:**
```json
{
  "timestamp": "2026-02-01T14:35:00Z",
  "action": "CHARGE",
  "setpoint_kw": -45.0,
  "shap_values": {
    "cmg_current": 0.38,
    "soc_pct": 0.22,
    "temperature_c": 0.08,
    "hour_of_day": 0.19,
    "cmg_30d_mean": 0.13
  },
  "confidence": 0.87
}
```

- Store SHAP values in a rotating in-memory ring buffer (last 24h × 288 pts = 6912 entries)
- Persist to `data/shap_log.parquet` daily (pruned to 30 days)
- SHAP computation adds < 2ms overhead per inference step (pre-computed, not on-demand)

### Acceptance criteria

- `GET /shap/{ts}` returns 200 with correct structure for any timestamp in the last 24h.
- Returns 404 for timestamps outside the buffer window.
- Response time < 50ms.
- Unit tests covering: valid ts, out-of-range ts, malformed ts.

### References

- BEP-0301 (Explainability Protocol)
- Lundberg & Lee (2017) — SHAP Unified Approach
- `src/agents/drl_agent.py`

---

## REQ-004 · Dashboard UI — Real-time WebSocket feed (P2)

### Problem

The current dashboard API is REST-only (polling). For real-time monitoring on the field,
operators need a push-based WebSocket feed for SOC, power, and CMg updates every 5 seconds.

### Recommendation

Add a WebSocket endpoint to `src/interfaces/dashboard.py`:

```python
@router.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket):
    """Push telemetry every 5s to connected clients."""
```

**Message format:**
```json
{
  "ts": "2026-02-01T14:35:00Z",
  "soc_pct": 67.2,
  "power_kw": -45.5,
  "cmg_clp_kwh": 87.3,
  "temperature_c": 28.4,
  "agent": "DRL",
  "safety_status": "OK"
}
```

- Max concurrent connections: 50 (configurable)
- Heartbeat ping every 30s
- Backpressure: drop messages if consumer is slow (log warning)
- Authentication: Bearer token via sec-websocket-protocol header

### Acceptance criteria

- WebSocket delivers messages within 100ms of the 5s telemetry cycle.
- Graceful disconnection handled (no server crash).
- Load test: 50 concurrent clients at 5s cadence for 60s — no message loss > 1%.
- Unit test using `websockets` test client.

### References

- FastAPI WebSocket docs
- `src/interfaces/dashboard.py`

---

## REQ-005 · Fleet manager — multi-site aggregation (P3)

### Problem

`src/core/fleet.py` has the skeleton for multi-BESS coordination but the aggregation
logic (averaging setpoints, rolling-up SOC, consolidating metrics) is not implemented.

### Recommendation

Implement `FleetOrchestrator.aggregate_setpoints()` in `src/core/fleet.py`:

```python
def aggregate_setpoints(
    self,
    sites: list[SiteState],
    market_signal: MarketSignal,
) -> dict[str, float]:
    """Return per-site setpoints optimizing fleet-level revenue."""
```

**Algorithm (initial):** proportional allocation based on available capacity.
**Phase 2:** MILP optimization across sites (BEP-0400 draft).

### Acceptance criteria

- `FleetOrchestrator` correctly allocates setpoints for 2–5 sites.
- Total fleet setpoint never exceeds the sum of individual limits.
- SafetyGuard applied per-site before dispatch.
- At least 10 unit tests including edge cases (1 site offline, all sites at min SOC).

### References

- BEP-0400 (Fleet Coordination — draft)
- `src/core/fleet.py`

---

## Implementation Priority

| ID | Title | Priority | Effort | Status |
|---|---|---|---|---|
| REQ-001 | Local Write-Ahead Buffer | P1 | ~16h | Open |
| REQ-002 | Circuit Breaker for drivers | P1 | ~12h | Open |
| REQ-003 | SHAP /shap/{ts} endpoint | P2 | ~8h | Open |
| REQ-004 | WebSocket telemetry feed | P2 | ~12h | Open |
| REQ-005 | Fleet multi-site aggregation | P3 | ~24h | Open |

> To claim any of these, open a GitHub Issue referencing this document and the REQ ID, then follow the contribution process in [CONTRIBUTING.md](../CONTRIBUTING.md).
