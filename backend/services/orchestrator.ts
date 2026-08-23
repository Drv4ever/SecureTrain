/** Training orchestrator: wires bandit -> LLM -> freshness -> behavior ->
 *  reward -> update -> persist for one round (docs/BLUEPRINT.md, section 3).
 *
 *  Python stays stateless; Node owns persistence. Everything here is
 *  idempotent by (session, round_no): re-running a round returns the
 *  stored result instead of double-updating the bandit.
 */

import { createHash } from "crypto";
import { config } from "../config";
import { BanditState, Employee, Round, Scenario, TrainingSession } from "../db";
import { generateScenario, templateFallback } from "./llm";

export const RESPONSES = ["ignore", "report", "click", "credentials"] as const;
export type Response = (typeof RESPONSES)[number];

const TACTICS = ["urgency", "authority", "invoice", "credential"] as const;

// Design A: detection drives the bandit; safety is reported only (see blueprint §9).
export const DETECTION_REWARDS: Record<Response, number> = {
  credentials: 1.0, click: 0.7, ignore: 0.3, report: 0.0,
};
export const SAFETY_REWARDS: Record<Response, number> = {
  report: 1.0, ignore: 0.6, click: 0.2, credentials: 0.0,
};

// ---------- python ai-service client ----------

export class AiError extends Error {}

