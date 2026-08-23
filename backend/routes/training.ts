/** Training session lifecycle: start, run rounds, human responses, batch, export. */

import { Router } from "express";
import { Round, Scenario, TrainingSession } from "../db";
import {
  RESPONSES,
  completeHumanRound,
  runBatch,
  runRound,
  startSession,
} from "../services/orchestrator";

const router = Router();

router.post("/training/sessions", async (req, res) => {
  try {
    const session = await startSession(req.body ?? {});
    res.status(201).json(session);
  } catch (err) {
    res.status(400).json({ error: (err as Error).message });
  }
});

router.post("/training/sessions/:id/rounds", async (req, res) => {
  try {
    const result = await runRound(req.params.id, { useLlm: req.body?.use_llm ?? true });
    res.json(result);
  } catch (err) {
    res.status(400).json({ error: (err as Error).message });
  }
});

router.patch("/training/sessions/:id/rounds/:roundNo/response", async (req, res) => {
  const response = req.body?.response;
  if (!RESPONSES.includes(response)) {
    return res.status(400).json({ error: `response must be one of ${RESPONSES.join(", ")}` });
  }
  try {
    const round = await completeHumanRound(req.params.id, Number(req.params.roundNo), response);
    res.json(round);
  } catch (err) {
    res.status(400).json({ error: (err as Error).message });
  }
});

router.post("/training/sessions/:id/run-batch", async (req, res) => {
  try {
    const rounds = Number(req.body?.rounds ?? 300);
    const useLlm = req.body?.use_llm ?? false; // batch defaults to templates for speed
    const result = await runBatch(req.params.id, rounds, { useLlm });
    res.json(result);
  } catch (err) {
    res.status(400).json({ error: (err as Error).message });
  }
});

/** Pre-seed a live-demo employee with simulated rounds so a human session
 *  can later inherit the learned prior (POST /training/sessions with
 *  inherit_bandit_from = this session's id). */
router.post("/demo/warm-start", async (req, res) => {
  try {
    const employeeId = req.body?.employee_id;
    const rounds = Number(req.body?.rounds ?? 50);
    if (!employeeId) return res.status(400).json({ error: "employee_id is required" });
    const session = await startSession({
      employee_id: employeeId,
      selector: "thompson",
      behavior_source: "probabilistic",
      mode: "demo",
      n_rounds: rounds,
    });
    const result = await runBatch(String(session._id), rounds, { useLlm: false });
    res.json({ session, ran: result.ran });
  } catch (err) {
    res.status(400).json({ error: (err as Error).message });
  }
});

router.get("/training/sessions/:id", async (req, res) => {
  const session = await TrainingSession.findById(req.params.id);
  if (!session) return res.status(404).json({ error: "session not found" });
  const rounds = await Round.find({ session_id: session._id })
    .sort({ round_no: 1 })
    .skip(Number(req.query.skip ?? 0))
    .limit(Number(req.query.limit ?? 200));
  res.json({ session, rounds });
});

router.get("/training/sessions/:id/export", async (req, res) => {
  const session = await TrainingSession.findById(req.params.id);
  if (!session) return res.status(404).json({ error: "session not found" });

  const rounds = await Round.find({ session_id: session._id }).sort({ round_no: 1 });
  const scenarios = await Scenario.find({ session_id: session._id });

  const scenarioById = new Map(scenarios.map((s) => [String(s._id), s]));
  const rows = rounds.map((r) => {
    const scenario = scenarioById.get(String(r.scenario_id));
    return {
      session_id: String(session._id),
      selector: session.selector,
      mode: session.mode,
      round_no: r.round_no,
      tactic: r.tactic_selected,
      response: r.response?.response ?? null,
      reward_detection: r.reward?.detection ?? null,
      reward_safety: r.reward?.safety ?? null,
      subject: scenario?.subject ?? "",
      generation_source: scenario?.generation_source ?? "",
      freshness_max_cosine: scenario?.freshness?.max_cosine ?? null,
    };
  });

  const format = (req.query.format ?? "jsonl") as string;
  if (format === "csv") {
    const header = Object.keys(rows[0] ?? {}).join(",");
    const lines = rows.map((r) => Object.values(r).map(quoteCsv).join(","));
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", "attachment; filename=session_export.csv");
    return res.send([header, ...lines].join("\n"));
  }

  res.setHeader("Content-Type", "application/x-ndjson");
  res.send(rows.map((r) => JSON.stringify(r)).join("\n"));
});

function quoteCsv(value: unknown): string {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export default router;