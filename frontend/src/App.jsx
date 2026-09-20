import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Home from "./pages/Home.jsx";
import Ledger from "./pages/Ledger.jsx";
import Ask from "./pages/Ask.jsx";
import Risk from "./pages/Risk.jsx";

const navLinkClass = ({ isActive }) => `nav-link ${isActive ? "active" : ""}`;

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="navbar">
          <div className="brand">
            <span className="brand-dot"></span>
            VoiceLedger
          </div>
          <nav className="nav-tabs">
            <NavLink to="/" className={navLinkClass}>Home</NavLink>
            <NavLink to="/ledger" className={navLinkClass}>Ledger</NavLink>
            <NavLink to="/ask" className={navLinkClass}>Ask</NavLink>
            <NavLink to="/risk" className={navLinkClass}>Risk</NavLink>
          </nav>
        </header>

        <main className="container">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/ledger" element={<Ledger />} />
            <Route path="/ask" element={<Ask />} />
            <Route path="/risk" element={<Risk />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}