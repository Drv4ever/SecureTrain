/** Employee CRUD + vulnerability/history endpoints. */

import { Router } from "express";
import { BanditState, Employee, Round, TrainingSession } from "../db";

const TACTICS = ["urgency", "authority", "invoice", "credential"];
const router = Router();

const pick = <T>(obj: Record<string, T>, keys: string[]): Record<string, T> => {
  const out: Record<string, T> = {};
  for (const key of keys) if (key in obj) out[key] = obj[key];
  return out;
};

const publicEmployee = (doc: any, includeTruth: boolean) => {
  const base = {
    _id: doc._id,
    code: doc.code,
    role: doc.role,
    department: doc.department,
    base_alertness: doc.base_alertness,
    created_at: doc.created_at,
  };
  return includeTruth ? { ...base, susceptibility: doc.susceptibility } : base;
};

/** Generate a hidden susceptibility profile with exactly one dominant arm. */
function randomSusceptibility(): Record<string, number> {
  const dominant = TACTICS[Math.floor(Math.random() * TACTICS.length)];
  const profile: Record<string, number> = {};
  for (const tactic of TACTICS) {
    profile[tactic] = tactic === dominant
      ? 0.65 + Math.random() * 0.25   // [0.65, 0.90]
      : 0.05 + Math.random() * 0.40;  // <= 0.45  (gap >= 0.20)
  }
  return profile;
}

router.post("/employees", async (req, res) => {
  try {
    const body = req.body ?? {};
    const employee = await Employee.create({
      code: body.code ?? `emp_${Date.now()}`,
      role: body.role ?? "employee",
      department: body.department ?? "General",
      base_alertness: body.base_alertness ?? 0.55,
      susceptibility: body.susceptibility ?? randomSusceptibility(),
    });
    res.status(201).json(publicEmployee(employee, false));
  } catch (err) {
    res.status(400).json({ error: (err as Error).message });
  }
});

router.get("/employees", async (req, res) => {
  const filter: Record<string, unknown> = {};
  if (req.query.role) filter.role = req.query.role;
  if (req.query.department) filter.department = req.query.department;
  const employees = await Employee.find(filter).limit(Number(req.query.limit ?? 500));
  res.json(employees.map((e) => publicEmployee(e, false)));
});

router.get("/employees/:id", async (req, res) => {
  const employee = await Employee.findById(req.params.id);
  if (!employee) return res.status(404).json({ error: "employee not found" });
  const includeTruth = req.query.include_truth === "true"; // eval harness only
  res.json(publicEmployee(employee, includeTruth));
});

/** Estimated vulnerability ranking = posterior-mean estimates from the
 *  employee's completed sessions (the agent's learned belief). */
router.get("/employees/:id/vulnerability", async (req, res) => {
  const employee = await Employee.findById(req.params.id);
  if (!employee) return res.status(404).json({ error: "employee not found" });

  const sessions = await TrainingSession.find({ employee_id: employee._id });
  const totals: Record<string, { sum: number; count: number }> = {};
  for (const tactic of TACTICS) totals[tactic] = { sum: 0, count: 0 };

  for (const session of sessions) {
    const bandit = await BanditState.findOne({ session_id: session._id });
    if (!bandit) continue;
    for (const tactic of TACTICS) {
      const arm = bandit.arms[tactic];
      if (arm && arm.alpha + arm.beta > 2) {
        totals[tactic].sum += arm.alpha / (arm.alpha + arm.beta);
        totals[tactic].count += 1;
      }
    }
  }

  const estimates = TACTICS.map((tactic) => ({
    tactic,
    mean: totals[tactic].count ? totals[tactic].sum / totals[tactic].count : null,
    sessions: totals[tactic].count,
  }));
  const ranking = estimates
    .filter((e) => e.mean !== null)
    .sort((a, b) => (b.mean as number) - (a.mean as number))
    .map((e) => e.tactic);

  res.json({ employee_id: employee._id, estimates, ranking });
});

router.get("/employees/:id/history", async (req, res) => {
  const employee = await Employee.findById(req.params.id);
  if (!employee) return res.status(404).json({ error: "employee not found" });

  const sessions = await TrainingSession.find({ employee_id: employee._id });
  const rounds = await Round.find({ employee_id: employee._id })
    .sort({ created_at: -1 })
    .limit(Number(req.query.limit ?? 100));

  res.json({
    employee_id: employee._id,
    sessions: sessions.length,
    rounds: rounds.map((r) => pick(r.toObject(), [
      "round_no", "tactic_selected", "status", "response", "reward", "created_at",
    ])),
  });
});

export default router;