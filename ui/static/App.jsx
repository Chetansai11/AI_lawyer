const { useState, useEffect, useRef, useCallback } = React;

const SESSION_KEY = "ai_intake_auditor_session_id";

function useSessionId() {
  const [sessionId, setSessionIdState] = useState(() => sessionStorage.getItem(SESSION_KEY) || null);

  const setSessionId = useCallback((id) => {
    if (id) sessionStorage.setItem(SESSION_KEY, id);
    else sessionStorage.removeItem(SESSION_KEY);
    setSessionIdState(id);
  }, []);

  return [sessionId, setSessionId];
}

function BriefPane({ markdown }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!markdown || typeof marked === "undefined" || typeof DOMPurify === "undefined") {
      el.innerHTML = "";
      if (!markdown) {
        el.innerHTML =
          '<p class="text-slate-500 text-center py-12">Your live attorney brief will appear here as the agent updates.</p>';
      }
      return;
    }
    const html = marked.parse(markdown, { mangle: false, headerIds: false });
    el.innerHTML = DOMPurify.sanitize(html);
  }, [markdown]);

  return <div ref={ref} className="brief-prose" />;
}

function AgentWelcomeBubble({ loading, text }) {
  return (
    <div className="mr-auto max-w-[95%] shrink-0 rounded-2xl border border-blue-500/20 bg-gradient-to-br from-firm-950/95 to-blue-950/30 px-4 py-4 text-[15px] leading-relaxed text-slate-200 shadow-lg shadow-blue-950/20">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-blue-400/90">AI Intake Auditor</div>
      {loading ? (
        <div className="space-y-2 animate-pulse">
          <div className="h-4 w-full max-w-md rounded bg-slate-700/50" />
          <div className="h-4 w-full max-w-sm rounded bg-slate-700/40" />
          <div className="h-4 w-2/3 max-w-xs rounded bg-slate-700/35" />
          <p className="pt-2 text-xs text-slate-500">Preparing your intake assistant…</p>
        </div>
      ) : (
        <div className="whitespace-pre-wrap text-slate-200">{text}</div>
      )}
    </div>
  );
}

