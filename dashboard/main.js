/**
 * BESSAI Edge Gateway — Dashboard Client
 * Polls the DashboardAPI REST endpoints and renders live data.
 *
 * API consumed (from dashboard_api.py):
 *   GET /api/v1/status    → telemetry, IDS, ONNX
 *   GET /api/v1/fleet     → fleet KPIs
 *   GET /api/v1/carbon    → CO₂ avoided
 *   GET /api/v1/p2p       → P2P credits
 *   GET /api/v1/schedule  → Arbitrage schedule
 *   GET /api/v1/version   → version info
 *
 * Config: window.BESSAI_API_URL (default: same-origin :8080)
 */

'use strict';

// ─── Config ────────────────────────────────────────────────────────────────
const API_BASE = (window.BESSAI_API_URL || 'http://localhost:8080') + '/api/v1';
const POLL_INTERVAL_MS   = 3000;   // Main telemetry poll
const SCHEDULE_INTERVAL  = 60000;  // Arbitrage schedule (1 min)
const CHART_MAX_POINTS   = 120;    // 6 min @ 3s

// ─── State ──────────────────────────────────────────────────────────────────
const state = {
  connected: false,
  apiKey: localStorage.getItem('bessai_api_key') || '',
  alerts: [],
  chartSoc: [],
  chartPower: [],
  chartLabels: [],
};

// ─── Chart.js setup ─────────────────────────────────────────────────────────
let mainChart = null;

function initChart() {
  const ctx = document.getElementById('chart-main').getContext('2d');
  mainChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'SOC (%)',
          data: [],
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99,102,241,.08)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 0,
          yAxisID: 'y',
        },
        {
          label: 'Potencia (kW)',
          data: [],
          borderColor: '#22d3ee',
          backgroundColor: 'rgba(34,211,238,.05)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 0,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { display: false }, tooltip: {
        backgroundColor: 'rgba(13,22,37,.95)',
        borderColor: '#1e2d42',
        borderWidth: 1,
        titleColor: '#e2e8f0',
        bodyColor: '#7a95b0',
      }},
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,.04)' },
          ticks: { color: '#4a6580', maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
        },
        y: {
          position: 'left',
          grid: { color: 'rgba(255,255,255,.04)' },
          ticks: { color: '#6366f1', callback: v => v + '%' },
          min: 0, max: 100,
        },
        y1: {
          position: 'right',
          grid: { display: false },
          ticks: { color: '#22d3ee', callback: v => v + ' kW' },
        },
      },
    },
  });
}

function pushChartPoint(soc, power) {
  const now = new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  state.chartLabels.push(now);
  state.chartSoc.push(soc);
  state.chartPower.push(power);
  if (state.chartLabels.length > CHART_MAX_POINTS) {
    state.chartLabels.shift();
    state.chartSoc.shift();
    state.chartPower.shift();
  }
  mainChart.data.labels = [...state.chartLabels];
  mainChart.data.datasets[0].data = [...state.chartSoc];
  mainChart.data.datasets[1].data = [...state.chartPower];
  mainChart.update('none');
}

