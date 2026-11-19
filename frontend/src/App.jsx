import { useEffect, useRef, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import "./App.css";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseKey =
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
const apiUrl = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const supabase =
  supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null;

async function apiFetch(path, options = {}) {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token)
    throw new Error("Your session has expired. Please log in again.");
  const response = await fetch(`${apiUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...options.headers,
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail || detail;
    } catch {
      /* status text */
    }
    throw new Error(detail);
  }
  return response;
}

function AuthScreen() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const result =
      mode === "login"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    setBusy(false);
    if (result.error) setError(result.error.message);
    else if (mode === "signup" && !result.data.session)
      setNotice("Check your email to confirm your account, then log in.");
  }
  return (
    <main className="auth-shell">
      <section className="auth-card">
        <div className="brand-mark">
          L<span>×</span>
        </div>
        <p className="eyebrow">LEXRAG</p>
        <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p className="auth-copy">Your intelligent legal research companion.</p>
        <form onSubmit={submit}>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength="6"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          {notice && <p className="form-notice">{notice}</p>}
          <button className="primary-button" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
          </button>
        </form>
        <button
          className="switch-button"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setError("");
            setNotice("");
          }}
        >
          {mode === "login"
            ? "New to LexRAG? Create an account"
            : "Already have an account? Log in"}
        </button>
      </section>
    </main>
  );
}

function Thinking({ items, streaming }) {
  const [open, setOpen] = useState(streaming); // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    if (streaming) setOpen(true);
  }, [streaming]);
  if (!items.length) return null;
  return (
    <div className="thinking-block">
      <button
        className="thinking-toggle"
        onClick={() => setOpen((value) => !value)}
      >
        <span className={streaming ? "thinking-dot active" : "thinking-dot"} />
        <span>{streaming ? "Thinking…" : "Thought process"}</span>
        <span className="chevron">{open ? "⌃" : "⌄"}</span>
      </button>
      {open && (
        <div className="thinking-list">
          {items.map((item, index) => (
            <div className="thinking-item" key={`${item.tool}-${index}`}>
              <span className={item.done ? "step-icon done" : "step-icon"}>
                {item.done ? "✓" : "·"}
              </span>
              <div>
                <strong>{item.tool}</strong>
                <code>{JSON.stringify(item.args)}</code>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);
  // These effects synchronize the React state with Supabase's external auth session.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    if (!supabase) {
      setReady(true);
      return undefined;
    }
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user || null);
      setReady(true);
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) =>
      setUser(session?.user || null),
    );
    return () => subscription.unsubscribe();
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    if (!user) {
      setSessions([]);
      setActiveId(null);
      setMessages([]);
      return;
    }
    loadSessions();
    apiFetch("/users/sync", {
      method: "POST",
      body: JSON.stringify({ username: user.email || user.id }),
    }).catch(() => {});
  }, [user]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);
  async function loadSessions() {
    try {
      setSessions(await (await apiFetch("/sessions")).json());
    } catch (e) {
      setError(e.message);
    }
  }
  async function selectSession(id) {
    setActiveId(id);
    setError("");
    try {
      setMessages(
        (await (await apiFetch(`/sessions/${id}/messages`)).json()).map(
          (message) => ({ ...message, thinking: [] }),
        ),
      );
    } catch (e) {
      setError(e.message);
    }
  }
  function newChat() {
    setActiveId(null);
    setMessages([]);
    setPrompt("");
    setError("");
  }
  async function sendPrompt(event) {
    event?.preventDefault();
    const query = prompt.trim();
    if (!query || streaming) return;
    setPrompt("");
    setError("");
    setStreaming(true);
    let threadId = activeId;
    setMessages((current) => [
      ...current,
      { role: "user", content: query, thinking: [] },
      { role: "agent", content: "", thinking: [] },
    ]);
    try {
      if (!threadId) {
        const created = await (
          await apiFetch("/sessions", {
            method: "POST",
            body: JSON.stringify({ query }),
          })
        ).json();
        threadId = created.session_id;
        setActiveId(threadId);
        setSessions((current) => [
          { ...created, updated_at: new Date().toISOString() },
          ...current,
        ]);
      }
      const response = await apiFetch("/agent/chat", {
        method: "POST",
        body: JSON.stringify({ query, thread_id: threadId }),
      });
      if (!response.body)
        throw new Error("The server did not return a stream.");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const handle = (eventText) => {
        const lines = eventText.split("\n");
        const type = lines
          .find((line) => line.startsWith("event:"))
          ?.slice(6)
          .trim();
        const dataLine = lines.find((line) => line.startsWith("data:"));
        if (!type || !dataLine) return;
        const data = JSON.parse(dataLine.slice(5).trim());
        if (type === "message")
          setMessages((current) =>
            current.map((message, index) =>
              index === current.length - 1
                ? { ...message, content: message.content + data.text }
                : message,
            ),
          );
        if (type === "thinking_start")
          setMessages((current) =>
            current.map((message, index) =>
              index === current.length - 1
                ? {
                    ...message,
                    thinking: [
                      ...message.thinking,
                      { tool: data.tool, args: data.args, done: false },
                    ],
                  }
                : message,
            ),
          );
        if (type === "thinking_end")
          setMessages((current) =>
            current.map((message, index) =>
              index === current.length - 1
                ? {
                    ...message,
                    thinking: message.thinking.map((item, itemIndex) =>
                      itemIndex ===
                      message.thinking.findLastIndex(
                        (entry) => entry.tool === data.tool,
                      )
                        ? { ...item, done: true }
                        : item,
                    ),
                  }
                : message,
            ),
          );
        if (type === "error") throw new Error(data.error);
      };
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        parts.forEach(handle);
        if (done) break;
      }
      if (buffer.trim()) handle(buffer);
      await loadSessions();
    } catch (e) {
      setError(e.message);
      setMessages((current) =>
        current.map((message, index) =>
          index === current.length - 1 && !message.content
            ? { ...message, content: "I couldn’t complete that request." }
            : message,
        ),
      );
    } finally {
      setStreaming(false);
    }
  }
  if (!supabase)
    return (
      <div className="config-error">
        Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to start LexRAG.
      </div>
    );
  if (!ready) return <div className="loading-screen">Loading LexRAG…</div>;
  if (!user) return <AuthScreen />;
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="brand-lockup">
            <div className="brand-mark small">
              L<span>×</span>
            </div>
            <span>LexRAG</span>
          </div>
          <button className="new-chat" onClick={newChat}>
            <span>＋</span> New chat
          </button>
        </div>
        <div className="session-heading">Your conversations</div>
        <nav className="sessions">
          {sessions.map((session) => (
            <button
              key={session.session_id}
              className={
                activeId === session.session_id ? "session active" : "session"
              }
              onClick={() => selectSession(session.session_id)}
            >
              <span className="session-icon">◌</span>
              <span>{session.title}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="user-chip">
            <div className="avatar">{(user.email || "U")[0].toUpperCase()}</div>
            <span title={user.email}>{user.email}</span>
          </div>
          <button className="logout" onClick={() => supabase.auth.signOut()}>
            <span>↪</span> Log out
          </button>
        </div>
      </aside>
      <section className="chat-panel">
        <header className="topbar">
          <span className="mobile-brand">LexRAG</span>
          <span className="status-pill">
            <span /> Legal research assistant
          </span>
        </header>
        <div className="message-scroll">
          <div className={messages.length ? "conversation" : "empty-state"}>
            {!messages.length && (
              <>
                <div className="welcome-mark">
                  L<span>×</span>
                </div>
                <h1>What can I help you research?</h1>
                <p>Ask about Indian law, statutes, and legal concepts.</p>
                <div className="suggestions">
                  <button
                    onClick={() =>
                      setPrompt(
                        "Explain the essentials of a valid contract under Indian law.",
                      )
                    }
                  >
                    Essentials of a valid contract
                  </button>
                  <button
                    onClick={() =>
                      setPrompt("What are the remedies for breach of contract?")
                    }
                  >
                    Remedies for breach of contract
                  </button>
                </div>
              </>
            )}
            {messages.map((message, index) => (
              <article
                className={`message ${message.role}`}
                key={`${message.created_at || "live"}-${index}`}
              >
                <div className="message-label">
                  {message.role === "user" ? "You" : "LexRAG"}
                </div>
                {message.role === "agent" && (
                  <Thinking
                    items={message.thinking}
                    streaming={streaming && index === messages.length - 1}
                  />
                )}
                <div className="message-content">
                  {message.content ||
                    (streaming && index === messages.length - 1 ? (
                      <span className="typing">
                        <i />
                        <i />
                        <i />
                      </span>
                    ) : (
                      ""
                    ))}
                </div>
              </article>
            ))}
          </div>
          <div ref={bottomRef} />
        </div>
        {error && <div className="error-toast">{error}</div>}
        <form className="composer-wrap" onSubmit={sendPrompt}>
          <div className="composer">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendPrompt(event);
                }
              }}
              placeholder="Ask a legal question…"
              rows="1"
              aria-label="Ask a legal question"
            />
            <button
              className="send-button"
              type="submit"
              disabled={!prompt.trim() || streaming}
              aria-label="Send prompt"
            >
              {streaming ? <span className="stop-square" /> : "↑"}
            </button>
          </div>
          <p className="composer-note">
            LexRAG can make mistakes. Verify important legal information.
          </p>
        </form>
      </section>
    </main>
  );
}

export default App;
