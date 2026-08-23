/** Scenario generation for Node: Groq first, local template fallback.
 *
 * Reuses the canonical prompt text + templates from the repo's prompts/
 * directory (the Python offline pool generator uses the same files).
 */

import fs from "fs";
import path from "path";
import { config } from "../config";

const GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions";
const TACTICS = ["urgency", "authority", "invoice", "credential"];

const FICTIONAL_COMPANIES = [
  "Aurora Cloud",
  "Northwind Logistics",
  "Vantage Partners",
  "Ironpeak Systems",
  "Harborline Group",
  "Crestwood Consulting",
];

const STYLE_SEEDS = [
  "formal corporate memo",
  "casual colleague note",
  "automated system notification",
  "overworked manager's quick ask",
  "compliance official notice",
];

export type Scenario = {
  tactic: string;
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

export type ScenarioResult = { scenario: Scenario; attempts: number };

const readText = (rel: string) => fs.readFileSync(path.join(config.promptsDir, rel), "utf-8");
const templatesDir = () => path.join(config.promptsDir, "templates");

function systemPrompt(): string {
  return readText("system_prompt.txt");
}

function buildUserPrompt(opts: {
  tactic: string; difficulty: number; role: string; department: string;
  company: string; style: string; recentSubjects: string[];
}): string {
  const lines = [
    "Generate one phishing scenario for a security-awareness training simulation.",
    `Target: ${opts.role} in the ${opts.department} department.`,
    `Company name to use: ${opts.company}.`,
    `Tactic: ${opts.tactic}.`,
    `Difficulty target: ${opts.difficulty} out of 5.`,
    `Writing style: ${opts.style}.`,
    "Do not reuse or paraphrase any of these recent subject lines: "
      + (opts.recentSubjects.length ? opts.recentSubjects.join("; ") : "none yet."),
  ];
  return lines.join("\n");
}

function minimalShapeCheck(raw: Record<string, unknown>): raw is Scenario {
  return (
    typeof raw.tactic === "string" && TACTICS.includes(raw.tactic) &&
    typeof raw.difficulty === "number" &&
    typeof raw.sender_name === "string" &&
    typeof raw.sender_email === "string" &&
    typeof raw.subject === "string" &&
    typeof raw.body === "string" &&
    Array.isArray(raw.indicators) &&
    typeof raw.hook === "string"
  );
}

async function groqGenerate(userPrompt: string, model?: string): Promise<Record<string, unknown> | null> {
  if (!config.groqApiKey) return null;
  const chosen = model ?? config.groqModelBulk;
  try {
    const response = await fetch(GROQ_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${config.groqApiKey}` },
      body: JSON.stringify({
        model: chosen,
        messages: [
          { role: "system", content: systemPrompt() },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.9,
        response_format: { type: "json_object" },
      }),
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) {
      console.warn(`[llm] Groq HTTP ${response.status}, using template fallback`);
      return null;
    }
    const data = (await response.json()) as { choices: { message: { content: string } }[] };
    return JSON.parse(data.choices[0].message.content) as Record<string, unknown>;
  } catch (err) {
    console.warn(`[llm] generation failed (${(err as Error).name}), using template fallback`);
    return null;
  }
}

function loadTemplatePool(): Record<string, Scenario[]> {
  const pool: Record<string, Scenario[]> = {};
  for (const tactic of TACTICS) {
    const dir = path.join(templatesDir(), tactic);
    if (!fs.existsSync(dir)) continue;
    pool[tactic] = fs.readdirSync(dir)
      .filter((f) => f.endsWith(".json"))
      .sort()
      .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8")) as Scenario);
  }
  return pool;
}

export function templateFallback(tactic: string): Scenario {
  const pool = loadTemplatePool();
  const choices = pool[tactic];
  if (!choices || choices.length === 0) {
    throw new Error(`no templates available for tactic '${tactic}'`);
  }
  const pick = choices[Math.floor(Math.random() * choices.length)];
  return { ...pick, generation_source: "template" };
}

/** Generate one scenario: LLM -> shape check -> template fallback. */
export async function generateScenario(opts: {
  tactic: string; difficulty: number; role: string; department: string;
  recentSubjects: string[]; company?: string; style?: string;
}): Promise<Scenario> {
  const company = opts.company ?? FICTIONAL_COMPANIES[Math.floor(Math.random() * FICTIONAL_COMPANIES.length)];
  const style = opts.style ?? STYLE_SEEDS[Math.floor(Math.random() * STYLE_SEEDS.length)];

  for (let attempt = 0; attempt < 3; attempt++) {
    const raw = await groqGenerate(buildUserPrompt({ ...opts, company, style }));
    if (raw && minimalShapeCheck(raw)) {
      return { ...raw, company, generation_source: "llm" };
    }
  }
  return templateFallback(opts.tactic);
}