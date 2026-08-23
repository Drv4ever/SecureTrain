import { useState } from "react";

const STEPS = [
  {
    title: "This is SecureTrain",
    body: "An adaptive security trainer. Its one job: find out which scam style each person falls for — then train them on exactly that.",
  },
  {
    title: "Pick an employee",
    body: "Every employee hides a secret weakness (one of the 4 scam styles). The agent can't see it — it has to discover it through rounds.",
  },
  {
    title: "You play the employee",
    body: "On the Training screen choose “You (live demo)”. Each round the agent writes a fake email and shows it to you. React honestly with one of the 4 buttons.",
  },
  {
    title: "Watch it learn",
    body: "The bars are the agent's beliefs per tactic. The highest bar = its best guess at your weakness. It explores uncertain tactics first, then hones in.",
  },
  {
    title: "See the evidence",
    body: "The Analytics tab runs the same experiment over 100 simulated employees and shows Thompson Sampling beating random selection.",
  },
];

const DONE_KEY = "securetrain_tour_done";

export function Tour() {
  const [open, setOpen] = useState(() => !localStorage.getItem(DONE_KEY));
  const [step, setStep] = useState(0);

  if (!open) return null;
  const current = STEPS[step];

  const close = () => {
    localStorage.setItem(DONE_KEY, "1");
    setOpen(false);
  };

  return (
    <div className="tour-backdrop" onClick={close}>
      <div className="tour-card" onClick={(e) => e.stopPropagation()}>
        <h2>{current.title}</h2>
        <p className="page-sub">{current.body}</p>
        <div className="row">
          <button className="btn ghost" onClick={close}>Skip</button>
          <div className="spacer" />
          <div className="tour-dots">
            {STEPS.map((_, i) => (
              <span key={i} className={i === step ? "on" : ""} />
            ))}
          </div>
          {step > 0 && (
            <button className="btn" onClick={() => setStep(step - 1)}>Back</button>
          )}
          {step < STEPS.length - 1 ? (
            <button className="btn primary" onClick={() => setStep(step + 1)}>Next</button>
          ) : (
            <button className="btn primary" onClick={close}>Let's go</button>
          )}
        </div>
      </div>
    </div>
  );
}