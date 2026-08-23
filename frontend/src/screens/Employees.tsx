import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Employee, listEmployees } from "../api";

export default function Employees() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    listEmployees()
      .then(setEmployees)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <h1 className="page-title">Employees</h1>
      <p className="page-sub">
        Synthetic workforce. Each employee hides a vulnerability profile that the
        agent must discover through training rounds.
      </p>

      {error && <div className="error">{error}</div>}
      {loading && <div className="empty">loading…</div>}

      <div className="grid">
        {employees.map((emp) => (
          <div key={emp._id} className="emp" onClick={() => navigate(`/training/${emp._id}`)}>
            <div className="code">{emp.code}</div>
            <div className="meta">
              {emp.role} · {emp.department}
            </div>
            <div className="foot">
              <span>alertness {emp.base_alertness.toFixed(2)}</span>
              <span className="badge plain">train →</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}