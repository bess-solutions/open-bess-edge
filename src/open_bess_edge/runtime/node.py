"""Nodo orquestador: lazo de control determinista con máquina de estados y fail-safe.

Ciclo::

    poll_connection -> read_telemetry -> SafetyEnvelope -> FFR/droop -> Volt/VAR
        -> limitador -> write_setpoints (+verificación) -> heartbeat -> auditoría

Garantías de fail-safe (probadas en ``tests/``):

* Pérdida de telemetría: se retiene la última consigna ``comm_loss_hold_s`` y
  luego se fuerza 0 kW/0 kvar (``SAFE_STATE``), reintentando la escritura de 0
  en cada ciclo hasta confirmarla.
* Dato requerido inválido (NaN, fuera de rango físico, ausente): salida 0.
* Disparo de seguridad: salida 0 enclavada hasta ``request_reset`` válido.
* Fallos de escritura repetidos: ``SAFE_STATE``.
* Arranque: salida 0 hasta ``startup_valid_cycles`` ciclos consecutivos válidos.
* Parada (SIGTERM o excepción interna): se escribe 0 antes de cerrar.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from ..config import EdgeConfig, ReactiveMode
from ..control.ffr_droop import FFRDroopController
from ..control.limiter import apply_limits
from ..control.volt_var import VoltVarController
from ..errors import ConfigError, PlantCommError, PlantDataError
from ..modbus.driver import ModbusPlant
from ..models import Command, NodeState, SafetyVerdict, Severity, Telemetry
from ..safety.envelope import SafetyEnvelope
from .audit import AuditLog
from .clock import SystemClock

log = logging.getLogger("open_bess_edge.node")


@dataclass
class CycleResult:
    state: str
    status: str
    t_mono: float
    f_hz: Optional[float] = None
    v_v: Optional[float] = None
    p_measured_kw: Optional[float] = None
    p_setpoint_kw: float = 0.0
    q_setpoint_kvar: float = 0.0
    ffr_status: str = ""
    is_ffr_emergency: bool = False
    safety_status: str = ""
    faults: tuple[str, ...] = ()
    commit_ok: Optional[bool] = None
    verified: Optional[bool] = None
    latency_ms: float = 0.0            # edad de la muestra de frecuencia al terminar la escritura
    cycle_ms: float = 0.0


@dataclass
class Metrics:
    cycles: int = 0
    overruns: int = 0
    comm_errors: int = 0
    write_failures: int = 0
    verify_mismatches: int = 0
    trips: int = 0
    safe_state_entries: int = 0
    internal_errors: int = 0
    ffr_budget_exceeded: int = 0
    latency_ms_max: float = 0.0
    latency_ms_last: float = 0.0
    latencies: list[float] = field(default_factory=list)   # ventana de las últimas muestras (ms)

    def record_latency(self, ms: float) -> None:
        self.latency_ms_last = ms
        self.latency_ms_max = max(self.latency_ms_max, ms)
        self.latencies.append(ms)
        if len(self.latencies) > 2000:
            del self.latencies[:1000]

    def percentile(self, q: float) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        return float(s[min(len(s) - 1, int(q * len(s)))])


class EdgeNode:
    def __init__(self, cfg: EdgeConfig, plant: ModbusPlant, *, clock: Any = None, audit: Optional[AuditLog] = None) -> None:
        self.cfg = cfg
        self.plant = plant
        self.clock = clock or SystemClock()
        self.audit = audit or AuditLog(cfg.audit.path, cfg.audit.max_bytes, cfg.audit.backups)
        self.metrics = Metrics()
        self.state = NodeState.INIT
        self.safety = SafetyEnvelope(cfg.safety.limits, cfg.plant, cfg.grid.f_nominal_hz)
        f = cfg.ffr
        self.ffr = FFRDroopController(
            p_nominal_kw=cfg.plant.p_nominal_kw, f_nominal_hz=cfg.grid.f_nominal_hz, droop_r=f.droop_r,
            deadband_hz=f.deadband_hz, contingency_threshold_hz=f.contingency_threshold_hz,
            ramp_pct_per_min=f.ramp_pct_per_min, freq_invalid_hold_s=f.freq_invalid_hold_s, enabled=f.enabled,
        )
        v = cfg.volt_var
        self.vv = VoltVarController(
            mode=v.mode, q_max_kvar=v.q_max_kvar, v_nominal_v=cfg.plant.v_nominal_v,
            p_nominal_kw=cfg.plant.p_nominal_kw, s_max_kva=cfg.s_max_kva, deadband_pct=v.deadband_pct,
            slope_k_q=v.slope_k_q, fixed_q_kvar=v.fixed_q_kvar, power_factor=v.power_factor,
            pf_excitation=v.pf_excitation, cos_phi_p_curve=v.cos_phi_p_curve,
            cos_phi_p_excitation=v.cos_phi_p_excitation, invalid_hold_s=v.invalid_hold_s,
            q_ramp_kvar_per_s=v.q_ramp_kvar_per_s,
        )
        self.control_enabled = False
        self._stop = asyncio.Event()
        self._last_good: Optional[float] = None
        self._last_tel: Optional[Telemetry] = None
        self._valid_streak = 0
        self._write_failures = 0
        self._last_cmd = Command(0.0, 0.0)
        self._zero_confirmed = False
        self._fault_codes: tuple[str, ...] = ()
        self._dispatch_p = cfg.dispatch.p_base_kw
        self._dispatch_t: Optional[float] = None
        self._track_since: Optional[float] = None
        self._track_alarm = False
        self._last_sp_log_t = -1e18
        self._last_sp_logged = 0.0
        self._consec_internal = 0
        self.last_cycle_mono: Optional[float] = None
        self.last_result: Optional[CycleResult] = None

    # ------------------------------------------------------------------
    # Arranque / parada
    # ------------------------------------------------------------------
    def _validate_capabilities(self) -> None:
        cfg, prof = self.cfg, self.plant.profile
        req = self.safety.limits.required_signals
        missing = prof.missing_signals(req)
        monitor = cfg.runtime.monitor_only
        if not monitor:
            if not prof.can_control_p:
                raise ConfigError(
                    f"el perfil '{prof.name}' no define consigna de P: no puede controlarse. "
                    "Use runtime.monitor_only: true o un perfil con binding p_setpoint_kw.")
            if missing:
                raise ConfigError(
                    f"el perfil '{prof.name}' no provee señales de seguridad requeridas: {missing}. "
                    "El control sin envolvente de seguridad completa está prohibido.")
            if cfg.ffr.enabled and "frequency_hz" not in prof.bindings:
                raise ConfigError("ffr.enabled requiere el binding frequency_hz en el perfil")
            v = cfg.volt_var
            if v.mode is not ReactiveMode.DISABLED:
                if not prof.can_control_q:
                    raise ConfigError(f"volt_var.mode={v.mode.value} requiere binding q_setpoint_kvar; use DISABLED")
                if v.mode is ReactiveMode.VOLT_VAR_Q_V and "v_grid_v" not in prof.bindings:
                    raise ConfigError("Q(V) requiere el binding v_grid_v en el perfil")
            self.plant.check_setpoint_range(
                max(cfg.plant.p_discharge_cap_kw, cfg.plant.p_charge_cap_kw), cfg.volt_var.q_max_kvar)
        self.control_enabled = not monitor

    async def start(self, timeout_s: float = 5.0) -> bool:
        self._validate_capabilities()
        self.audit.event("NODE_START", self.clock.wall(), device_id=self.cfg.node.device_id,
                         profile=self.plant.profile.name, verification=self.plant.profile.verification_level,
                         control=self.control_enabled)
        ok = await self.plant.connect_now(timeout_s)
        if not ok:
            self._set_state(NodeState.SAFE_STATE, "NO_CONNECTION_AT_START")
            return False
        if self.control_enabled:
            res = await self.plant.write_zero()          # arranque siempre en 0
            self._zero_confirmed = res.ok
            self._set_state(NodeState.STARTING, "STARTUP")
        else:
            self._set_state(NodeState.MONITOR_ONLY, "MONITOR_ONLY")
        return True

    def request_stop(self) -> None:
        self._stop.set()

    async def stop(self) -> None:
        self._set_state(NodeState.STOPPING, "STOP")
        if self.control_enabled and self.plant.connected:
            try:
                res = await asyncio.wait_for(self.plant.write_zero(), timeout=self.cfg.modbus.timeout_s * 2)
                self.audit.event("SHUTDOWN_ZERO", self.clock.wall(), ok=res.ok, detail=res.detail)
            except (asyncio.TimeoutError, PlantCommError) as exc:
                self.audit.event("SHUTDOWN_ZERO", self.clock.wall(), ok=False, detail=str(exc))
        await self.plant.close()
        self._set_state(NodeState.STOPPED, "STOPPED")
        self.audit.close()

    # ------------------------------------------------------------------
    # Operación
    # ------------------------------------------------------------------
    def set_dispatch(self, p_kw: float) -> None:
        """Consigna base externa (p. ej. AGC/SCADA). Expira a 0 tras ``dispatch.external_timeout_s``."""
        if not math.isfinite(p_kw):
            raise ValueError("consigna de despacho no finita")
        cap_d, cap_c = self.cfg.plant.p_discharge_cap_kw, self.cfg.plant.p_charge_cap_kw
        self._dispatch_p = max(-cap_c, min(cap_d, p_kw))
        self._dispatch_t = self.clock.mono()

    def _dispatch_now(self, now: float) -> float:
        if self._dispatch_t is not None and now - self._dispatch_t > self.cfg.dispatch.external_timeout_s:
            self._dispatch_p, self._dispatch_t = 0.0, None
            self.audit.event("DISPATCH_EXPIRED", self.clock.wall())
        return self._dispatch_p

    def request_reset(self) -> tuple[bool, str]:
        ok, msg = self.safety.reset_trips(self.clock.mono())
        self.audit.event("TRIP_RESET_REQUEST", self.clock.wall(), ok=ok, detail=msg)
        return ok, msg

    def _set_state(self, new: NodeState, why: str = "") -> None:
        if new is not self.state:
            self.audit.event("STATE", self.clock.wall(), old=self.state.value, new=new.value, why=why)
            if new is NodeState.SAFE_STATE:
                self.metrics.safe_state_entries += 1
            log.info("estado %s -> %s (%s)", self.state.value, new.value, why)
            self.state = new

    # ------------------------------------------------------------------
    async def _write_zero_safe(self) -> bool:
        try:
            res = await self.plant.write_zero()
        except PlantCommError:
            res = None
        self._zero_confirmed = bool(res and res.ok)
        return self._zero_confirmed

    def _log_faults(self, verdict: SafetyVerdict) -> None:
        codes = tuple(f"{f.code}:{f.name}" for f in verdict.faults)
        if codes != self._fault_codes:
            raised = sorted(set(codes) - set(self._fault_codes))
            cleared = sorted(set(self._fault_codes) - set(codes))
            detail = {f"{f.code}:{f.name}": f.detail for f in verdict.faults}
            self.audit.event("FAULTS", self.clock.wall(), raised=raised, cleared=cleared,
                             detail={k: detail[k] for k in raised if k in detail})
            if any(f.severity is Severity.TRIP and f.latched and f"{f.code}:{f.name}" in raised for f in verdict.faults):
                self.metrics.trips += 1
            self._fault_codes = codes

    async def step(self) -> CycleResult:
        m = self.metrics
        t_cycle0 = self.clock.mono()
        now = t_cycle0
        m.cycles += 1
        rt = self.cfg.runtime

        connected = self.plant.poll_connection()
        tel: Optional[Telemetry] = None
        err = ""
        if connected:
            try:
                tel = await self.plant.read_telemetry()
            except PlantCommError as exc:
                err = str(exc)
        else:
            err = "sin conexión"
        if tel is not None:
            self._last_good = now
            self._last_tel = tel
        else:
            m.comm_errors += 1

        age = float("inf") if self._last_good is None else now - self._last_good
        max_age = max(rt.comm_loss_hold_s, rt.cycle_ms / 1000.0 * 3)

        # ---- pérdida de telemetría ---------------------------------------
        if tel is None:
            self._valid_streak = 0
            if (self.control_enabled and age <= rt.comm_loss_hold_s
                    and self.state in (NodeState.RUNNING, NodeState.DEGRADED)):
                self._set_state(NodeState.DEGRADED, f"TELEMETRY_LOST: {err}")
                return self._finish(CycleResult(self.state.value, "COMM_HOLD", now), t_cycle0)
            verdict = self.safety.evaluate(None, now)
            self._log_faults(verdict)
            if self.control_enabled:
                self._enter_blocked(NodeState.SAFE_STATE, "TELEMETRY_LOST_BEYOND_HOLD")
                zero_ok = await self._write_zero_safe() if connected else False
                self._last_cmd = Command(0.0, 0.0, reason="COMM_LOSS")
                res = CycleResult(self.state.value, "TELEMETRY_COMM_ERROR", now, p_setpoint_kw=0.0,
                                  safety_status=verdict.status, faults=verdict.codes, commit_ok=zero_ok)
            else:
                res = CycleResult(self.state.value, "TELEMETRY_COMM_ERROR", now, safety_status=verdict.status,
                                  faults=verdict.codes)
            return self._finish(res, t_cycle0)

        # ---- seguridad ---------------------------------------------------
        verdict = self.safety.evaluate(tel, now, max_age_s=max_age)
        self._log_faults(verdict)

        if not self.control_enabled:
            res = CycleResult(NodeState.MONITOR_ONLY.value, "MONITOR", now, f_hz=tel.frequency_hz, v_v=tel.v_grid_v,
                              p_measured_kw=tel.p_kw, safety_status=verdict.status, faults=verdict.codes)
            return self._finish(res, t_cycle0)

        if not verdict.allow_output:
            self._valid_streak = 0
            new = NodeState.TRIPPED if verdict.tripped else NodeState.SAFE_STATE
            self._enter_blocked(new, "TRIP" if verdict.tripped else "DATA_FAULT")
            zero_ok = await self._write_zero_safe()
            self._last_cmd = Command(0.0, 0.0, reason="SAFETY_INTERLOCK")
            status = "SAFETY_TRIP_INTERLOCK" if verdict.tripped else "SAFETY_DATA_INTERLOCK"
            res = CycleResult(self.state.value, status, now, f_hz=tel.frequency_hz, v_v=tel.v_grid_v,
                              p_measured_kw=tel.p_kw, safety_status=verdict.status, faults=verdict.codes,
                              commit_ok=zero_ok)
            return self._finish(res, t_cycle0)

        # ---- salida de estados bloqueados / arranque ---------------------
        self._valid_streak += 1
        if self.state is NodeState.DEGRADED:
            self._set_state(NodeState.RUNNING, "TELEMETRY_RESTORED")   # microcorte dentro de la ventana de retención
        elif self.state in (NodeState.STARTING, NodeState.SAFE_STATE, NodeState.TRIPPED, NodeState.INIT):
            need = rt.startup_valid_cycles
            if self._valid_streak < need or not self._zero_confirmed:
                if not self._zero_confirmed:
                    await self._write_zero_safe()
                res = CycleResult(self.state.value, "STARTUP_VALIDATING", now, f_hz=tel.frequency_hz,
                                  v_v=tel.v_grid_v, p_measured_kw=tel.p_kw, safety_status=verdict.status,
                                  faults=verdict.codes, commit_ok=self._zero_confirmed)
                return self._finish(res, t_cycle0)
            self.ffr.reset(0.0)
            self.vv.reset()
            self._set_state(NodeState.RUNNING, "VALIDATED")

        # ---- control -----------------------------------------------------
        wall = self.clock.wall()
        p_base = self._dispatch_now(now)
        ffr = self.ffr.update(now, tel.frequency_hz, p_base, wall=wall)
        vv = self.vv.update(now, tel.v_grid_v, ffr.p_kw)
        cmd = apply_limits(ffr.p_kw, vv.q_kvar, verdict, s_max_kva=self.cfg.s_max_kva,
                           q_max_kvar=self.cfg.volt_var.q_max_kvar if self.plant.profile.can_control_q else 0.0)
        if not self.plant.profile.can_control_q and abs(cmd.q_kvar) > 0:
            cmd = Command(cmd.p_kw, 0.0, cmd.p_clipped, True, cmd.reason)
        self.ffr.observe_applied(cmd.p_kw)

        # ---- escritura ---------------------------------------------------
        verify = self.cfg.modbus.verify_writes and (m.cycles % self.cfg.modbus.verify_every_n_cycles == 0)
        try:
            wr = await self.plant.write_setpoints(cmd.p_kw, cmd.q_kvar, verify=verify,
                                                  tolerance_kw=self.cfg.modbus.verify_tolerance_kw)
        except (PlantCommError, PlantDataError) as exc:
            from ..models import WriteResult  # noqa: PLC0415
            wr = WriteResult(False, str(exc))
        if wr.ok:
            self._write_failures = 0
            applied = wr.extra.get("applied_p_kw")
            self._last_cmd = Command(applied if applied is not None else cmd.p_kw,
                                     cmd.q_kvar, cmd.p_clipped, cmd.q_clipped, cmd.reason)
            self._zero_confirmed = cmd.p_kw == 0.0 and cmd.q_kvar == 0.0
            await self.plant.heartbeat()
        else:
            self._write_failures += 1
            m.write_failures += 1
            if wr.verified is False:
                m.verify_mismatches += 1
            self.audit.event("WRITE_FAILURE", wall, detail=wr.detail, consecutive=self._write_failures)
            self._zero_confirmed = False
            if self._write_failures >= rt.write_fail_safe_after:
                self._enter_blocked(NodeState.SAFE_STATE, "WRITE_FAILURES")
                await self._write_zero_safe()

        # ---- instrumentación FFR ----------------------------------------
        t_end = self.clock.mono()
        latency_ms = (t_end - tel.t_mono) * 1000.0
        m.record_latency(latency_ms)
        if ffr.contingency and latency_ms > rt.ffr_latency_budget_ms:
            m.ffr_budget_exceeded += 1
            self.audit.event("FFR_LATENCY_BUDGET_EXCEEDED", wall, latency_ms=round(latency_ms, 2),
                             budget_ms=rt.ffr_latency_budget_ms)
        for rec in self.ffr.pop_finished():
            self.audit.event("CONTINGENCY", wall, **rec.as_dict())
        self._track(now, tel, cmd)
        self._log_setpoint(now, wall, cmd, ffr.status)

        res = CycleResult(
            self.state.value, ("FFR_CONTINGENCY" if ffr.contingency else "OK") if wr.ok else "WRITE_FAILURE", now,
            f_hz=tel.frequency_hz, v_v=tel.v_grid_v, p_measured_kw=tel.p_kw,
            p_setpoint_kw=cmd.p_kw, q_setpoint_kvar=cmd.q_kvar, ffr_status=ffr.status,
            is_ffr_emergency=ffr.contingency, safety_status=verdict.status, faults=verdict.codes,
            commit_ok=wr.ok, verified=wr.verified, latency_ms=latency_ms,
        )
        return self._finish(res, t_cycle0)

    # ------------------------------------------------------------------
    def _enter_blocked(self, new: NodeState, why: str) -> None:
        if self.state not in (NodeState.SAFE_STATE, NodeState.TRIPPED) or self.state is not new:
            self.ffr.reset(0.0)
            self.vv.reset()
            self._zero_confirmed = False
        self._set_state(new, why)

    def _track(self, now: float, tel: Telemetry, cmd: Command) -> None:
        if tel.p_kw is None:
            return
        tol = self.cfg.runtime.tracking_tolerance_pct / 100.0 * self.cfg.plant.p_nominal_kw
        # Tolerancia sólo tras un tiempo de asentamiento razonable (primer orden del PCS).
        if abs(tel.p_kw - cmd.p_kw) > tol:
            if self._track_since is None:
                self._track_since = now
            elif not self._track_alarm and now - self._track_since >= self.cfg.runtime.tracking_alarm_s:
                self._track_alarm = True
                self.audit.event("PCS_NOT_TRACKING", self.clock.wall(), p_measured=tel.p_kw, p_setpoint=cmd.p_kw)
        else:
            if self._track_alarm:
                self.audit.event("PCS_TRACKING_RECOVERED", self.clock.wall())
            self._track_since, self._track_alarm = None, False

    def _log_setpoint(self, now: float, wall: float, cmd: Command, ffr_status: str) -> None:
        a = self.cfg.audit
        if (abs(cmd.p_kw - self._last_sp_logged) >= max(a.setpoint_log_delta_kw, 1e-9)
                and now - self._last_sp_log_t >= 1.0) or now - self._last_sp_log_t >= a.setpoint_log_interval_s:
            self.audit.event("SETPOINT", wall, p_kw=round(cmd.p_kw, 3), q_kvar=round(cmd.q_kvar, 3),
                             ffr=ffr_status, reason=cmd.reason)
            self._last_sp_log_t, self._last_sp_logged = now, cmd.p_kw

    def _finish(self, res: CycleResult, t0: float) -> CycleResult:
        res.cycle_ms = (self.clock.mono() - t0) * 1000.0
        self.last_cycle_mono = self.clock.mono()
        self.last_result = res
        return res

    # ------------------------------------------------------------------
    async def run(self) -> None:
        period = self.cfg.runtime.cycle_ms / 1000.0
        nxt = self.clock.mono()
        while not self._stop.is_set():
            try:
                await self.step()
                self._consec_internal = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - el lazo jamás debe morir en silencio
                self.metrics.internal_errors += 1
                self._consec_internal += 1
                log.exception("error interno en el ciclo de control")
                self.audit.event("INTERNAL_ERROR", self.clock.wall(), error=repr(exc))
                self._enter_blocked(NodeState.SAFE_STATE, "INTERNAL_ERROR")
                with contextlib.suppress(Exception):
                    await self._write_zero_safe()
                if self._consec_internal >= 50:
                    log.critical("50 errores internos consecutivos: se detiene el nodo")
                    break
            nxt += period
            now = self.clock.mono()
            if now > nxt:
                self.metrics.overruns += 1
                nxt = now
            await self.clock.sleep(nxt - now)
