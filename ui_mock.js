import React, { useMemo, useState, useRef } from "react";

// Mock data
const mockThreads = [
  {
    id: "t1",
    name: "DovOS – Embedding Pipeline",
    lastDate: "2025-09-04 22:31",
    summary:
      "We mapped chunking rules, chose cosine similarity, and parked HNSW params for later.",
    messages: [
      {
        id: "m1",
        role: "user",
        author: "Dov",
        time: "2025-09-04 21:58",
        text:
          "Sketch a plan for embedding pipeline v2: ingestion, normalization, chunking, embeddings, and index updates without downtime.",
      },
      {
        id: "m2",
        role: "ai",
        author: "AI",
        time: "2025-09-04 22:12",
        text:
          "Here’s a phased approach: (1) Ingestion via event queue (n8n) → (2) Normalization (UTF-8, newline compaction) → (3) Chunking (Semantic/Token) → (4) Embeddings (Qdrant/Chroma) → (5) Blue/Green index swap for zero-downtime.",
      },
      {
        id: "m3",
        role: "user",
        author: "Dov",
        time: "2025-09-04 22:20",
        text: "Good. Capture tradeoffs for semantic vs token chunking.",
      },
      {
        id: "m4",
        role: "ai",
        author: "AI",
        time: "2025-09-04 22:31",
        text:
          "Token chunking = predictable recall + simpler caching; semantic chunking = higher coherence + fewer edge breaks but needs model pass and QA.",
      },
    ],
  },
  {
    id: "t2",
    name: "Sovereign Stack – Threat Model",
    lastDate: "2025-09-03 09:14",
    summary:
      "Outlined local-first trust boundaries, API egress rules, and operator audit log needs.",
    messages: [
      {
        id: "m1",
        role: "user",
        author: "Dov",
        time: "2025-09-03 08:47",
        text: "Give me a concise threat model for a local-first LLM stack.",
      },
      {
        id: "m2",
        role: "ai",
        author: "AI",
        time: "2025-09-03 09:14",
        text:
          "Actors: User, Operator, Model Host, Integrations. Risks: prompt exfil, data drift, package supply chain, side-channel telemetry. Controls: network deny-by-default, signed models, content provenance, immutable logs.",
      },
    ],
  },
  {
    id: "t3",
    name: "Spanish – Shrimp Order Script",
    lastDate: "2025-09-02 10:05",
    summary: "Short dialogue for ordering and asking to devein shrimp (quitar la vena).",
    messages: [
      {
        id: "m1",
        role: "user",
        author: "Dov",
        time: "2025-09-02 09:55",
        text: "Make a 60-sec PV market shrimp order script in Spanish.",
      },
      {
        id: "m2",
        role: "ai",
        author: "AI",
        time: "2025-09-02 10:05",
        text:
          "Cliente: ‘¿Me puede limpiar y quitar la vena a los camarones, por favor?’ Vendedor: ‘Claro, ¿cuántos?’ …",
      },
    ],
  },
];

function clsx(...args) {
  return args.filter(Boolean).join(" ");
}

function Avatar({ label }) {
  const initial = label?.[0]?.toUpperCase() || "?";
  return (
    <div className="h-8 w-8 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center text-xs font-semibold text-zinc-700 dark:text-zinc-200">
      {initial}
    </div>
  );
}

