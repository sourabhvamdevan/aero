import { useEffect, useState } from "react";
import {
  ComposedChart, Area, Line, BarChart, Bar, LineChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const get = (url) => fetch(url).then((r) => { if (!r.ok) throw new Error(url); return r.json(); });
const mw = (x) => (x == null ? "–" : Math.round(x).toLocaleString() + " MW");
const hhmm = (iso) => iso.slice(11, 16);
const stamp = (iso) => (iso ? iso.slice(0, 10) + " " + iso.slice(11, 16) + " UK" : "–");

function Kpi({ label, value }) {
  return <div className="kpi"><div className="v">{value}</div><div className="l">{label}</div></div>;
}

export default function App() {
  const [days, setDays] = useState([]);
  const [date, setDate] = useState("");
  const [hour, setHour] = useState(9);
  const [day, setDay] = useState(null);
  const [sum, setSum] = useState(null);
  const [hor, setHor] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    get("/api/config").then((c) => { setDays(c.delivery_days); setDate(c.delivery_days[13]); setHour(c.default_decision_hour); })
      .catch(() => setErr("Cannot reach the API"));
    get("/api/horizon").then(setHor).catch(() => {});
  }, []);

  useEffect(() => {
    if (!date) return;
    get(`/api/day?date=${date}&decision_hour=${hour}`).then(setDay).catch(() => setErr("Failed to load day"));
    get(`/api/summary?decision_hour=${hour}`).then(setSum).catch(() => setErr("Failed to load summary"));
  }, [date, hour]);

  if (err) return <main><div className="card">{err}</div></main>;
  if (!day || !sum) return <main><div className="card">Loading…</div></main>;

  const m = day.metrics;
  const pts = day.points.map((p) => ({ ...p, t: hhmm(p.time), band: p.low == null ? null : [p.low, p.high] }));
  const [q10, q90] = day.band_p10_p90;

  return (
    <>
      <header>
        <h1>Wind Generation Forecast Accuracy</h1>
        <p>UK national wind (Elexon FUELHH actuals vs WINDFOR forecasts) · day-ahead purchase decisions, January 2026</p>
      </header>
      <main>
        <div className="controls">
          <label>Delivery day
            <select value={date} onChange={(e) => setDate(e.target.value)}>
              {days.map((d) => <option key={d}>{d}</option>)}
            </select>
          </label>
          <label>Decision made at (UK time, day before)
            <select value={hour} onChange={(e) => setHour(+e.target.value)}>
              {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}
            </select>
          </label>
        </div>

        <div className="banner">
          At <b>{stamp(day.decision_time)}</b> the latest available wind forecast for <b>{day.date}</b> was published
          at <b>{stamp(day.forecast_published_max)}</b>. It expects <b>{day.forecast_mwh ? Math.round(day.forecast_mwh).toLocaleString() : "–"} MWh</b> of
          wind. Historically (this month) the real output landed between <b>{mw(-q90)}</b> and <b>{mw(-q10)}</b> relative
          to the forecast about 80% of the time — plan your thermal buying with that range in mind.
        </div>

        <div className="kpis">
          <Kpi label="Forecast energy (MWh)" value={day.forecast_mwh ? Math.round(day.forecast_mwh).toLocaleString() : "–"} />
          <Kpi label="Actual energy (MWh)" value={day.actual_mwh ? Math.round(day.actual_mwh).toLocaleString() : "–"} />
          <Kpi label="MAE (this day)" value={mw(m.mae)} />
          <Kpi label="RMSE (this day)" value={mw(m.rmse)} />
          <Kpi label="Bias (+ = over-forecast)" value={mw(m.bias)} />
          <Kpi label="MAE (whole month)" value={mw(sum.overall.mae)} />
        </div>

        <div className="card">
          <h2>Actual vs forecast – {day.date}</h2>
          <p className="muted">Shaded band = 10th–90th percentile of this month's forecast errors applied to the forecast.</p>
          <ResponsiveContainer width="100%" height={340}>
            <ComposedChart data={pts}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="t" interval={3} />
              <YAxis unit=" MW" width={80} />
              <Tooltip formatter={(v) => (Array.isArray(v) ? v.map(Math.round).join(" – ") : Math.round(v))} />
              <Legend />
              <Area dataKey="band" name="Likely range" stroke="none" fill="#9ecae1" fillOpacity={0.45} />
              <Line dataKey="forecast" name="Forecast" stroke="#1f78b4" dot={false} strokeWidth={2} />
              <Line dataKey="actual" name="Actual" stroke="#e6550d" dot={false} strokeWidth={2} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <div className="grid2">
          <div className="card">
            <h2>Daily MAE across January</h2>
            <p className="muted">Which delivery days were hard to forecast?</p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={sum.daily.map((d) => ({ ...d, day: d.date.slice(5) }))}>
                <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="day" interval={4} /><YAxis width={60} />
                <Tooltip formatter={(v) => Math.round(v) + " MW"} />
                <Bar dataKey="mae" name="MAE" fill="#1f78b4" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="card">
            <h2>MAE by hour of delivery day</h2>
            <p className="muted">Which parts of the day are riskiest?</p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={sum.by_hour_of_day}>
                <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="hour" /><YAxis width={60} />
                <Tooltip formatter={(v) => Math.round(v) + " MW"} />
                <Bar dataKey="mae" name="MAE" fill="#31a354" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h2>Accuracy vs forecast horizon</h2>
          <p className="muted">Error of every forecast by how many hours before delivery it was published — shows the value of waiting for a fresher forecast.</p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={hor}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="horizon_h" label={{ value: "hours ahead", position: "insideBottom", offset: -2 }} />
              <YAxis width={60} />
              <Tooltip formatter={(v) => Math.round(v) + " MW"} />
              <Legend />
              <Line dataKey="mae" name="MAE" stroke="#1f78b4" dot={false} strokeWidth={2} />
              <Line dataKey="rmse" name="RMSE" stroke="#e6550d" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </main>
    </>
  );
}
