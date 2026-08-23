/** Dashboard aggregates + experiment grid runner. */

import { Router } from "express";
import { Analytics, Employee, Round, TrainingSession } from "../db";
import { config } from "../config";
import { aiPost, runBatch, startSession } from "../services/orchestrator";

const router = Router();
const TACTICS = ["urgency", "authority", "invoice", "credential"];

async function computeOverview() {
  const sessions = await TrainingSession.find({ status: "complete" }).populate("employee_id");
  const bySelector: Record<string, any> = {};

  for (const session of sessions) {
    const rounds = await Round.find({ session_id: session._id, status: "completed" }).sort({ round_no: 1 });
    if (!rounds.length) continue;

    const key = session.selector;
    const agg = (bySelector[key] ??= {
      sessions: 0,
      cumulative_reward: [],
      response_counts: { ignore: 0, report: 0, click: 0, credentials: 0 },
      selection_share: { urgency: 0, authority: 0, invoice: 0, credential: 0 },
      mean_final_safety: 0,
    });
    agg.sessions += 1;

    let cumulative = 0;
    for (const round of rounds) {
      cumulative += round.reward?.detection ?? 0;
      agg.cumulative_reward.push(cumulative);
      const response = round.response?.response as keyof typeof agg.response_counts;
      if (response in agg.response_counts) agg.response_counts[response] += 1;
      const tactic = round.tactic_selected as keyof typeof agg.selection_share;
      if (tactic in agg.selection_share) agg.selection_share[tactic] += 1;
      agg.mean_final_safety += round.reward?.safety ?? 0;
    }
    agg.mean_final_safety /= rounds.length;
  }

  // aggregate curves to a compact form: mean curve over sessions per selector
  for (const selector of Object.keys(bySelector)) {
    const agg = bySelector[selector];
    const maxLen = Math.max(agg.cumulative_reward.length, 1);
    agg.curve = [];
    const buckets = 30;
    for (let b = 0; b < buckets; b++) {
      const start = Math.floor((b * maxLen) / buckets);
      const end = Math.floor(((b + 1) * maxLen) / buckets) || start + 1;
      const slice = agg.cumulative_reward.slice(start, end);
      agg.curve.push(slice.length ? slice[slice.length - 1] : 0);
    }
    delete agg.cumulative_reward;
    agg.mean_final_reward = agg.curve[agg.curve.length - 1];
  }

  return {
    total_sessions: sessions.length,
    selectors: bySelector,
    tactics: TACTICS,
  };
}

router.get("/analytics/overview", async (_req, res) => {
  try {
    res.json(await computeOverview());
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

/** Snapshot the current overview into the analytics collection (optional). */
router.post("/analytics/snapshot", async (_req, res) => {
  const overview = await computeOverview();
  await Analytics.create({
    scope: "global",
    selector: "all",
    metrics: {
      ...overview,
      generated_at: new Date().toISOString(),
      config: { ai_service: config.aiServiceUrl, groq_bulk: config.groqModelBulk },
    },
  });
  res.status(201).json({ snapshotted: true });
});

/** Grid runner: reproduces the offline experiment through the live stack.
 *  Creates sessions across employees x selectors x reps, runs batches, and
 *  aggregates final reward + regret (regret via the Python oracle). */
router.post("/experiments", async (req, res) => {
  try {
    const body = req.body ?? {};
    const rounds = Number(body.rounds ?? 150);
    const nEmployees = Number(body.employees ?? 10);
    const reps = Number(body.reps ?? 1);
    const selectors: string[] = body.selectors ?? ["thompson", "random"];
    const behaviorSource = body.behavior_source ?? "probabilistic";

    const employees = await Employee.find().limit(nEmployees);
    type ResultAgg = {
      rewards: number[]; regrets: number[]; discovery: boolean[];
      mean_reward?: number; mean_regret?: number; discovery_rate?: number;
    };
    const results: Record<string, ResultAgg> = {};

    for (const selector of selectors) {
      const agg: ResultAgg = (results[selector] = { rewards: [], regrets: [], discovery: [] });
      for (let rep = 0; rep < reps; rep++) {
        for (const emp of employees) {
          const session = await startSession({
            employee_id: String(emp._id),
            selector: selector as any,
            behavior_source: behaviorSource as any,
            mode: "evaluation",
            n_rounds: rounds,
            seed: rep + 1,
          });
          await runBatch(String(session._id), rounds, { useLlm: false });

          const sessRounds = await Round.find({ session_id: session._id, status: "completed" }).sort({ round_no: 1 });
          if (!sessRounds.length) continue;

          const reward = sessRounds.reduce((sum, r) => sum + (r.reward?.detection ?? 0), 0);
          agg.rewards.push(reward);

          const means = await aiPost("/metrics/true-means", {
            employee: {
              code: emp.code, role: emp.role, department: emp.department,
              base_alertness: emp.base_alertness, susceptibility: emp.susceptibility,
            },
          });
          const metrics = await aiPost("/metrics/session", {
            true_means: means,
            rounds: sessRounds.map((r) => ({ arm: r.tactic_selected, reward: r.reward?.detection })),
          });
          agg.regrets.push(metrics.cum_regret[metrics.cum_regret.length - 1]);

          // discovery: did the learned posterior pick the true weak tactic?
          const bandit = await Round.findOne({ session_id: session._id }).sort({ round_no: -1 });
          const arms = bandit?.bandit_after ?? {};
          const learned = Object.keys(arms).reduce((a, b) => (arms[b].alpha / (arms[b].alpha + arms[b].beta)) > (arms[a].alpha / (arms[a].alpha + arms[a].beta)) ? b : a);
          const susceptibility = (emp.susceptibility as any).toObject?.() ?? emp.susceptibility; // subdoc -> plain
          const trueWeak = Object.keys(susceptibility).reduce((a, b) => susceptibility[b] > susceptibility[a] ? b : a);
          agg.discovery.push(learned === trueWeak);
        }
      }
      agg.mean_reward = mean(agg.rewards);
      agg.mean_regret = mean(agg.regrets);
      agg.discovery_rate = agg.discovery.length ? agg.discovery.filter(Boolean).length / agg.discovery.length : 0;
    }

    const summary = {
      name: body.name ?? `experiment-${Date.now()}`,
      config: { rounds, employees: employees.length, reps, selectors, behavior_source: behaviorSource },
      results,
      run_at: new Date().toISOString(),
    };
    res.json(summary);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

function mean(values: number[]): number {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
}

export default router;