function formatRelative(ts) {
  try {
    const d = new Date(ts.includes("T") ? ts : ts.replace(" ", "T"));
    if (isNaN(d.getTime())) return ts;
    const now = new Date();
    const diffMs = now - d;
    const sec = Math.floor(diffMs / 1000);
    const min = Math.floor(sec / 60);
    const hr = Math.floor(min / 60);
    const day = Math.floor(hr / 24);
    const week = Math.floor(day / 7);

    if (min < 1) return "just now";
    if (hr < 1) return `${min}m ago`;
    if (day < 1) return `${hr}h ago`;
    if (week < 1) return `${day}d ago`;
    if (week < 4) return `${week}w ago`;
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch (_) {
    return ts;
  }
}

export default function SovereignAIMockUI() {
  const [threads] = useState(mockThreads);
  const [activeId, setActiveId] = useState(threads[0]?.id);
  const active = useMemo(
    () => threads.find((t) => t.id === activeId) || threads[0],
    [threads, activeId]
  );

  const convoRef = useRef(null);

  const copyConversation = async () => {
    if (!active) return;
    const text = active.messages
      .map((m) => `${m.author} — ${m.time}\n${m.text}`)
      .join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      alert("Conversation copied to clipboard.");
    } catch (e) {
      console.error(e);
      alert("Clipboard failed. Select and copy manually.");
    }
  };

  return (
    <div className="h-screen w-full bg-zinc-50 dark:bg-zinc-900 text-zinc-900 dark:text-zinc-50">
      <header className="h-14 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <div className="text-xl font-semibold tracking-tight">Sovereign AI</div>
          <div className="text-xs px-2 py-0.5 rounded-full bg-zinc-200/70 dark:bg-zinc-800/80">Mock UI</div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={copyConversation}
            className="px-3 py-1.5 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-sm"
            title="Copy the entire conversation to clipboard"
          >
            Copy Conversation
          </button>
        </div>
      </header>

      <main className="h-[calc(100vh-3.5rem)] grid grid-cols-[320px_1fr]">
        <aside className="border-r border-zinc-200 dark:border-zinc-800 overflow-y-auto">
          <div className="p-3 sticky top-0 bg-zinc-50/80 dark:bg-zinc-900/80 backdrop-blur border-b border-zinc-200 dark:border-zinc-800 flex gap-2">
            <input
              className="w-full px-3 py-2 rounded-xl bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 text-sm outline-none focus:ring-2 focus:ring-indigo-500/40"
              placeholder="Search conversations"
            />
            <button className="px-3 py-2 rounded-xl bg-indigo-600 text-white text-sm hover:bg-indigo-500">New</button>
          </div>

          <ul className="p-2 space-y-1">
            {threads.map((t) => (
              <li key={t.id}>
                <button
                  onClick={() => setActiveId(t.id)}
                  className={clsx(
                    "w-full text-left p-3 rounded-xl border hover:bg-zinc-100/70 dark:hover:bg-zinc-800/70",
                    active?.id === t.id
                      ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-950/40"
                      : "border-zinc-200 dark:border-zinc-800"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium truncate" title={t.name}>{t.name}</div>
                    <div className="text-xs text-zinc-500 whitespace-nowrap">{formatRelative(t.lastDate)}</div>
                  </div>
                  <div
                    className="mt-1 text-sm text-zinc-600 dark:text-zinc-400 line-clamp-1"
                    title={t.summary}
                  >
                    {t.summary}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="overflow-y-auto">
          <div className="sticky top-0 z-10 bg-zinc-50/90 dark:bg-zinc-900/90 backdrop-blur border-b border-zinc-200 dark:border-zinc-800 px-6 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold tracking-tight">{active?.name}</h2>
                <p className="text-xs text-zinc-500">Last updated {formatRelative(active?.lastDate)}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={copyConversation}
                  className="px-3 py-1.5 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-sm"
                  title="Copy the entire conversation to clipboard"
                >
                  Copy
                </button>
                <button
                  className="px-3 py-1.5 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-sm"
                  onClick={() => window.location.reload()}
                  title="Refresh"
                >
                  Refresh
                </button>
              </div>
            </div>
          </div>

          <div ref={convoRef} className="px-6 py-6 space-y-6">
            {active?.messages.map((m) => (
              <article key={m.id}>
                <div
                  className={clsx(
                    "flex gap-3",
                    m.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  {m.role === "ai" && <Avatar label={m.author} />}
                  <div
                    className={clsx(
                      "max-w-[70ch] rounded-2xl p-4 shadow-sm border",
                      m.role === "user"
                        ? "bg-indigo-600/10 border-indigo-200 dark:border-indigo-900"
                        : "bg-white dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700"
                    )}
                  >
                    <header className="flex items-center justify-between mb-1">
                      <div className="text-sm font-semibold">
                        {m.author}
                        <span
                          className="ml-2 text-xs font-normal text-zinc-500"
                          title={m.time}
                        >
                          {formatRelative(m.time)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          className="text-xs px-2 py-1 rounded-md border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-700"
                          title="Copy this message"
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(`${m.author} — ${m.time}\n${m.text}`);
                              alert("Message copied.");
                            } catch (e) {
                              alert("Clipboard failed.");
                            }
                          }}
                        >
                          Copy
                        </button>
                      </div>
                    </header>

                    <p className="leading-relaxed whitespace-pre-wrap text-[15px]">
                      {m.text}
                    </p>
                  </div>
                  {m.role === "user" && <Avatar label={m.author} />}
                </div>
              </article>
            ))}
          </div>

          <div className="sticky bottom-0 bg-zinc-50/90 dark:bg-zinc-900/90 backdrop-blur border-t border-zinc-200 dark:border-zinc-800 p-4">
            <div className="flex items-end gap-3">
              <textarea
                className="flex-1 min-h-[56px] max-h-48 rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-4 py-3 outline-none focus:ring-2 focus:ring-indigo-500/40"
                placeholder="Type a message (mock)"
              />
              <button className="h-11 px-4 rounded-2xl bg-indigo-600 text-white font-medium hover:bg-indigo-500">
                Send
              </button>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
