import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Bandit, Employee, Response, Round, Scenario, Session, Tactic,
  completeRound, getEmployee, getSession, getVulnerability, runBatch,
  runRound, startSession, warmStart, Vulnerability,
} from "../api";
import { PosteriorBars, VulnerabilityPills } from "../components/charts";
import { ScenarioCard } from "../components/ScenarioCard";
import { ActionButtons } from "../components/ActionButtons";
import { beliefSummary, responseNarration } from "../coach";

type Pill<T extends string> = { value: T; label: string };

const SOURCES: Pill<Session["behavior_source"]>[] = [
  { value: "probabilistic", label: "Probabilistic simulator" },
  { value: "classifier", label: "ML classifier" },
  { value: "human", label: "You (live demo)" },
];
const SELECTORS: Pill<Session["selector"]>[] = [
  { value: "thompson", label: "Thompson Sampling" },
  { value: "random", label: "Random" },
];

export default function Training() {
  const { employeeId } = useParams();
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [vulnerability, setVulnerability] = useState<Vulnerability | null>(null);

  const [source, setSource] = useState<Session["behavior_source"]>("probabilistic");
  const [selector, setSelector] = useState<Session["selector"]>("thompson");
  const [mode, setMode] = useState<Session["mode"]>("evaluation");
  const [nRounds, setNRounds] = useState(300);
  const [inheritPrior, setInheritPrior] = useState(false);

  const [session, setSession] = useState<Session | null>(null);
  const [priorSessionId, setPriorSessionId] = useState<string | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [pendingNo, setPendingNo] = useState<number | null>(null);
  const [bandit, setBandit] = useState<Bandit | undefined>(undefined);
  const [history, setHistory] = useState<Round[]>([]);
  const [last, setLast] = useState<{ response?: Response; rewards?: { detection: number; safety: number } } | null>(null);
  const [lastTactic, setLastTactic] = useState<Tactic | undefined>(undefined);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mountBusy = useRef(false);

  const load = useCallback((id: string) => {
    setBusy(true);
    setError("");
    getEmployee(id)
      .then((emp) => {
        setEmployee(emp);
        return getVulnerability(id).catch(() => null);
      })
      .then((vuln) => setVulnerability(vuln))
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => {
    if (!employeeId || mountBusy.current) return;
    mountBusy.current = true;
    load(employeeId);
  }, [employeeId, load]);

  const refresh = useCallback(async (sessionId: string) => {
    const detail = await getSession(sessionId);
    setHistory(detail.rounds);
    const lastRound = detail.rounds[detail.rounds.length - 1];
    if (lastRound?.bandit_after) setBandit(lastRound.bandit_after);
    setSession(detail.session);
  }, []);

  const handleStart = async () => {
    if (!employee) return;
    setBusy(true);
    setError("");
    try {
      let inherit: string | undefined;
      if (source === "human" && inheritPrior) {
        if (!priorSessionId) {
          const warm = await warmStart(employee._id, 50);
          setPriorSessionId(warm.session._id);
          inherit = warm.session._id;
        } else {
          inherit = priorSessionId;
        }
      }
      const created = await startSession({
        employee_id: employee._id,
        selector,
        behavior_source: source,
        mode,
        n_rounds: nRounds,
        inherit_bandit_from: inherit,
      });
      setSession(created);
      setScenario(null);
      setPendingNo(null);
      setBandit(undefined);
      setHistory([]);
      setLast(null);
      const detail = await getSession(created._id);
      setHistory(detail.rounds);
      const vuln = await getVulnerability(employee._id).catch(() => null);
      setVulnerability(vuln);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleWarmPrior = async () => {
    if (!employee) return;
    setBusy(true);
    setError("");
    try {
      const warm = await warmStart(employee._id, 50);
      setPriorSessionId(warm.session._id);
      await refresh(warm.session._id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleNext = async () => {
    if (!session) return;
    setBusy(true);
    setError("");
    try {
      const result = await runRound(session._id, false);
      setScenario(result.scenario ?? null);
      setLast(result.rewards ? { response: result.response, rewards: result.rewards } : null);
      setLastTactic(result.round.tactic_selected);
      if (result.round.bandit_after) setBandit(result.round.bandit_after);
      setPendingNo(result.round.status === "pending_human" ? result.round.round_no : null);
      await refresh(session._id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleBatch = async (rounds: number) => {
    if (!session) return;
    setBusy(true);
    setError("");
    try {
      const result = await runBatch(session._id, rounds);
      setLast({});
      await refresh(session._id);
      const vuln = await getVulnerability(employee!._id).catch(() => null);
      setVulnerability(vuln);
      return result;
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleResponse = async (response: Response) => {
    if (!session || pendingNo === null) return;
    setBusy(true);
    setError("");
    try {
      const round = await completeRound(session._id, pendingNo, response);
      setLast({ response, rewards: round.reward ?? undefined });
      setLastTactic(round.tactic_selected);
      if (round.bandit_after) setBandit(round.bandit_after);
      setScenario(null);
      setPendingNo(null);
      await refresh(session._id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const isHuman = source === "human";

  return (
    <div className="page">
      <h1 className="page-title">Training</h1>
      <p className="page-sub">
        {employee ? (
          <>
            Training <strong>{employee.code}</strong> — {employee.role} · {employee.department} ·
            alertness {employee.base_alertness.toFixed(2)}
          </>
        ) : (
          "Pick an employee from the list to begin."
        )}
      </p>

      <details className="card how" style={{ marginBottom: 16 }}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>
          How this works (3 steps)
        </summary>
        <ol className="hint" style={{ margin: "10px 0 0", paddingLeft: 20, lineHeight: 1.8 }}>
          <li>The agent picks one of 4 scam styles — <strong>urgency, authority, fake invoice, credential request</strong> — especially ones it's unsure about.</li>
          <li>It writes a fake email with that style and shows it to you (or the simulated employee).</li>
          <li>Your reaction teaches it. Report = safe, Click / Enter credentials = that style works on you. The bars below are its beliefs — the highest bar is its guess at your weakness.</li>
        </ol>
      </details>

      {!employee && (
        <Link to="/" className="btn">Choose an employee</Link>
      )}

      {error && <div className="error" style={{ marginBottom: 16 }}>{error}</div>}

      {employee && (
        <>
          <div className="card">
            <h3>Session setup</h3>
            <div className="row" style={{ marginBottom: 14, alignItems: "flex-start" }}>
              <div>
                <div className="hint" style={{ marginBottom: 6 }}>Who plays the employee</div>
                <div className="pill-group">
                  {SOURCES.map((s) => (
                    <button key={s.value} className={`pill${source === s.value ? " on" : ""}`}
                      onClick={() => setSource(s.value)}>{s.label}</button>
                  ))}
                </div>
              </div>
              <div>
                <div className="hint" style={{ marginBottom: 6 }}>Selection policy</div>
                <div className="pill-group">
                  {SELECTORS.map((s) => (
                    <button key={s.value} className={`pill${selector === s.value ? " on" : ""}`}
                      onClick={() => setSelector(s.value)}>{s.label}</button>
                  ))}
                </div>
              </div>
            </div>
            <div className="row">
              <label className="field" style={{ width: 130 }}>
                Rounds
                <input type="number" min={1} max={1000} value={nRounds}
                  onChange={(e) => setNRounds(Number(e.target.value))} />
              </label>
              <button className={`pill${mode === "evaluation" ? " on" : ""}`}
                onClick={() => setMode("evaluation")}>evaluation</button>
              <button className={`pill${mode === "demo" ? " on" : ""}`}
                onClick={() => setMode("demo")}>demo</button>
              <div className="spacer" />
              <button className="btn" onClick={handleStart} disabled={busy || !!session}>
                {session ? "Session running" : "Start session"}
              </button>
              {isHuman && (
                <button className="btn ghost" onClick={handleWarmPrior} disabled={busy}>
                  {priorSessionId ? "Prior ready" : "Warm-start prior (50 rounds)"}
                </button>
              )}
              {isHuman && priorSessionId && (
                <label className="hint" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input type="checkbox" checked={inheritPrior} onChange={(e) => setInheritPrior(e.target.checked)} />
                  inherit prior
                </label>
              )}
            </div>
          </div>

          {session && (
            <>
              <div className="card">
                <h3>What the agent believes</h3>
                <PosteriorBars bandit={bandit} />
                {bandit && (
                  <div className="callout" style={{ marginTop: 14 }}>
                    {beliefSummary(bandit)}
                  </div>
                )}
                {vulnerability && vulnerability.ranking.length > 0 && (
                  <div style={{ marginTop: 14 }}>
                    <span className="hint">Estimated vulnerability ranking: </span>
                    <VulnerabilityPills ranking={vulnerability.ranking} />
                  </div>
                )}
              </div>

              {isHuman ? (
                <div className="card">
                  <h3>Live inbox — you are the employee</h3>
                  {scenario ? (
                    <>
                      <ScenarioCard scenario={scenario} />
                      <div style={{ marginTop: 14 }}>
                        <ActionButtons onResponse={handleResponse} disabled={busy} />
                      </div>
                    </>
                  ) : (
                    <div className="empty">
                      {last ? (
                        <div>
                          {last.response && lastTactic && (
                            <div className="callout" style={{ marginBottom: 14, textAlign: "left" }}>
                              <strong>{responseNarration(last.response, lastTactic)}</strong>
                            </div>
                          )}
                          <button className="btn primary" onClick={handleNext} disabled={busy}>
                            Next round
                          </button>
                        </div>
                      ) : (
                        <button className="btn primary" onClick={handleNext} disabled={busy}>
                          Start round 1 — the agent sends its first fake email
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="card">
                  <h3>Run rounds (simulated)</h3>
                  <div className="row">
                    <button className="btn primary" onClick={handleNext} disabled={busy}>
                      Next round
                    </button>
                    <button className="btn" onClick={() => handleBatch(50)} disabled={busy}>
                      Run 50
                    </button>
                    <button className="btn" onClick={() => handleBatch(300)} disabled={busy}>
                      Run 300
                    </button>
                  </div>
                  {last && (
                    <div style={{ marginTop: 12 }}>
                      {last.response && lastTactic && (
                        <div className="callout">
                          <strong>{responseNarration(last.response, lastTactic)}</strong>
                        </div>
                      )}
                    </div>
                  )}
                  {scenario && (
                    <div style={{ marginTop: 14 }}>
                      <ScenarioCard scenario={scenario} />
                    </div>
                  )}
                </div>
              )}

              <div className="card">
                <h3>Round history</h3>
                {history.length === 0 ? (
                  <div className="empty">no rounds yet</div>
                ) : (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>#</th><th>tactic</th><th>response</th>
                        <th>detection</th><th>safety</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.slice(-20).reverse().map((r) => (
                        <tr key={r._id}>
                          <td>{r.round_no}</td>
                          <td className="muted">{r.tactic_selected}</td>
                          <td>{r.response?.response ?? "—"}</td>
                          <td>{r.reward?.detection ?? "—"}</td>
                          <td>{r.reward?.safety ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}