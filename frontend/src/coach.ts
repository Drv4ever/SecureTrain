import type { ArmState, Bandit, Response, Tactic } from "./api";

/** Plain-language narration of one round's outcome. */
export function responseNarration(response: Response, tactic: Tactic): string {
  switch (response) {
    case "report":
      return `You reported the email — the safest move. The agent learns "${tactic}" tricks don't fool you, and will test it less.`;
    case "ignore":
      return `You ignored it. That's okay, though reporting is safer. Mild signal that "${tactic}" isn't your weak spot.`;
    case "click":
      return `You clicked the link. Strong signal — the agent now suspects "${tactic}" scams work on you.`;
    case "credentials":
      return `You handed over credentials — the strongest possible signal. The agent now believes "${tactic}" is your biggest weakness.`;
  }
  return "Round recorded.";
}

/** What the agent believes right now, in one line. */
export function beliefSummary(bandit: Bandit): string {
  const ranked = (Object.entries(bandit) as [Tactic, ArmState][])
    .map(([t, a]) => ({ t, mean: a.alpha / (a.alpha + a.beta), pulls: a.pulls }))
    .sort((x, y) => y.mean - x.mean);

  const top = ranked[0];
  const second = ranked[1];
  const confident = top.pulls >= 10 && top.mean - second.mean > 0.05;
  const list = ranked.map((r) => `${r.t} ${Math.round(r.mean * 100)}%`).join(" · ");

  if (confident) {
    return `Most likely weakness: ${top.t} (${list}). The agent is fairly confident — it will keep testing there.`;
  }
  return `Still exploring — current top suspect: ${top.t} (${list}). A few more rounds and it will settle.`;
}

/** Counts of how many rounds each tactic has been tested. */
export function pullsOf(bandit: Bandit): Record<Tactic, number> {
  return Object.fromEntries(
    (Object.entries(bandit) as [Tactic, ArmState][]).map(([t, a]) => [t, a.pulls]),
  ) as Record<Tactic, number>;
}