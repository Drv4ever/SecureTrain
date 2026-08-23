// database/seed.js - populate MongoDB with the canonical synthetic workforce.
// Run: node database/seed.js  (requires the Python service running for /employee/generate)
const { createRequire } = require("module");
const path = require("path");
const requireFromBackend = createRequire(require.resolve("../backend/package.json"));
const { MongoClient } = requireFromBackend("mongodb");
requireFromBackend("dotenv").config({ path: path.resolve(__dirname, "../.env") });

const MONGODB_URI = process.env.MONGO_URI || "mongodb://localhost:27017";
const DB = process.env.DB_NAME || "securetrain";
const AI = process.env.AI_SERVICE_URL || "http://localhost:8000";

async function main() {
  const response = await fetch(`${AI}/employee/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ count_per_combo: 4, seed: 42 }),
  });
  if (!response.ok) {
    throw new Error(
      `ai /employee/generate failed (${response.status}). Start the Python service first: uvicorn api:app --port 8000`,
    );
  }
  const { employees } = await response.json();

  const client = new MongoClient(MONGODB_URI);
  await client.connect();
  const db = client.db(DB);

  await db.collection("employees").deleteMany({});
  await db.collection("employees").insertMany(employees);
  console.log(`seeded ${employees.length} employees into ${DB}`);
  await client.close();
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});