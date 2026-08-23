// database/init.js - create indexes (run before seed.js).
// Uses backend's mongodb driver via createRequire so no duplicate installs.
const { createRequire } = require("module");
const path = require("path");
const requireFromBackend = createRequire(require.resolve("../backend/package.json"));
const { MongoClient } = requireFromBackend("mongodb");
requireFromBackend("dotenv").config({ path: path.resolve(__dirname, "../.env") });

const MONGODB_URI = process.env.MONGO_URI || "mongodb://localhost:27017";
const DB = process.env.DB_NAME || "securetrain";

async function main() {
  const client = new MongoClient(MONGODB_URI);
  await client.connect();
  const db = client.db(DB);

  await db.collection("employees").createIndex({ role: 1, department: 1 });
  await db.collection("rounds").createIndex({ session_id: 1, round_no: 1 }, { unique: true });
  await db.collection("scenarios").createIndex({ content_hash: 1 });
  await db.collection("scenarios").createIndex({ session_id: 1, round_no: 1 }, { unique: true });
  await db.collection("training_sessions").createIndex({ employee_id: 1, status: 1 });

  console.log("indexes ready on db:", DB);
  await client.close();
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});