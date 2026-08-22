import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { HOTEL_NAME } from "./config/brand";
import Chat from "./routes/Chat";
import Inbox from "./routes/Inbox";
import Ops from "./routes/Ops";

/**
 * Application shell.
 *
 * Routing/landmarks scaffolded by @project.mgr (*setup-project); real
 * UI/UX is @frontend.eng's responsibility. The brand mark below is
 * deliberately not an <h1> — each route supplies the page's one <h1>
 * (SC 1.3.1/2.4.6) so this doesn't create a second, competing heading
 * on every page.
 */
export default function App() {
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <header className="site-header">
        <span className="site-header__brand">{HOTEL_NAME}</span>
        <nav aria-label="Primary">
          <NavLink to="/chat">Chat</NavLink>
          <NavLink to="/inbox">Inbox</NavLink>
          <NavLink to="/ops">Ops</NavLink>
        </nav>
      </header>
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
