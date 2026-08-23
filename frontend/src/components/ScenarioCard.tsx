import type { Scenario } from "../api";

export function ScenarioCard({ scenario }: { scenario: Scenario }) {
  const initials = scenario.sender_name
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="email">
      <div className="head">
        <div className="avatar">{initials || "?"}</div>
        <div>
          <div className="subject">{scenario.subject}</div>
          <div className="from">
            {scenario.sender_name} &lt;{scenario.sender_email}&gt;
          </div>
        </div>
        <div className="spacer" />
        <span className="sim-banner">Simulation</span>
      </div>
      <div className="body">{scenario.body}</div>
      <div className="indicators">
        <strong>Why this is phishy</strong>
        <ul>
          {scenario.indicators.map((indicator, i) => (
            <li key={i}>{indicator}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}