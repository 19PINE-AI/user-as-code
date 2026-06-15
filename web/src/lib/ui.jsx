import React, { useEffect, useState } from 'react'

// Base URL aware data loader (works with vite base './').
export function dataUrl(name) {
  const base = import.meta.env.BASE_URL || '/'
  return `${base}data/${name}`.replace(/\/+/g, '/')
}

export function useJson(name) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    let alive = true
    setData(null)
    setError(null)
    fetch(dataUrl(name))
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json()
      })
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e))
    return () => {
      alive = false
    }
  }, [name])
  return { data, error }
}

export function cx(...xs) {
  return xs.filter(Boolean).join(' ')
}

// --- Minimal Python syntax highlighter (good enough for short snippets) ---
const KW = new Set([
  'def', 'class', 'return', 'for', 'in', 'if', 'elif', 'else', 'import', 'from',
  'and', 'or', 'not', 'is', 'None', 'True', 'False', 'with', 'as', 'lambda',
  'continue', 'break', 'while', 'try', 'except', 'pass', 'yield', 'dataclass',
])
const BUILTIN = new Set(['list', 'dict', 'set', 'tuple', 'str', 'int', 'float', 'bool', 'date', 'field', 'sum', 'len', 'sorted', 'round', 'mean', 'print', 'range', 'defaultdict'])

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// Single-pass tokenizer over HTML-escaped source. Each token is emitted
// exactly once, so inserted markup (e.g. class="tok-str") is never re-scanned
// — previously the identifier pass matched `class`/`str` inside that markup
// and corrupted the tags.
// Note: escapeHtml only escapes & < > (not quotes), so string delimiters in the
// escaped source are still literal " and '.
const TOKEN_RE =
  /(#[^\n]*)|((?:f|r|rf|fr)?("|')[\s\S]*?\3)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)/g

export function highlightPython(code) {
  if (!code) return ''
  return escapeHtml(code).replace(TOKEN_RE, (m, comment, str, _q, num, ident) => {
    if (comment) return `<span class="tok-com">${comment}</span>`
    if (str) return `<span class="tok-str">${str}</span>`
    if (num) return `<span class="tok-num">${num}</span>`
    if (ident) {
      if (KW.has(ident)) return `<span class="tok-kw">${ident}</span>`
      if (BUILTIN.has(ident)) return `<span class="tok-fn">${ident}</span>`
      if (/^[A-Z]/.test(ident)) return `<span class="tok-cls">${ident}</span>`
      return ident
    }
    return m
  })
}

export function CodeBlock({ code, lang = 'python', className = '', caption }) {
  const html = lang === 'python' ? highlightPython(code) : escapeHtml(code || '')
  return (
    <div className={cx('group relative overflow-hidden rounded-xl border border-white/10 bg-ink-950/80', className)}>
      <div className="flex items-center gap-1.5 border-b border-white/5 bg-ink-900/60 px-4 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
        {caption && <span className="ml-3 font-mono text-[11px] text-slate-500">{caption}</span>}
      </div>
      <pre className="scroll-thin overflow-x-auto p-4 text-[12.5px] leading-relaxed">
        <code className="font-mono" dangerouslySetInnerHTML={{ __html: html }} />
      </pre>
    </div>
  )
}

export function Verdict({ ok, label }) {
  if (ok === undefined || ok === null) {
    return <span className="chip border-slate-600/40 bg-slate-600/10 text-slate-400">{label || '—'}</span>
  }
  return ok ? (
    <span className="chip border-ok/30 bg-ok/10 text-ok">
      <CheckIcon /> {label || 'Correct'}
    </span>
  ) : (
    <span className="chip border-bad/30 bg-bad/10 text-bad">
      <XIcon /> {label || 'Wrong'}
    </span>
  )
}

export function CheckIcon({ className = 'h-3 w-3' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.1 3.1 6.8-6.8a1 1 0 011.4 0z" clipRule="evenodd" />
    </svg>
  )
}
export function XIcon({ className = 'h-3 w-3' }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 8.6l3.7-3.7a1 1 0 011.4 1.4L11.4 10l3.7 3.7a1 1 0 01-1.4 1.4L10 11.4l-3.7 3.7a1 1 0 01-1.4-1.4L8.6 10 4.9 6.3a1 1 0 011.4-1.4L10 8.6z" clipRule="evenodd" />
    </svg>
  )
}

export function Spinner({ label = 'Loading evaluation data…' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-slate-500">
      <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-400/30 border-t-brand-400" />
      <span className="font-mono text-xs">{label}</span>
    </div>
  )
}

export function StatPill({ value, label, accent = 'brand' }) {
  const color = accent === 'accent' ? 'text-accent-300' : accent === 'ok' ? 'text-ok' : 'text-brand-300'
  return (
    <div className="card px-5 py-4">
      <div className={cx('font-mono text-2xl font-bold sm:text-3xl', color)}>{value}</div>
      <div className="mt-1 text-xs text-slate-400">{label}</div>
    </div>
  )
}

// Color for the canonical system keys, used across charts + explorer.
export const SYS_COLORS = {
  uac_v5: '#22d3ee',
  full_context: '#a78bfa',
  memmachine: '#f472b6',
  hindsight: '#fbbf24',
  evermemos: '#34d399',
  a_mem: '#60a5fa',
  mem0: '#f87171',
  fc_repl: '#a78bfa',
}
