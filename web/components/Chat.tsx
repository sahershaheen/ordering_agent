"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, sendChat, sendVoiceChat, type Source } from "@/lib/api";
import { playBase64Wav, WavRecorder } from "@/lib/audio";
import { ConfidenceBar } from "@/components/ui";

interface Message {
  role: "user" | "agent";
  text: string;
  sources?: Source[];
  confidence?: number | null;
  spoken?: boolean;
}

const WELCOME: Message = {
  role: "agent",
  text:
    "Welcome to Flavour & Rush! I can show you the menu, take your order, " +
    "track an existing one, or book you a table. What can I get you today?",
};

export default function Chat({ sessionId }: { sessionId: string }) {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const recorderRef = useRef<WavRecorder | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, busy]);

  const appendAgentError = (error: unknown) => {
    const text =
      error instanceof ApiError
        ? error.message
        : "Something went wrong. Please try again.";
    setMessages((prev) => [...prev, { role: "agent", text }]);
  };

  const submitText = async (event: React.FormEvent) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || busy) return;

    setDraft("");
    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setBusy(true);
    try {
      const res = await sendChat(sessionId, message);
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          text: res.reply,
          sources: res.sources,
          confidence: res.confidence,
        },
      ]);
    } catch (error) {
      appendAgentError(error);
    } finally {
      setBusy(false);
    }
  };

  const toggleRecording = async () => {
    setVoiceError(null);

    if (recording) {
      // Stop, upload, and play the spoken reply
      setRecording(false);
      setBusy(true);
      try {
        const wav = await recorderRef.current!.stop();
        const res = await sendVoiceChat(sessionId, wav);
        setMessages((prev) => [
          ...prev,
          { role: "user", text: res.transcript, spoken: true },
          {
            role: "agent",
            text: res.reply,
            sources: res.sources,
            confidence: res.confidence,
            spoken: true,
          },
        ]);
        playBase64Wav(res.audio_base64).catch(() => {
          /* playback failure is non-fatal: the text reply is on screen */
        });
      } catch (error) {
        if (error instanceof ApiError && error.status === 422) {
          setVoiceError("I couldn't hear any speech — try again a bit closer to the mic.");
        } else {
          appendAgentError(error);
        }
      } finally {
        setBusy(false);
      }
      return;
    }

    try {
      recorderRef.current = new WavRecorder();
      await recorderRef.current.start();
      setRecording(true);
    } catch {
      setVoiceError("Microphone access was denied. Allow it in your browser settings.");
    }
  };

  return (
    <div className="flex h-[36rem] flex-col overflow-hidden rounded-2xl border border-surface-700 bg-surface-900/80 shadow-lg shadow-black/30">
      {/* Message list */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-5">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {busy && (
          <div className="flex items-center gap-1.5 pl-1 text-brand-400">
            <span className="typing-dot h-2 w-2 rounded-full bg-current" />
            <span className="typing-dot h-2 w-2 rounded-full bg-current" />
            <span className="typing-dot h-2 w-2 rounded-full bg-current" />
          </div>
        )}
      </div>

      {voiceError && (
        <p className="border-t border-surface-700 px-5 py-2 text-xs text-amber-300">
          {voiceError}
        </p>
      )}

      {/* Composer */}
      <form
        onSubmit={submitText}
        className="flex items-center gap-2 border-t border-surface-700 bg-surface-800/60 p-3"
      >
        <button
          type="button"
          onClick={toggleRecording}
          disabled={busy && !recording}
          title={recording ? "Stop and send" : "Speak your message"}
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition
            ${
              recording
                ? "rec-pulse bg-red-500 text-white"
                : "bg-surface-700 text-ink-300 hover:bg-surface-600 hover:text-brand-300"
            } disabled:cursor-not-allowed disabled:opacity-40`}
        >
          {recording ? <StopIcon /> : <MicIcon />}
        </button>

        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={
            recording ? "Listening… press stop to send" : "Ask about the menu, order food, book a table…"
          }
          disabled={recording}
          maxLength={2000}
          className="flex-1 rounded-full border border-surface-600 bg-surface-900 px-4 py-2.5
                     text-sm text-ink-100 placeholder-ink-500 outline-none transition
                     focus:border-brand-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={busy || recording || !draft.trim()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-500
                     text-surface-950 transition hover:bg-brand-400
                     disabled:cursor-not-allowed disabled:opacity-40"
          title="Send"
        >
          <SendIcon />
        </button>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed
          ${
            isUser
              ? "rounded-br-sm bg-brand-500 text-surface-950"
              : "rounded-bl-sm border border-surface-700 bg-surface-800 text-ink-100"
          }`}
      >
        {message.spoken && (
          <span className={`mb-1 flex items-center gap-1 text-[11px] ${isUser ? "text-surface-950/70" : "text-ink-500"}`}>
            <MicIcon size={11} /> voice
          </span>
        )}
        <p className="whitespace-pre-wrap">{message.text}</p>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2 border-t border-surface-700 pt-2">
            <button
              type="button"
              onClick={() => setShowSources((v) => !v)}
              className="flex items-center gap-2 text-xs text-brand-400 hover:text-brand-300"
            >
              {showSources ? "Hide sources" : `Sources (${message.sources.length})`}
              {message.confidence != null && <ConfidenceBar value={message.confidence} />}
            </button>
            {showSources && (
              <ul className="mt-2 space-y-1.5">
                {message.sources.map((source, i) => (
                  <li key={i} className="rounded-lg bg-surface-900 px-2.5 py-1.5 text-xs text-ink-300">
                    <span className="mr-1.5 font-semibold text-brand-400">p.{source.page}</span>
                    {source.snippet}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function MicIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m22 2-7 20-4-9-9-4Z" />
      <path d="M22 2 11 13" />
    </svg>
  );
}
