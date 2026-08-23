import { useCallback, useEffect, useState } from "react";
import {
  ExperimentResult, Overview, getOverview, runExperiment,
} from "../api";
import { ResponseDistribution, RewardCurve, SelectionShare } from "../components/charts";

export default function Analytics() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [experiment, setExperiment] = useState<ExperimentResult | null>(null);
  const [employees, setEmployees] = useState(10);
  const [rounds, setRounds] = useState(150);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selectedSelector, setSelectedSelector] = useState("thompson");

  const load = useCallback(() => {
    getOverview()
      .then(setOverview)
      .catch((err) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  const handleRun = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await runExperiment({
        name: "dashboard-grid",
        employees,
        rounds,
        selectors: ["thompson", "random"],
      });
      setExperiment(result);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <h1 className="page-title">Analytics</h1>
      <p className="page-sub">
        Thompson Sampling vs random, aggregated from completed sessions in the
        live system.
      </p>

      {error && <div className="error" style={{ marginBottom: 16 }}>{error}</div>}

      {overview && (
        <>
          <div className="two-col">
            <div className="card">
              <h3>Cumulative reward — {overview.total_sessions} completed sessions</h3>
              <RewardCurve overview={overview} />
            </div>
            <div className="card">
              <h3>Response distribution by policy</h3>
              <ResponseDistribution overview={overview} />
            </div>
          </div>

          <div className="card">
            <h3>Selection share</h3>
            <div className="pill-group" style={{ marginBottom: 14 }}>
              {Object.keys(overview.selectors).map((key) => (
                <button key={key}
                  className={`pill${selectedSelector === key ? " on" : ""}`}
                  onClick={() => setSelectedSelector(key)}>
                  {key}
                </button>
              ))}
            </div>
            <SelectionShare overview={overview} selector={selectedSelector} />
          </div>
        </>
      )}

      <div className="card">
        <h3>Run a live experiment grid</h3>
        <p className="hint">
          Creates sessions across employees × policies and runs them through the
          real stack (bandit → scenario → behavior → reward). Regret is computed
          against the simulator's ground truth.
        </p>
        <div className="row">
          <label className="field" style={{ width: 130 }}>
            Employees
            <input type="number" min={1} max={100} value={employees}
              onChange={(e) => setEmployees(Number(e.target.value))} />
          </label>
          <label className="field" style={{ width: 130 }}>
            Rounds
            <input type="number" min={1} max={500} value={rounds}
              onChange={(e) => setRounds(Number(e.target.value))} />
          </label>
          <div className="spacer" />
          <button className="btn primary" onClick={handleRun} disabled={busy}>
            {busy ? "running…" : "Run grid"}
          </button>
        </div>

        {experiment && (
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>policy</th><th>mean reward</th><th>mean regret</th>
                <th>weakness discovered</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(experiment.results).map(([key, res]) => (
                <tr key={key}>
                  <td className="muted">{key}</td>
                  <td>{res.mean_reward.toFixed(1)}</td>
                  <td>{res.mean_regret.toFixed(1)}</td>
                  <td>{Math.round(res.discovery_rate * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}