// ─── API helpers ─────────────────────────────────────────────────────────────
async function apiFetch(endpoint) {
  const headers = {};
  if (state.apiKey) headers['Authorization'] = `Bearer ${state.apiKey}`;
  const res = await fetch(`${API_BASE}${endpoint}`, { headers });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function setConnected(online) {
  state.connected = online;
  const dot = document.getElementById('conn-dot');
  const label = document.getElementById('conn-label');
  dot.className = 'conn-dot ' + (online ? 'online' : 'offline');
  label.textContent = online ? 'Online' : 'Offline';
}

// ─── Gauge renderer ───────────────────────────────────────────────────────────
function renderSocGauge(soc) {
  const fill = document.getElementById('gauge-fill');
  const valueEl = document.getElementById('soc-value');
  const statusEl = document.getElementById('soc-status');

  // Arc total length ≈ 251px (180° semicircle r=80)
  const total = 251;
  const filled = (soc / 100) * total;
  fill.setAttribute('stroke-dasharray', `${filled} ${total - filled}`);

  valueEl.textContent = soc.toFixed(1);

  // Color coding
  let color = '#22c55e', statusText = 'NOMINAL', statusBg = 'rgba(34,197,94,.1)';
  if (soc < 10) { color = '#ef4444'; statusText = 'CRÍTICO'; statusBg = 'rgba(239,68,68,.1)'; }
  else if (soc < 20) { color = '#f59e0b'; statusText = 'BAJO'; statusBg = 'rgba(245,158,11,.1)'; }
  else if (soc > 95) { color = '#06b6d4'; statusText = 'LLENO'; statusBg = 'rgba(6,182,212,.1)'; }

  fill.setAttribute('stroke', color);
  valueEl.style.color = color;
  statusEl.textContent = statusText;
  statusEl.style.background = statusBg;
  statusEl.style.color = color;
  statusEl.style.borderColor = color.replace(')', ',.3)').replace('rgb', 'rgba');
}

// ─── Power flow renderer ──────────────────────────────────────────────────────
function renderPowerFlow(powerKw) {
  const valEl = document.getElementById('power-value');
  const dirLabel = document.getElementById('power-dir-label');
  const arrow = document.getElementById('power-arrow');
  const line1 = document.getElementById('flow-line-1');
  const line2 = document.getElementById('flow-line-2');

  valEl.textContent = Math.abs(powerKw).toFixed(1);

  if (powerKw > 0) {
    // Discharging: BESS → Load
    dirLabel.textContent = 'Descargando → Red';
    arrow.textContent = '↗';
    valEl.style.color = '#f59e0b';
    line1.classList.remove('active');
    line2.classList.add('active');
  } else if (powerKw < 0) {
    // Charging: Grid → BESS
    dirLabel.textContent = 'Cargando ← Red';
    arrow.textContent = '↙';
    valEl.style.color = '#22c55e';
    line1.classList.add('active');
    line2.classList.remove('active');
  } else {
    dirLabel.textContent = 'En reposo';
    arrow.textContent = '·';
    valEl.style.color = '#7a95b0';
    line1.classList.remove('active');
    line2.classList.remove('active');
  }
}

// ─── IDS renderer ─────────────────────────────────────────────────────────────
function renderIds(score, alertCount, trained, onnxAvailable, onnxMs) {
  const ring = document.getElementById('ids-ring');
  const scoreEl = document.getElementById('ids-score');
  const badge = document.getElementById('ids-badge');
  const alertsEl = document.getElementById('ids-alerts');
  const trainedEl = document.getElementById('ids-trained');
  const onnxEl = document.getElementById('onnx-status');
  const onnxMsEl = document.getElementById('onnx-ms');

  // Ring: 201 total circumference
  const offset = 201 - (score * 201);
  ring.style.strokeDashoffset = offset;

  // Color by severity
  let color = '#22d3ee';
  if (score > 0.7) color = '#ef4444';
  else if (score > 0.4) color = '#f59e0b';
  ring.style.stroke = color;

  scoreEl.textContent = score.toFixed(2);
  scoreEl.style.color = color;

  badge.textContent = score > 0.7 ? '⚠ ALARMA' : 'IDS OK';
  badge.className = 'ids-status-badge' + (score > 0.7 ? ' alarm' : '');

  alertsEl.textContent = alertCount;
  trainedEl.textContent = trained ? '✓ Entrenado' : '⏳ Entrenando';
  onnxEl.textContent = onnxAvailable ? '✓ Activo' : '— Sin modelo';
  onnxMsEl.textContent = onnxMs > 0 ? `${onnxMs.toFixed(1)} ms` : '-- ms';
}

// ─── Safety renderer ──────────────────────────────────────────────────────────
function renderSafety(isSafe) {
  const icon = document.getElementById('safety-icon');
  const text = document.getElementById('safety-text');
  icon.textContent = isSafe ? '✓' : '✗';
  icon.className = 'safety-icon' + (isSafe ? '' : ' blocked');
  text.textContent = isSafe ? 'NOMINAL' : 'BLOQUEADO';
  text.className = 'safety-text' + (isSafe ? '' : ' blocked');
}

// ─── Alerts ──────────────────────────────────────────────────────────────────
function addAlert(msg, level = 'info') {
  const feed = document.getElementById('alerts-feed');
  const countEl = document.getElementById('alerts-count');

  // Remove empty placeholder
  const empty = feed.querySelector('.alert-empty');
  if (empty) empty.remove();

  const ts = new Date().toLocaleTimeString('es-CL');
  const item = document.createElement('div');
  item.className = `alert-item ${level}`;
  item.innerHTML = `<span class="alert-time">${ts}</span><span class="alert-msg">${msg}</span>`;
  feed.prepend(item);

  // Keep max 20
  const items = feed.querySelectorAll('.alert-item');
  if (items.length > 20) items[items.length - 1].remove();

  state.alerts.push({ ts, msg, level });
  countEl.textContent = Math.min(state.alerts.length, 99) + (state.alerts.length > 99 ? '+' : '');
}

// ─── Uptime formatter ─────────────────────────────────────────────────────────
function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}h ${m}m ${s}s`;
}

// ─── Main poll ───────────────────────────────────────────────────────────────
async function pollStatus() {
  try {
    const data = await apiFetch('/status');
    setConnected(true);

    // Update site badge
    document.getElementById('site-id-badge').textContent = `📍 ${data.site_id}`;

    // SOC gauge + power
    const soc = data.telemetry.soc_pct;
    const power = data.telemetry.power_kw;
    const temp = data.telemetry.temp_c;

    renderSocGauge(soc);
    renderPowerFlow(power);

    document.getElementById('temp-val').textContent = `${temp.toFixed(1)}°C`;
    document.getElementById('cycles-val').textContent = data.cycle_count;

    // Chart
    pushChartPoint(soc, power);

    // IDS + ONNX
    renderIds(
      data.ids.score,
      data.ids.alert_count,
      data.ids.trained,
      data.onnx.available,
      data.onnx.inference_ms,
    );

    // Previous IDS alert count stored?
    if (data.ids.alert_count > (window._prevAlertCount || 0)) {
      addAlert(`AI-IDS: anomalía detectada (score: ${data.ids.score.toFixed(3)})`, 'warning');
    }
    window._prevAlertCount = data.ids.alert_count;

    // Safety
    renderSafety(data.is_safe);
    if (!data.is_safe) addAlert('Safety Guard: operación BLOQUEADA por límite físico', 'critical');

    // Footer
    document.getElementById('footer-uptime').textContent = 'Uptime: ' + formatUptime(data.uptime_s);

  } catch (err) {
    setConnected(false);
    console.warn('[BESSAI] Status poll failed:', err.message);
  }
}

async function pollCarbon() {
  try {
    const d = await apiFetch('/carbon');
    document.getElementById('co2-val').textContent = d.co2_avoided_kg.toFixed(2);
    document.getElementById('trees-val').textContent = d.equivalent_trees_planted.toFixed(1);
  } catch (_) {}
}

async function pollFleet() {
  try {
    const d = await apiFetch('/fleet');
    document.getElementById('fleet-sites').textContent = d.n_sites;
    document.getElementById('fleet-soc').textContent = d.avg_soc_pct.toFixed(1) + '%';
    document.getElementById('fleet-kw').textContent = d.available_kw.toFixed(0) + ' kW';
    const alarmsEl = document.getElementById('fleet-alarms');
    alarmsEl.textContent = d.sites_in_alarm;
    alarmsEl.style.color = d.sites_in_alarm > 0 ? '#ef4444' : '#22c55e';
    if (d.sites_in_alarm > 0) addAlert(`Fleet: ${d.sites_in_alarm} sitio(s) con alarma`, 'warning');
  } catch (_) {}
}

async function pollP2P() {
  try {
    const d = await apiFetch('/p2p');
    document.getElementById('p2p-kwh').textContent = d.credits_kwh.toFixed(1);
    document.getElementById('p2p-minted').textContent = d.credits_minted;
    document.getElementById('p2p-pending').textContent = d.credits_pending;
  } catch (_) {}
}

async function loadSchedule() {
  const btn = document.getElementById('btn-schedule');
  btn.textContent = '⏳ Calculando…';
  try {
    const d = await apiFetch('/schedule');
    const net = d.best?.ganancia_neta ?? d.projected_net_clp ?? 0;
    const cH = d.n_charge_hours ?? 0;
    const dH = d.n_discharge_hours ?? 0;
    const src = d.source === 'bessai_arbitrage' ? 'Flywheel' : 'CMg EMA';
    document.getElementById('arb-net').textContent = '$' + Math.round(net).toLocaleString('es-CL');
    document.getElementById('arb-charge').textContent = cH + ' h';
    document.getElementById('arb-discharge').textContent = dH + ' h';
    document.getElementById('arb-source').textContent = src;
    addAlert(`Programa arbitraje actualizado: +$${Math.round(net).toLocaleString('es-CL')} CLP proyectado`, 'info');
  } catch (err) {
    document.getElementById('arb-net').textContent = 'API offline';
    addAlert('Error al cargar programa de arbitraje: ' + err.message, 'warning');
  } finally {
    btn.textContent = '↻ Actualizar';
  }
}

async function loadVersion() {
  try {
    const d = await apiFetch('/version');
    document.getElementById('footer-version').textContent = `v${d.version}`;
  } catch (_) {}
}

// ─── Clock ───────────────────────────────────────────────────────────────────
function startClock() {
  function tick() {
    document.getElementById('nav-time').textContent =
      new Date().toLocaleTimeString('es-CL');
  }
  tick();
  setInterval(tick, 1000);
}

// ─── Bootstrap ───────────────────────────────────────────────────────────────
window.bessai = { loadSchedule };

window.addEventListener('DOMContentLoaded', async () => {
  startClock();
  initChart();

  // Initial load
  addAlert('BESSAI Dashboard iniciado — conectando al gateway…', 'info');
  await pollStatus();
  await Promise.allSettled([pollCarbon(), pollFleet(), pollP2P(), loadVersion(), loadSchedule()]);

  // Periodic polls
  setInterval(pollStatus, POLL_INTERVAL_MS);
  setInterval(pollCarbon, 30_000);
  setInterval(pollFleet, 15_000);
  setInterval(pollP2P, 30_000);
  setInterval(loadSchedule, SCHEDULE_INTERVAL);
});