export async function aiPost(path: string, body: unknown): Promise<Record<string, any>> {
  const response = await fetch(`${config.aiServiceUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new AiError(`AI ${path} -> ${response.status}: ${detail.slice(0, 200)}`);
  }
  return response.json();
}

const contentHash = (subject: string, body: string): string =>
  createHash("sha256")
    .update(`${subject} ${body}`.toLowerCase().replace(/\s+/g, " ").trim())
    .digest("hex");

// ---------- bandit state ----------

const defaultArms = () => ({
  urgency: { alpha: 1, beta: 1, pulls: 0 },
  authority: { alpha: 1, beta: 1, pulls: 0 },
  invoice: { alpha: 1, beta: 1, pulls: 0 },
  credential: { alpha: 1, beta: 1, pulls: 0 },
});

async function getOrCreateBanditState(sessionId: string) {
  const existing = await BanditState.findOne({ session_id: sessionId });
  if (existing) return existing;
  return BanditState.create({ session_id: sessionId, arms: defaultArms(), total_rounds: 0 });
}

// ---------- session lifecycle ----------

export async function startSession(payload: {
  employee_id: string;
  selector: "thompson" | "random" | "epsilon_greedy";
  behavior_source: "classifier" | "probabilistic" | "human";
  mode?: "evaluation" | "demo";
  n_rounds?: number;
  difficulty?: number;
  seed?: number;
  inherit_bandit_from?: string;
}) {
  const session = await TrainingSession.create({
    employee_id: payload.employee_id,
    selector: payload.selector,
    behavior_source: payload.behavior_source,
    mode: payload.mode ?? "evaluation",
    n_rounds: payload.n_rounds ?? 300,
    difficulty: payload.difficulty ?? config.defaultDifficulty,
    seed: payload.seed ?? 1,
  });
  const bandit = await getOrCreateBanditState(String(session._id));

  // warm-start: a live-demo session may inherit the posterior learned by a
  // pre-seeding session so the demo begins with an informed prior
  if (payload.inherit_bandit_from) {
    const source = await BanditState.findOne({ session_id: payload.inherit_bandit_from });
    if (source) {
      bandit.arms = JSON.parse(JSON.stringify(source.arms));
      bandit.markModified("arms");
      await bandit.save();
    }
  }
  return session;
}

// ---------- one round ----------

export async function runRound(sessionId: string, opts: { useLlm?: boolean } = {}) {
  const session = await TrainingSession.findById(sessionId);
  if (!session) throw new Error("session not found");
  if (session.status === "complete") throw new Error("session already complete");

  const latest = await Round.findOne({ session_id: sessionId }).sort({ round_no: -1 });
  const roundNo = (latest?.round_no ?? 0) + 1;

  // idempotency: never run a round twice
  const existing = await Round.findOne({ session_id: sessionId, round_no: roundNo });
  if (existing) return { round: existing };

  const bandit = await getOrCreateBanditState(sessionId);
  const employee = (await Employee.findById(session.employee_id))!;

  // 2. bandit selects a tactic (random baseline bypasses the bandit entirely)
  const tactic: string = session.selector === "random"
    ? TACTICS[Math.floor(Math.random() * TACTICS.length)]
    : (await aiPost("/bandit/select", { arms: bandit.arms })).tactic;

  // 3-4. generate a scenario (LLM unless disabled for batch speed)
  const recentScenarios = await Scenario.find({ session_id: sessionId })
    .sort({ round_no: -1 }).limit(20);
  const recentSubjects = recentScenarios.slice(0, 10).map((s) => s.subject);
  const recentTexts = recentScenarios.map((s) => `${s.subject} ${s.body}`);

  const scenario = await produceFreshScenario({
    tactic,
    difficulty: session.difficulty,
    employee,
    recentSubjects,
    recentTexts,
    useLlm: opts.useLlm ?? true,
  });

  // 7. persist scenario
  const scenarioDoc = await Scenario.create({
    session_id: sessionId,
    round_no: roundNo,
    tactic,
    difficulty: session.difficulty,
    sender_name: scenario.sender_name,
    sender_email: scenario.sender_email,
    subject: scenario.subject,
    body: scenario.body,
    indicators: scenario.indicators,
    hook: scenario.hook,
    company: scenario.company,
    content_hash: contentHash(scenario.subject, scenario.body),
    generation_source: scenario.generation_source,
    freshness: { max_cosine: 0, passed: true },
  });

  // 8. behavior step (simulated vs human)
  if (session.behavior_source === "human") {
    const round = await Round.create({
      session_id: sessionId,
      employee_id: employee._id,
      round_no: roundNo,
      tactic_selected: tactic,
      scenario_id: scenarioDoc._id,
      status: "pending_human",
    });
    return { round, scenario: scenarioDoc };
  }

  const { response, probs, source } = await simulateBehavior(sessionId, session.behavior_source, employee, tactic, roundNo);

  // 9-10. reward + bandit update
  const detection = DETECTION_REWARDS[response];
  const safety = SAFETY_REWARDS[response];

  if (session.selector !== "random") {
    const arm = bandit.arms[tactic];
    const updated = await aiPost("/bandit/update", {
      arm: tactic, reward: detection, alpha: arm.alpha, beta: arm.beta,
    });
    bandit.arms[tactic] = { alpha: updated.alpha, beta: updated.beta, pulls: arm.pulls + 1 };
  }
  bandit.total_rounds = roundNo;
  bandit.markModified("arms"); // mongoose Mixed requires explicit dirty marking
  await bandit.save();

  // 11. persist round
  const round = await Round.create({
    session_id: sessionId,
    employee_id: employee._id,
    round_no: roundNo,
    tactic_selected: tactic,
    scenario_id: scenarioDoc._id,
    status: "completed",
    response: { response, probs, source },
    reward: { detection, safety },
    bandit_after: bandit.arms,
  });

  return { round, scenario: scenarioDoc, response, rewards: { detection, safety } };
}

/** Validate + de-duplicate a generated scenario against session history. */
async function produceFreshScenario(opts: {
  tactic: string; difficulty: number;
  employee: { role: string; department: string; code: string };
  recentSubjects: string[]; recentTexts: string[]; useLlm: boolean;
}) {
  const { tactic, difficulty, employee, recentSubjects, recentTexts, useLlm } = opts;

  for (let attempt = 0; attempt < 3; attempt++) {
    const scenario = useLlm
      ? await generateScenario({
          tactic, difficulty, role: employee.role,
          department: employee.department, recentSubjects,
        })
      : templateFallback(tactic);

    const evaluate = await aiPost("/scenario/evaluate", { scenario });
    if (!evaluate.valid) continue;

    const freshness = await aiPost("/scenario/freshness", {
      candidate: scenario, history: recentTexts.map((text) => ({ subject: "", body: text })),
      threshold: config.freshnessThreshold,
    });
    if (freshness.passed) {
      return { ...scenario, freshness: { max_cosine: freshness.max_cosine, passed: true } };
    }
  }
  // give up on freshness but keep a valid scenario
  const fallback = templateFallback(tactic);
  return { ...fallback, freshness: { max_cosine: 1, passed: false } };
}

async function simulateBehavior(
  sessionId: string,
  behaviorSource: string,
  employee: { _id: unknown; code: string; role: string; department: string; base_alertness: number; susceptibility: Record<string, number> },
  tactic: string,
  roundNo: number,
): Promise<{ response: Response; probs: Record<string, number>; source: string }> {
  if (behaviorSource === "classifier") {
    const priorRounds = await Round.find({ session_id: sessionId, status: "completed" });
    const features = buildFeatures(employee, priorRounds, tactic, roundNo);
    const prediction = await aiPost("/behavior/predict", { features });
    const probs: Record<string, number> = prediction.probs;
    const response = sampleFromProbs(probs);
    return { response, probs, source: "classifier" };
  }
  // probabilistic: ask the simulator directly (susceptibility is the hidden ground truth)
  const simulation = await aiPost("/behavior/simulate", {
    employee: {
      code: employee.code, role: employee.role, department: employee.department,
      base_alertness: employee.base_alertness, susceptibility: employee.susceptibility,
    },
    tactic,
    difficulty: 3,
  });
  return { response: simulation.response as Response, probs: simulation.probs, source: "probabilistic" };
}

// ---------- human-mode completion ----------

export async function completeHumanRound(sessionId: string, roundNo: number, response: Response) {
  if (!(response in DETECTION_REWARDS)) throw new Error(`invalid response '${response}'`);
  const round = await Round.findOne({ session_id: sessionId, round_no: roundNo });
  if (!round) throw new Error("round not found");
  if (round.status !== "pending_human") throw new Error("round is not awaiting human input");

  const bandit = await getOrCreateBanditState(sessionId);
  const arm = bandit.arms[round.tactic_selected];
  const updated = await aiPost("/bandit/update", {
    arm: round.tactic_selected, reward: DETECTION_REWARDS[response],
    alpha: arm.alpha, beta: arm.beta,
  });

  bandit.arms[round.tactic_selected] = { alpha: updated.alpha, beta: updated.beta, pulls: arm.pulls + 1 };
  bandit.markModified("arms");
  await bandit.save();

  round.status = "completed";
  round.response = { response, probs: {}, source: "human" };
  round.reward = { detection: DETECTION_REWARDS[response], safety: SAFETY_REWARDS[response] };
  round.bandit_after = bandit.arms;
  await round.save();
  return round;
}

// ---------- batch runner (evaluation) ----------

export async function runBatch(sessionId: string, rounds: number, opts: { useLlm?: boolean } = {}) {
  const session = await TrainingSession.findById(sessionId);
  if (!session) throw new Error("session not found");

  const completed = await Round.countDocuments({ session_id: sessionId, status: "completed" });
  let ran = 0;
  for (let i = completed; i < rounds; i++) {
    const result = await runRound(sessionId, opts);
    if (!("response" in result && result.response)) break; // human mode cannot batch
    ran += 1;
  }
  if (ran > 0) {
    session.status = "complete";
    session.finished_at = new Date();
    await session.save();
  }
  return { ran };
}

// ---------- helpers ----------

function buildFeatures(
  employee: { code: string; role: string; department: string; base_alertness: number },
  priorRounds: { tactic_selected: string; response?: { response?: string } }[],
  tactic: string,
  roundNo: number,
) {
  const timesSeen = priorRounds.filter((r) => r.tactic_selected === tactic).length;
  const last = priorRounds.length
    ? priorRounds[priorRounds.length - 1].response?.response ?? null
    : null;
  let streak = 0;
  for (let i = priorRounds.length - 1; i >= 0; i--) {
    const r = priorRounds[i].response?.response;
    if (r === "ignore" || r === "report") streak += 1;
    else break;
  }
  return {
    tactic,
    difficulty: 3,
    role: employee.role,
    department: employee.department,
    base_alertness: employee.base_alertness,
    times_seen_tactic: timesSeen,
    last_response: last,
    safe_streak: streak,
    round_no: roundNo,
    employee_code: employee.code,
  };
}

function sampleFromProbs(probs: Record<string, number>): Response {
  const labels = RESPONSES.filter((r) => r in probs);
  const weights = labels.map((r) => probs[r]);
  const total = weights.reduce((a, b) => a + b, 0);
  let draw = Math.random() * total;
  for (let i = 0; i < labels.length; i++) {
    draw -= weights[i];
    if (draw <= 0) return labels[i] as Response;
  }
  return labels[labels.length - 1] as Response;
}