function App() {
  const [sessionId, setSessionId] = useSessionId();
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [briefMd, setBriefMd] = useState("");
  const [logs, setLogs] = useState([]);
  const [sending, setSending] = useState(false);
  const [toast, setToast] = useState(null);
  const [showLogs, setShowLogs] = useState(true);
  const [lawyerMatches, setLawyerMatches] = useState([]);
  /** Latest counsel-only metrics (not shown in chat or client brief); one panel updates in place. */
  const [counselTriage, setCounselTriage] = useState(null);
  const [welcomeText, setWelcomeText] = useState("");
  const [welcomeLoading, setWelcomeLoading] = useState(true);
  const [selectedLawyer, setSelectedLawyer] = useState(null);
  const [lawyerModalOpen, setLawyerModalOpen] = useState(false);
  const [shareBusy, setShareBusy] = useState(false);
  const [apptBusy, setApptBusy] = useState(false);
  const [apptEmail, setApptEmail] = useState("");
  const [apptPhone, setApptPhone] = useState("");
  const [apptTimes, setApptTimes] = useState("");
  const [apptNote, setApptNote] = useState("");

  const messagesEndRef = useRef(null);
  const toastTimer = useRef(null);

  const showToast = useCallback((message, isError) => {
    setToast({ message, isError: !!isError });
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 4500);
  }, []);

  useEffect(() => {
    return () => {
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
    };
  }, []);

  const loadWelcome = useCallback(async () => {
    setWelcomeLoading(true);
    setWelcomeText("");
    try {
      const res = await fetch("/welcome");
      if (!res.ok) throw new Error("welcome failed");
      const data = await res.json();
      setWelcomeText(typeof data.message === "string" ? data.message : "");
    } catch {
      setWelcomeText(
        "Hi — I'm here to help with your legal intake.\n\nTell me what happened in your own words. I'll ask one follow-up at a time and keep a brief on the right for your lawyer.\n\nType below and press Send or Enter to start."
      );
    } finally {
      setWelcomeLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWelcome();
  }, [loadWelcome]);

  useEffect(() => {
    if (messages.length === 0 && !sending) return;
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const sendMessage = async (e) => {
    e?.preventDefault?.();
    const text = draft.trim();
    if (!text || sending) return;

    setSending(true);
    setDraft("");
    setMessages((m) => [...m, { role: "user", content: text }]);

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        let detail = err.detail;
        if (Array.isArray(detail)) {
          detail = detail.map((x) => x.msg || JSON.stringify(x)).join("; ");
        }
        throw new Error(detail || `${res.status} ${res.statusText}`);
      }

      const data = await res.json();
      setSessionId(data.session_id);
      setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
      setBriefMd(data.brief || "");
      setLogs(Array.isArray(data.logs) ? data.logs : []);
      setLawyerMatches(Array.isArray(data.lawyer_matches) ? data.lawyer_matches : []);
      const cs = data.case_score;
      const cf = data.confidence_score;
      const scoreN = typeof cs === "number" ? cs : parseFloat(cs);
      const confN = typeof cf === "number" ? cf : parseFloat(cf);
      if (!Number.isNaN(scoreN) || !Number.isNaN(confN)) {
        setCounselTriage({
          caseScore: Number.isNaN(scoreN) ? null : scoreN,
          confidence: Number.isNaN(confN) ? null : confN,
        });
      }
    } catch (err) {
      showToast(err.message || "Request failed", true);
      setMessages((m) => m.slice(0, -1));
      setDraft(text);
    } finally {
      setSending(false);
    }
  };

  const openLawyer = (law) => {
    setSelectedLawyer(law);
    setLawyerModalOpen(true);
  };

  const closeLawyer = () => {
    setLawyerModalOpen(false);
    setSelectedLawyer(null);
    setApptEmail("");
    setApptPhone("");
    setApptTimes("");
    setApptNote("");
  };

  const sendBriefToLawyer = async () => {
    if (!selectedLawyer) return;
    if (!briefMd) {
      showToast("No brief yet — send a message first.", true);
      return;
    }
    setShareBusy(true);
    try {
      const res = await fetch("/share-brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          lawyer_name: selectedLawyer.name || "",
          lawyer_email: selectedLawyer.contact_email || "",
          brief_markdown: briefMd,
          note: "Shared from AI Intake Auditor UI",
        }),
      });
      if (!res.ok) throw new Error("Share failed");
      const data = await res.json();
      showToast(`Brief queued to ${selectedLawyer.name}. Ref: ${data.reference_id}`);
    } catch (e) {
      showToast(e.message || "Share failed", true);
    } finally {
      setShareBusy(false);
    }
  };

  const requestAppointment = async () => {
    if (!selectedLawyer) return;
    setApptBusy(true);
    try {
      const res = await fetch("/book-appointment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          lawyer_name: selectedLawyer.name || "",
          lawyer_email: selectedLawyer.contact_email || "",
          client_email: apptEmail,
          client_phone: apptPhone,
          preferred_times: apptTimes,
          note: apptNote,
        }),
      });
      if (!res.ok) throw new Error("Request failed");
      const data = await res.json();
      showToast(`Appointment request sent. Ref: ${data.reference_id}`);
      closeLawyer();
    } catch (e) {
      showToast(e.message || "Request failed", true);
    } finally {
      setApptBusy(false);
    }
  };

  const newCase = () => {
    setSessionId(null);
    setMessages([]);
    setBriefMd("");
    setLogs([]);
    setDraft("");
    setLawyerMatches([]);
    setCounselTriage(null);
    loadWelcome();
    showToast("Fresh session — say hi with your story whenever you're ready.");
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header className="shrink-0 border-b border-white/10 px-4 py-4 md:px-8">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div
              className="flex h-11 w-11 items-center justify-center rounded-xl border border-blue-400/30 bg-gradient-to-br from-firm-800 to-firm-900 shadow-lg shadow-blue-900/40"
              aria-hidden
            >
              <span className="text-lg font-semibold tracking-tight text-blue-200">L</span>
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-white md:text-2xl">AI Intake Auditor</h1>
              <p className="text-xs text-slate-400 md:text-sm">Lawyer.com · Conversational legal intake</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 md:gap-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/35 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-40" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              Agent online
            </span>
            <div className="rounded-full border border-white/10 bg-firm-900/60 px-3 py-1 text-xs text-slate-400">
              Saved ~45m
            </div>
            <button
              type="button"
              onClick={newCase}
              className="rounded-lg border border-white/15 bg-firm-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-firm-700/80 md:text-sm"
            >
              New case
            </button>
          </div>
        </div>
      </header>

      {counselTriage && (counselTriage.caseScore != null || counselTriage.confidence != null) && (
        <details className="group shrink-0 border-b border-amber-500/20 bg-amber-950/20">
          <summary className="mx-auto max-w-[1600px] cursor-pointer list-none px-4 py-2 marker:content-none md:px-8 [&::-webkit-details-marker]:hidden">
            <span className="text-xs font-semibold text-amber-200/90">
              Counsel only — internal triage{" "}
              <span className="font-normal text-amber-200/50">(expand for score &amp; confidence)</span>
            </span>
          </summary>
          <div className="mx-auto max-w-[1600px] border-t border-amber-500/15 px-4 pb-3 pt-2 md:px-8">
            <p className="text-sm text-amber-100/95">
              <span className="text-amber-200/70">Case score:</span>{" "}
              <span className="font-semibold tabular-nums text-white">
                {counselTriage.caseScore != null ? counselTriage.caseScore.toFixed(1) : "—"}
              </span>
              <span className="text-slate-500"> /10</span>
              <span className="mx-2 text-slate-600">·</span>
              <span className="text-amber-200/70">Model confidence:</span>{" "}
              <span className="font-semibold tabular-nums text-white">
                {counselTriage.confidence != null ? counselTriage.confidence.toFixed(2) : "—"}
              </span>
            </p>
            <p className="mt-1 text-[11px] text-amber-200/55">
              Single internal readout (latest pipeline run). Omitted from intake chat and client brief.
            </p>
          </div>
        </details>
      )}

      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 px-4 py-4 md:px-8 md:py-5">
        <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-2 lg:gap-6">
          {/* Chat — fixed viewport band so messages scroll inside the card */}
          <section
            className="flex max-h-[calc(100dvh-12rem)] min-h-[420px] flex-col rounded-2xl border border-white/10 bg-firm-900/40 shadow-xl shadow-black/20 backdrop-blur-sm lg:min-h-[min(520px,calc(100dvh-12rem))]"
            aria-label="Conversation"
          >
            <div className="shrink-0 flex items-center justify-between border-b border-white/10 px-4 py-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Intake chat</h2>
              <span className="font-mono text-[10px] text-slate-500">
                {sessionId ? `···${sessionId.slice(-8)}` : "new"}
              </span>
            </div>
            <div
              className="min-h-0 flex-1 space-y-3 overflow-y-auto overflow-x-hidden overscroll-contain px-4 py-3"
              role="log"
              aria-live="polite"
              aria-relevant="additions"
            >
              {messages.length === 0 && (
                <AgentWelcomeBubble loading={welcomeLoading} text={welcomeText} />
              )}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={
                    "max-w-[95%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed " +
                    (msg.role === "user"
                      ? "ml-auto border border-blue-500/25 bg-blue-950/35 text-slate-100"
                      : "mr-auto border border-white/10 bg-firm-950/80 text-slate-200")
                  }
                >
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {msg.role === "user" ? "You" : "AI Intake Auditor"}
                  </div>
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                </div>
              ))}
              {sending && (
                <div className="mr-auto flex items-center gap-2 rounded-2xl border border-white/10 bg-firm-950/60 px-4 py-3 text-sm text-slate-400">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-blue-400" />
                  Agents running…
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <details className="shrink-0 border-t border-white/10 px-4 py-2" open={showLogs} onToggle={(e) => setShowLogs(e.target.open)}>
              <summary className="cursor-pointer text-[11px] font-medium uppercase tracking-wider text-slate-500">
                Agent orchestration log
              </summary>
              <pre className="mt-2 max-h-28 overflow-auto rounded-lg border border-slate-800 bg-[#070d14] p-3 font-mono text-[11px] leading-relaxed text-slate-400">
                {logs.length ? logs.join("\n") : "No log lines yet."}
              </pre>
            </details>

            <form className="shrink-0 border-t border-white/10 p-3" onSubmit={sendMessage}>
              <label className="sr-only" htmlFor="composer-input">
                Message
              </label>
              <textarea
                id="composer-input"
                rows={2}
                className="mb-2 w-full resize-none rounded-xl border border-white/10 bg-firm-950/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-blue-500/50 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                placeholder="Start here — e.g. what happened, where you were, and how you were hurt…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={sending}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
              />
              <button
                type="submit"
                disabled={sending || !draft.trim()}
                className="w-full rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-900/30 hover:from-blue-500 hover:to-blue-400 disabled:cursor-not-allowed disabled:opacity-40 md:w-auto md:px-8"
              >
                Send
              </button>
            </form>
          </section>

          {/* Brief — same height band as chat for layout balance */}
          <section
            className="flex max-h-[calc(100dvh-12rem)] min-h-[420px] flex-col rounded-2xl border border-white/10 bg-firm-900/40 shadow-xl shadow-black/20 backdrop-blur-sm lg:min-h-[min(520px,calc(100dvh-12rem))]"
            aria-label="Attorney brief"
          >
            <div className="shrink-0 flex items-center justify-between border-b border-white/10 px-4 py-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Live brief</h2>
              <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-200">
                Synced
              </span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4">
              <BriefPane markdown={briefMd} />
            </div>
          </section>
        </div>

        {/* Attorney match cards only — does not consume vertical space from chat/brief */}
        <section className="shrink-0" aria-label="Attorney matches">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Attorney matches</h2>
          {lawyerMatches.length === 0 ? (
            <p className="text-sm text-slate-500">Matches from the matcher agent appear here after you send a message.</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {lawyerMatches.map((law, idx) => (
                <div
                  key={`${law.name}-${idx}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => openLawyer(law)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") openLawyer(law);
                  }}
                  className="cursor-pointer rounded-xl border border-blue-500/20 bg-gradient-to-br from-firm-900/80 to-firm-950/90 p-4 shadow-lg shadow-blue-950/20 transition hover:border-blue-400/40 hover:bg-firm-900/90"
                >
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-blue-400/90">Counsel match</p>
                  <p className="mt-2 font-semibold text-white">{law.name || "—"}</p>
                  <p className="mt-1 text-sm text-slate-400">{law.specialty || "—"}</p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <p className="text-xs text-slate-500">{law.location || ""}</p>
                    <p className="text-xs text-slate-500">
                      {law.rating ? `★ ${Number(law.rating).toFixed(1)}` : ""}
                    </p>
                  </div>
                  {(law.location || law.score !== undefined) && (
                    <p className="mt-2 text-xs text-slate-500">
                      {law.location && <span>{law.location}</span>}
                      {law.location && law.score != null && <span> · </span>}
                      {law.score != null && <span>Score {Number(law.score).toFixed(2)}</span>}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {lawyerModalOpen && selectedLawyer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-6" role="dialog" aria-modal="true">
          <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-white/10 bg-firm-900/95 shadow-2xl shadow-black/40">
            <div className="flex items-start justify-between gap-4 border-b border-white/10 px-5 py-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Attorney profile</p>
                <h3 className="mt-1 text-xl font-semibold text-white">{selectedLawyer.name}</h3>
                <p className="mt-1 text-sm text-slate-400">
                  {selectedLawyer.specialty || "—"} {selectedLawyer.location ? `· ${selectedLawyer.location}` : ""}
                </p>
              </div>
              <button
                type="button"
                onClick={closeLawyer}
                className="rounded-lg border border-white/10 bg-black/20 px-3 py-1.5 text-sm text-slate-200 hover:bg-black/30"
              >
                Close
              </button>
            </div>
            <div className="space-y-5 px-5 py-5">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-firm-950/40 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Rating</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {selectedLawyer.rating ? `★ ${Number(selectedLawyer.rating).toFixed(1)}` : "—"}
                  </p>
                </div>
                <div className="rounded-xl border border-white/10 bg-firm-950/40 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Profile</p>
                  <a
                    className="mt-2 inline-block text-sm font-medium text-blue-400 hover:text-blue-300"
                    href={selectedLawyer.profile_url || "#"}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View on Lawyer.com
                  </a>
                </div>
                <div className="rounded-xl border border-white/10 bg-firm-950/40 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Contact</p>
                  <p className="mt-2 text-sm text-slate-300">{selectedLawyer.contact_email || "—"}</p>
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <button
                  type="button"
                  onClick={sendBriefToLawyer}
                  disabled={shareBusy}
                  className="rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-900/30 hover:from-blue-500 hover:to-blue-400 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {shareBusy ? "Sending…" : "Send brief to this lawyer"}
                </button>
                <p className="text-xs text-slate-500">
                  Sends the current generated brief (mock).
                </p>
              </div>

              <div className="rounded-xl border border-white/10 bg-firm-950/35 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Book appointment (request)</p>
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <input
                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-blue-500/50 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Your email (for confirmation)"
                    value={apptEmail}
                    onChange={(e) => setApptEmail(e.target.value)}
                  />
                  <input
                    className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-blue-500/50 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Phone (optional)"
                    value={apptPhone}
                    onChange={(e) => setApptPhone(e.target.value)}
                  />
                </div>
                <textarea
                  rows={2}
                  className="mt-3 w-full resize-none rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-blue-500/50 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  placeholder="Preferred times (e.g. Tue 2–4pm, Wed morning)…"
                  value={apptTimes}
                  onChange={(e) => setApptTimes(e.target.value)}
                />
                <textarea
                  rows={2}
                  className="mt-3 w-full resize-none rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-blue-500/50 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  placeholder="Note (optional)…"
                  value={apptNote}
                  onChange={(e) => setApptNote(e.target.value)}
                />
                <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <button
                    type="button"
                    onClick={requestAppointment}
                    disabled={apptBusy || !apptEmail.trim()}
                    className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-5 py-2.5 text-sm font-semibold text-emerald-200 hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {apptBusy ? "Requesting…" : "Request appointment"}
                  </button>
                  <p className="text-xs text-slate-500">Requires an email for confirmation.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div
          className={
            "fixed bottom-6 left-1/2 z-50 max-w-md -translate-x-1/2 rounded-xl border px-4 py-3 text-sm shadow-xl " +
            (toast.isError
              ? "border-red-500/40 bg-red-950/95 text-red-100"
              : "border-white/15 bg-firm-900/95 text-slate-100")
          }
          role="status"
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
