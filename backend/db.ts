/** MongoDB connection and all collections (docs/BLUEPRINT.md, section 11). */

import mongoose, { Schema, model, models } from "mongoose";
import { config } from "./config";

export async function connectDb(): Promise<void> {
  await mongoose.connect(config.mongoUri, { dbName: config.dbName });
}

export const dbReady = () => mongoose.connection.readyState === 1;

// ---------- employees ----------

const susceptibilitySchema = new Schema(
  {
    urgency: { type: Number, required: true },
    authority: { type: Number, required: true },
    invoice: { type: Number, required: true },
    credential: { type: Number, required: true },
  },
  { _id: false },
);

const employeeSchema = new Schema(
  {
    code: { type: String, required: true, unique: true },
    role: { type: String, required: true },
    department: { type: String, required: true },
    base_alertness: { type: Number, required: true },
    susceptibility: { type: susceptibilitySchema, required: true }, // HIDDEN ground truth
    created_at: { type: Date, default: Date.now },
  },
  { collection: "employees" },
);

// ---------- training_sessions ----------

const sessionSchema = new Schema(
  {
    employee_id: { type: Schema.Types.ObjectId, ref: "Employee", required: true },
    selector: { type: String, enum: ["thompson", "random", "epsilon_greedy"], required: true },
    behavior_source: { type: String, enum: ["classifier", "probabilistic", "human"], required: true },
    mode: { type: String, enum: ["evaluation", "demo"], default: "evaluation" },
    status: { type: String, enum: ["running", "complete"], default: "running" },
    n_rounds: { type: Number, default: 300 },
    difficulty: { type: Number, default: 3 },
    seed: { type: Number, default: 1 },
    started_at: { type: Date, default: Date.now },
    finished_at: { type: Date },
  },
  { collection: "training_sessions" },
);

// ---------- scenarios ----------

const scenarioSchema = new Schema(
  {
    session_id: { type: Schema.Types.ObjectId, ref: "TrainingSession", required: true },
    round_no: { type: Number, required: true },
    tactic: { type: String, required: true },
    difficulty: { type: Number, required: true },
    sender_name: { type: String, required: true },
    sender_email: { type: String, required: true },
    subject: { type: String, required: true },
    body: { type: String, required: true },
    indicators: { type: [String], default: [] },
    hook: { type: String, default: "" },
    company: { type: String, default: "" },
    content_hash: { type: String, required: true },
    generation_source: { type: String, enum: ["llm", "template"], default: "template" },
    freshness: { max_cosine: Number, passed: Boolean },
    created_at: { type: Date, default: Date.now },
  },
  { collection: "scenarios" },
);

// ---------- rounds ----------

const responseSchema = new Schema(
  {
    response: { type: String, required: true },
    probs: { type: Object, default: {} },
    source: { type: String, enum: ["classifier", "probabilistic", "human"], required: true },
  },
  { _id: false },
);

const rewardSchema = new Schema(
  {
    detection: { type: Number, required: true }, // drives the bandit (Design A)
    safety: { type: Number, required: true },    // reported metric only
  },
  { _id: false },
);

const roundSchema = new Schema(
  {
    session_id: { type: Schema.Types.ObjectId, ref: "TrainingSession", required: true },
    employee_id: { type: Schema.Types.ObjectId, ref: "Employee", required: true },
    round_no: { type: Number, required: true },
    tactic_selected: { type: String, required: true },
    scenario_id: { type: Schema.Types.ObjectId, ref: "Scenario" },
    status: { type: String, enum: ["completed", "pending_human"], default: "completed" },
    response: { type: responseSchema, default: null },
    reward: { type: rewardSchema, default: null },
    bandit_after: { type: Object, default: {} },
    created_at: { type: Date, default: Date.now },
  },
  { collection: "rounds" },
);
roundSchema.index({ session_id: 1, round_no: 1 }, { unique: true });

// ---------- bandit_state ----------

const armStateSchema = new Schema(
  { alpha: { type: Number, required: true }, beta: { type: Number, required: true }, pulls: { type: Number, default: 0 } },
  { _id: false },
);

const banditStateSchema = new Schema(
  {
    session_id: { type: Schema.Types.ObjectId, ref: "TrainingSession", required: true, unique: true },
    arms: { type: Object, default: {} },
    total_rounds: { type: Number, default: 0 },
    updated_at: { type: Date, default: Date.now },
  },
  { collection: "bandit_state" },
);

// ---------- analytics (materialized aggregates) ----------

const analyticsSchema = new Schema(
  {
    scope: { type: String, enum: ["session", "employee", "global"], required: true },
    ref_id: { type: Schema.Types.ObjectId },
    selector: { type: String },
    metrics: { type: Object, default: {} },
    computed_at: { type: Date, default: Date.now },
  },
  { collection: "analytics" },
);

export type EmployeeDoc = {
  _id: mongoose.Types.ObjectId;
  code: string;
  role: string;
  department: string;
  base_alertness: number;
  susceptibility: { urgency: number; authority: number; invoice: number; credential: number };
};

export const Employee = models.Employee || model("Employee", employeeSchema);
export const TrainingSession = models.TrainingSession || model("TrainingSession", sessionSchema);
export const Scenario = models.Scenario || model("Scenario", scenarioSchema);
export const Round = models.Round || model("Round", roundSchema);
export const BanditState = models.BanditState || model("BanditState", banditStateSchema);
export const Analytics = models.Analytics || model("Analytics", analyticsSchema);