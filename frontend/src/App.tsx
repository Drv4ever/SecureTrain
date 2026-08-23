import { NavLink, Route, Routes } from "react-router-dom";
import Employees from "./screens/Employees";
import Training from "./screens/Training";
import Analytics from "./screens/Analytics";
import { Tour } from "./components/Tour";

export default function App() {
  return (
    <>
      <Tour />
      <header className="topbar">
        <div className="brand">
          Secure<span>Train</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>Employees</NavLink>
          <NavLink to="/training">Training</NavLink>
          <NavLink to="/analytics">Analytics</NavLink>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Employees />} />
        <Route path="/training/:employeeId?" element={<Training />} />
        <Route path="/analytics" element={<Analytics />} />
      </Routes>
    </>
  );
}