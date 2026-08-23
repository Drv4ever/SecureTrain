import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Bandit, Overview, Response, Tactic } from "../api";

const TACTIC_COLORS: Record<Tactic, string> = {
  urgency: "#e29b2f",
  authority: "#c96b58",
  invoice: "#6f9e63",
  credential: "#7a86b8",
};

const RESPONSE_COLORS: Record<Response, string> = {
  ignore: "#d7cdb8",
  report: "#6f9e63",
  click: "#e29b2f",
  credentials: "#c96b58",
};

const axis = { stroke: "#b7af9f", fontSize: 11 };
const tooltipStyle = {
  border: "1px solid #ece5d7",
  borderRadius: 8,
  fontSize: 12,
  background: "#fff",
};

/** TS vs random cumulative reward (from /analytics/overview). */
export function RewardCurve({ overview }: { overview: Overview }) {
  const length = Math.max(
    ...Object.values(overview.selectors).map((s) => s.curve.length),
    1,
  );
  const data = Array.from({ length }, (_, i) => {
    const row: Record<string, number> = { round: i + 1 };
    for (const [key, sel] of Object.entries(overview.selectors)) {
      row[key] = Math.round(sel.curve[i] ?? sel.mean_final_reward);
    }
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: -18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#ece5d7" vertical={false} />
        <XAxis dataKey="round" {...axis} />
        <YAxis {...axis} />
        <Tooltip contentStyle={tooltipStyle} />
        {Object.keys(overview.selectors).map((key, idx) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={key}
            stroke={idx === 0 ? "#cf8514" : "#b7af9f"}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Response distribution per selector. */
export function ResponseDistribution({ overview }: { overview: Overview }) {
  const responses: Response[] = ["ignore", "report", "click", "credentials"];
  const data = Object.entries(overview.selectors).map(([selector, sel]) => ({
    selector,
    ...responses.reduce((acc, r) => ({ ...acc, [r]: sel.response_counts[r] ?? 0 }), {}),
  }));

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: -22 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#ece5d7" vertical={false} />
        <XAxis dataKey="selector" {...axis} />
        <YAxis {...axis} />
        <Tooltip contentStyle={tooltipStyle} />
        {responses.map((r) => (
          <Bar key={r} dataKey={r} stackId="a" fill={RESPONSE_COLORS[r]} radius={r === "credentials" ? [4, 4, 0, 0] : 0} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Tactic selection share over time for one selector. */
export function SelectionShare({ overview, selector }: { overview: Overview; selector: string }) {
  const sel = overview.selectors[selector];
  if (!sel) return <div className="empty">no data</div>;
  const tactics = overview.tactics as Tactic[];
  const total = Object.values(sel.selection_share).reduce((a, b) => a + b, 0) || 1;
  const data = tactics.map((t) => ({
    tactic: t,
    share: Math.round(((sel.selection_share[t] ?? 0) / total) * 1000) / 10,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: -18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#ece5d7" vertical={false} />
        <XAxis dataKey="tactic" {...axis} />
        <YAxis {...axis} unit="%" />
        <Tooltip contentStyle={tooltipStyle} />
        {data.map((d) => (
          <Area
            key={d.tactic}
            dataKey="share"
            data={[d]}
            name={d.tactic}
            stackId="a"
            fill={TACTIC_COLORS[d.tactic]}
            stroke={TACTIC_COLORS[d.tactic]}
            fillOpacity={0.85}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Posterior means as simple bars. */
export function PosteriorBars({ bandit }: { bandit?: Bandit }) {
  if (!bandit) return null;
  const arms = Object.entries(bandit) as [Tactic, { alpha: number; beta: number; pulls: number }][];
  const max = Math.max(...arms.map(([, a]) => a.alpha / (a.alpha + a.beta)), 0.01);
  const lead = arms.reduce((best, [t, a]) => {
    const m = a.alpha / (a.alpha + a.beta);
    const b = bandit[best as Tactic];
    return m > (b.alpha / (b.alpha + b.beta)) ? t : best;
  }, arms[0]?.[0] ?? "urgency");

  return (
    <div className="post">
      {arms.map(([tactic, arm]) => {
        const mean = arm.alpha / (arm.alpha + arm.beta);
        return (
          <div key={tactic} className={`arm${tactic === lead ? " lead" : ""}`}>
            <div className="name">{tactic}</div>
            <div className="mean">{mean.toFixed(2)}</div>
            <div className="bar">
              <div style={{ width: `${(mean / max) * 100}%` }} />
            </div>
            <div className="hint" style={{ marginTop: 6 }}>{arm.pulls} pulls</div>
          </div>
        );
      })}
    </div>
  );
}

/** Estimated vulnerability ranking pills. */
export function VulnerabilityPills({ ranking }: { ranking?: Tactic[] }) {
  if (!ranking || ranking.length === 0) return <span className="hint">no sessions yet</span>;
  return (
    <div className="pill-row">
      {ranking.map((t, i) => (
        <span key={t} className={i === 0 ? "badge" : "badge plain"}>{i + 1}. {t}</span>
      ))}
    </div>
  );
}