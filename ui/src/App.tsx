import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea } from 'recharts';
import { Battery, Zap, DollarSign, Activity, Cpu, Radio, ShieldCheck } from 'lucide-react';
import './index.css';

// Type definitions
interface DataPoint {
  time: string;
  real: number;
  predicted: number;
  action: 'CHARGE' | 'DISCHARGE' | 'IDLE';
}

const mockData: DataPoint[] = Array.from({ length: 24 }).map((_, i) => {
  const hour = i;
  const real = hour >= 10 && hour <= 16 ? Math.max(0, 15 + Math.random() * 5 - 10) : 40 + Math.random() * 60;
  const predicted = real + (Math.random() * 10 - 5);

  let action: 'CHARGE' | 'DISCHARGE' | 'IDLE' = 'IDLE';
  if (hour >= 11 && hour <= 15) action = 'CHARGE'; // solar valley
  if (hour >= 18 && hour <= 22) action = 'DISCHARGE'; // evening peak

  return {
    time: `${hour.toString().padStart(2, '0')}:00`,
    real: Math.round(real),
    predicted: Math.round(predicted),
    action
  };
});

function App() {
  const [data] = useState<DataPoint[]>(mockData);
  const [soc, setSoc] = useState(45.2);
  const [connected] = useState(true);
  const [autoMode, setAutoMode] = useState(true);
  const [currentCmg, setCurrentCmg] = useState(42.5);

  // Mock real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      setSoc(prev => {
        const next = autoMode ? prev + (Math.random() * 0.4 - 0.2) : prev;
        return Math.min(100, Math.max(0, next));
      });
      setCurrentCmg(prev => Math.max(0, prev + (Math.random() * 4 - 2)));
    }, 2000);
    return () => clearInterval(interval);
  }, [autoMode]);

  return (
    <div className="app-container">
      <nav className="navbar">
        <div className="navbar-brand">
          <Zap size={24} />
          <span>BESSAI <span style={{ fontWeight: 300, color: 'var(--text-muted)' }}>Edge Gateway</span></span>
        </div>
        <div className="status-badge">
          <div className="status-dot"></div>
          {connected ? 'SEN API Connected' : 'Disconnected'}
        </div>
      </nav>

      <main className="main-content">
        <header className="header-section">
          <h1 className="header-title">Arbitrage Dashboard</h1>
          <p className="header-subtitle">Real-time SEN Market & Battery Telemetry</p>
        </header>

        <section className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-header">
              <DollarSign size={18} className="kpi-icon" />
              <span>Costo Marginal (CMg)</span>
            </div>
            <div className="kpi-value">
              {currentCmg.toFixed(1)} <span className="kpi-unit">CLP/kWh</span>
            </div>
            <div className={`kpi-trend ${currentCmg > 50 ? 'trend-up' : 'trend-down'}`}>
              <Activity size={14} />
              <span>{Math.abs(currentCmg - 40).toFixed(1)} vs avg</span>
            </div>
          </div>

          <div className="kpi-card">
            <div className="kpi-header">
              <Battery size={18} className="kpi-icon" />
              <span>State of Charge (SOC)</span>
            </div>
            <div className="kpi-value">
              {soc.toFixed(1)} <span className="kpi-unit">%</span>
            </div>
            <div className="kpi-trend trend-down" style={{ color: 'var(--accent-cyan)' }}>
              <Zap size={14} />
              <span>Discharging 500kW</span>
            </div>
          </div>

          <div className="kpi-card">
            <div className="kpi-header">
              <Activity size={18} className="kpi-icon" />
              <span>Daily Revenue</span>
            </div>
            <div className="kpi-value">
              $1,240 <span className="kpi-unit">USD</span>
            </div>
            <div className="kpi-trend trend-up">
              <span>+14.2% optimized vs manual</span>
            </div>
          </div>
        </section>

        <div className="dashboard-grid">
          <section className="panel">
            <div className="panel-header">
              <h2 className="panel-title">
                <Cpu size={20} className="kpi-icon" />
                CMg Forecast vs Actual
              </h2>
            </div>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={12} tickMargin={10} />
                  <YAxis stroke="var(--text-muted)" fontSize={12} unit=" CLP" />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)', borderRadius: '8px' }}
                    itemStyle={{ fontFamily: 'var(--font-mono)' }}
                  />
                  {/* Highlight Charge Windows */}
                  {data.map((d, index) => {
                    if (d.action === 'CHARGE') {
                      return <ReferenceArea key={index} x1={d.time} x2={data[index + 1]?.time || d.time} fill="rgba(16, 185, 129, 0.1)" />;
                    }
                    if (d.action === 'DISCHARGE') {
                      return <ReferenceArea key={index} x1={d.time} x2={data[index + 1]?.time || d.time} fill="rgba(239, 68, 68, 0.1)" />;
                    }
                    return null;
                  })}
                  <Line type="monotone" dataKey="real" stroke="var(--text-main)" strokeWidth={2} dot={false} name="Real CMg" />
                  <Line type="monotone" dataKey="predicted" stroke="var(--accent-cyan)" strokeWidth={2} strokeDasharray="5 5" dot={false} name="Predicted (ONNX)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2 className="panel-title">
                <Radio size={20} className="kpi-icon" />
                Edge Gateway
              </h2>
            </div>
            <div className="control-list">
              <div className="control-item">
                <div className="control-info">
                  <span className="control-label">Autopilot Mode</span>
                  <span className="control-value" style={{ color: autoMode ? 'var(--status-green)' : 'var(--text-muted)' }}>
                    {autoMode ? 'ACTIVE' : 'MANUAL'}
                  </span>
                </div>
                <label className="switch">
                  <input type="checkbox" checked={autoMode} onChange={() => setAutoMode(!autoMode)} />
                  <span className="slider"></span>
                </label>
              </div>

              <div className="control-item">
                <div className="control-info">
                  <span className="control-label">Target Node</span>
                  <span className="control-value">Polpaico 220kV</span>
                </div>
              </div>

              <div className="control-item">
                <div className="control-info">
                  <span className="control-label">AI Model</span>
                  <span className="control-value" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <ShieldCheck size={14} color="var(--accent-violet)" />
                    ONNX Ensemble v2 (int8)
                  </span>
                </div>
              </div>

              <div className="control-item">
                <div className="control-info">
                  <span className="control-label">Inverter Protocol</span>
                  <span className="control-value">Modbus TCP (Huawei)</span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

export default App;
