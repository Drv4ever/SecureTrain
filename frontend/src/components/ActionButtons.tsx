import type { Response } from "../api";

const LABELS: { value: Response; label: string; className: string }[] = [
  { value: "ignore", label: "Ignore", className: "" },
  { value: "report", label: "Report", className: "ok" },
  { value: "click", label: "Click link", className: "danger" },
  { value: "credentials", label: "Enter credentials", className: "danger" },
];

/** The four actions the employee (human mode) can take on a scenario. */
export function ActionButtons({
  onResponse,
  disabled,
}: {
  onResponse: (response: Response) => void;
  disabled?: boolean;
}) {
  const confirmDanger = (value: Response, label: string) => {
    if (value === "ignore" || value === "report" || window.confirm(`Submit "${label}"?`)) {
      onResponse(value);
    }
  };

  return (
    <div className="actions">
      {LABELS.map(({ value, label, className }) => (
        <button
          key={value}
          className={`act ${className}`}
          disabled={disabled}
          onClick={() => confirmDanger(value, label)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}