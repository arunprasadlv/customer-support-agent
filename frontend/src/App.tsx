import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import Chat from "./routes/Chat";
import Inbox from "./routes/Inbox";
import Ops from "./routes/Ops";

/**
 * Application shell (scaffold only).
 *
 * Scaffolded by @project.mgr (*setup-project): routing + placeholder
 * pages for the three planned surfaces (sad.md SS3 Application
 * Structure). Real UI/UX is @frontend.eng's responsibility.
 */
export default function App() {
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <nav aria-label="Primary">
        <NavLink to="/chat">Chat</NavLink>
        <NavLink to="/inbox">Inbox</NavLink>
        <NavLink to="/ops">Ops</NavLink>
      </nav>
      <main id="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/inbox" element={<Inbox />} />
          <Route path="/ops" element={<Ops />} />
        </Routes>
      </main>
    </>
  );
}
