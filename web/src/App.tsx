import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import TextToSpeech from "./pages/TextToSpeech";
import Voices from "./pages/Voices";
import SpeechToText from "./pages/SpeechToText";
import VoiceChanger from "./pages/VoiceChanger";
import SoundEffects from "./pages/SoundEffects";
import VoiceIsolator from "./pages/VoiceIsolator";
import Dubbing from "./pages/Dubbing";
import DubbingProject from "./pages/DubbingProject";
import History from "./pages/History";
import Settings from "./pages/Settings";

const NAV = [
  { group: "Create", items: [
    { to: "/", label: "Text to Speech", icon: "Aa" },
    { to: "/voice-changer", label: "Voice Changer", icon: "⇄" },
    { to: "/sound-effects", label: "Sound Effects", icon: "♫" },
    { to: "/dubbing", label: "Dubbing", icon: "◎" },
  ]},
  { group: "Audio tools", items: [
    { to: "/speech-to-text", label: "Speech to Text", icon: "✎" },
    { to: "/voice-isolator", label: "Voice Isolator", icon: "◐" },
  ]},
  { group: "Library", items: [
    { to: "/voices", label: "Voices", icon: "☺" },
    { to: "/history", label: "History", icon: "⟲" },
    { to: "/settings", label: "Settings & API", icon: "⚙" },
  ]},
];

export default function App() {
  const [menu, setMenu] = useState(false);
  const loc = useLocation();
  useEffect(() => setMenu(false), [loc.pathname]);
  return (
    <div className="app">
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <div className="brand">
          <img src="/logo.svg" alt="" width={30} height={30} />
          <span>Kontho</span>
          <span className="badge">open source</span>
        </div>
        <nav>
          {NAV.map((g) => (
            <div key={g.group} className="nav-group">
              <div className="nav-title">{g.group}</div>
              {g.items.map((i) => (
                <NavLink key={i.to} to={i.to} end={i.to === "/"} className="nav-link">
                  <span className="nav-icon">{i.icon}</span>
                  {i.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot muted small">
          <a href="/docs" target="_blank" rel="noreferrer">API docs</a> ·{" "}
          <a href="https://github.com" target="_blank" rel="noreferrer">GitHub</a>
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <button className="icon-btn" onClick={() => setMenu(!menu)} aria-label="Menu">☰</button>
          <img src="/logo.svg" alt="" width={24} height={24} />
          <strong>Kontho</strong>
        </div>
        {menu && <div className="scrim" onClick={() => setMenu(false)} />}
        <main className="content">
          <Routes>
            <Route path="/" element={<TextToSpeech />} />
            <Route path="/voices" element={<Voices />} />
            <Route path="/speech-to-text" element={<SpeechToText />} />
            <Route path="/voice-changer" element={<VoiceChanger />} />
            <Route path="/sound-effects" element={<SoundEffects />} />
            <Route path="/voice-isolator" element={<VoiceIsolator />} />
            <Route path="/dubbing" element={<Dubbing />} />
            <Route path="/dubbing/:id" element={<DubbingProject />} />
            <Route path="/history" element={<History />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<TextToSpeech />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
