/** Backend client. In dev, Vite proxies /api -> http://localhost:4000. */

const API = "/api";

async function http<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error((body as { error?: string }).error ?? `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  http<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const patch = <T>(path: string, body: unknown) =>
  http<T>(path, { method: "PATCH", body: JSON.stringify(body) });

// ---------- types ----------

export type Tactic = "urgency" | "authority" | "invoice" | "credential";
export type Response = "ignore" | "report" | "click" | "credentials";

export type Employee = {
  _id: string;
  code: string;
  role: string;
  department: string;
  base_alertness: number;
  created_at: string;
};

export type Session = {
  _id: string;
  employee_id: string;
  selector: "thompson" | "random" | "epsilon_greedy";
  behavior_source: "classifier" | "probabilistic" | "human";
  mode: "evaluation" | "demo";
  status: "running" | "complete";
  n_rounds: number;
  difficulty: number;
};

export type Scenario = {
  _id: string;
  tactic: Tactic;
  difficulty: number;
  sender_name: string;
  sender_email: string;
  subject: string;
  body: string;
  indicators: string[];
  hook: string;
  company: string;
  generation_source: "llm" | "template";
};

export type ArmState = { alpha: number; beta: number; pulls: number };
export type Bandit = Record<Tactic, ArmState>;

export type Round = {
  _id: string;
  round_no: number;
  tactic_selected: Tactic;
  status: "completed" | "pending_human";
  response?: { response: Response; probs: Record<string, number>; source: string } | null;
  reward?: { detection: number; safety: number } | null;
  bandit_after?: Bandit;
  created_at: string;
};

export type RoundResult = {
  round: Round;
  scenario?: Scenario;
  response?: Response;
  rewards?: { detection: number; safety: number };
};

export type Vulnerability = {
  employee_id: string;
  estimates: { tactic: Tactic; mean: number | null; sessions: number }[];
  ranking: Tactic[];
};

export type Overview = {
  total_sessions: number;
  selectors: Record<string, {
    sessions: number;
    curve: number[];
    mean_final_reward: number;
    response_counts: Record<Response, number>;
    selection_share: Record<Tactic, number>;
    mean_final_safety?: number;
  }>;
  tactics: string[];
};

export type ExperimentResult = {
  name: string;
  config: { rounds: number; employees: number; reps: number; selectors: string[]; behavior_source: string };
  results: Record<string, {
    rewards: number[];
    regrets: number[];
    discovery: boolean[];
    mean_reward: number;
    mean_regret: number;
    discovery_rate: number;
  }>;
  run_at: string;
};

// ---------- employees ----------

export const listEmployees = () => http<Employee[]>("/employees");
export const getEmployee = (id: string) => http<Employee>(`/employees/${id}`);
export const getVulnerability = (id: string) => http<Vulnerability>(`/employees/${id}/vulnerability`);

// ---------- training ----------

export const startSession = (body: {
  employee_id: string;
  selector: Session["selector"];
  behavior_source: Session["behavior_source"];
  mode?: Session["mode"];
  n_rounds?: number;
  inherit_bandit_from?: string;
}) => post<Session>("/training/sessions", body);

export const runRound = (sessionId: string, useLlm = true) =>
  post<RoundResult>(`/training/sessions/${sessionId}/rounds`, { use_llm: useLlm });

export const completeRound = (sessionId: string, roundNo: number, response: Response) =>
  patch<Round>(`/training/sessions/${sessionId}/rounds/${roundNo}/response`, { response });

export const runBatch = (sessionId: string, rounds: number) =>
  post<{ ran: number }>(`/training/sessions/${sessionId}/run-batch`, { rounds, use_llm: false });

export const getSession = (sessionId: string) =>
  http<{ session: Session; rounds: Round[] }>(`/training/sessions/${sessionId}?limit=300`);

export const warmStart = (employeeId: string, rounds = 50) =>
  post<{ session: Session; ran: number }>("/demo/warm-start", { employee_id: employeeId, rounds });

// ---------- analytics ----------

export const getOverview = () => http<Overview>("/analytics/overview");
export const runExperiment = (body: {
  name?: string;
  employees?: number;
  rounds?: number;
  reps?: number;
  selectors?: string[];
  behavior_source?: string;
}) => post<ExperimentResult>("/experiments", body);