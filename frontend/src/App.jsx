import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home.jsx";
import Ledger from "./pages/Ledger.jsx";
import Ask from "./pages/Ask.jsx";
import Risk from "./pages/Risk.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <Link to="/">Home</Link> | <Link to="/ledger">Ledger</Link> |{" "}
        <Link to="/ask">Ask</Link> | <Link to="/risk">Risk</Link>
      </nav>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/ledger" element={<Ledger />} />
        <Route path="/ask" element={<Ask />} />
        <Route path="/risk" element={<Risk />} />
      </Routes>
    </BrowserRouter>
  );
}