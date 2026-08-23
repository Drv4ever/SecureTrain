/** Express entry point. */

import cors from "cors";
import express from "express";
import "express-async-errors"; // forwards async handler rejections to the error middleware
import { config } from "./config";
import { connectDb, dbReady } from "./db";
import employeesRouter from "./routes/employees";
import trainingRouter from "./routes/training";
import analyticsRouter from "./routes/analytics";

const app = express();
app.use(cors());
app.use(express.json({ limit: "2mb" }));

app.use("/api", employeesRouter);
app.use("/api", trainingRouter);
app.use("/api", analyticsRouter);

app.get("/healthz", async (_req, res) => {
  const ai = await fetch(`${config.aiServiceUrl}/healthz`)
    .then((r) => r.json())
    .then((body) => body.status)
    .catch(() => "unreachable");
  res.json({ status: "ok", db: dbReady() ? "ok" : "down", ai });
});

// global error handler: a bad request must never take the process down
app.use((err: any, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  const badInput = err?.name === "CastError" || err?.name === "ValidationError";
  console.error(`[error] ${badInput ? "bad request" : err?.message ?? err}`);
  res.status(badInput ? 400 : 500).json({ error: err?.message ?? "internal error" });
});

async function main() {
  await connectDb();
  console.log(`[db] connected to ${config.dbName}`);
  app.listen(config.port, () => {
    console.log(`[server] listening on http://localhost:${config.port}`);
  });
}

main().catch((err) => {
  console.error("startup failed:", err);
  process.exit(1);
});