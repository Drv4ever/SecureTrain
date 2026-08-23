/** Central configuration. Env vars come from the repo-root .env or backend/.env. */

import dotenv from "dotenv";
import fs from "fs";
import path from "path";

/** Walk up from a start dir until we find the repo root (contains backend/ + prompts/). */
function findRepoRoot(start: string): string {
  let dir = start;
  while (dir !== path.dirname(dir)) {
    if (fs.existsSync(path.join(dir, "backend")) && fs.existsSync(path.join(dir, "prompts"))) {
      return dir;
    }
    dir = path.dirname(dir);
  }
  return start;
}

const repoRoot = findRepoRoot(__dirname);
dotenv.config({ path: path.join(repoRoot, ".env") });
dotenv.config();

export const config = {
  port: Number(process.env.BACKEND_PORT ?? 4000),
  mongoUri: process.env.MONGO_URI ?? "mongodb://localhost:27017",
  dbName: process.env.DB_NAME ?? "securetrain",
  aiServiceUrl: process.env.AI_SERVICE_URL ?? "http://localhost:8000",
  groqApiKey: process.env.GROQ_API_KEY ?? "",
  groqModelBulk: process.env.GROQ_MODEL_BULK ?? "llama-3.1-8b-instant",
  groqModelDemo: process.env.GROQ_MODEL_DEMO ?? "llama-3.3-70b-versatile",
  freshnessThreshold: Number(process.env.FRESHNESS_THRESHOLD ?? 0.85),
  promptsDir: path.join(repoRoot, "prompts"),
  // difficulty is fixed so true arm means stay constant (regret stays well-defined)
  defaultDifficulty: 3,
};