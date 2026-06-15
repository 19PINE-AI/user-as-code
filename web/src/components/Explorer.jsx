import React, { useMemo, useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJson, Spinner, cx, Verdict, CodeBlock, SYS_COLORS } from '../lib/ui.jsx'

const BENCHES = [
  { id: 'locomo', label: 'LOCOMO', file: 'locomo.json', mem: 'locomo_memory.json', sub: '600 multi-session QAs' },
  { id: 'lme', label: 'LongMemEval', file: 'longmemeval.json', mem: 'lme_memory.json', sub: '500 long-memory QAs' },
  { id: 'analytical', label: 'Analytical', file: 'analytical.json', mem: 'analytical_memory.json', sub: '100 aggregation cases' },
  { id: 'active', label: 'Active Service', file: 'active.json', mem: 'active_memory.json', sub: '60 proactive scenarios' },
]

/* Arrow-key navigation across the filtered case list. */
function useKeyNav(sel, setSel, count) {
  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target.tagName || '').toLowerCase()
      if (tag === 'input' || tag === 'select' || tag === 'textarea') return
      if (e.key === 'ArrowDown' || e.key === 'j') {
        setSel((s) => Math.min(count - 1, s + 1))
        e.preventDefault()
      } else if (e.key === 'ArrowUp' || e.key === 'k') {
        setSel((s) => Math.max(0, s - 1))
        e.preventDefault()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setSel, count])
}

/* ------------------------------------------------------------------ */
/* Shared layout: filter bar + scrollable list + detail pane          */
/* ------------------------------------------------------------------ */
function Layout({ filters, list, detail, count, total, sel, setSel }) {
  const hasNav = typeof sel === 'number' && count > 0
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
      <div className="flex flex-col">
        <div className="card flex flex-col overflow-hidden">
          <div className="space-y-3 border-b border-white/10 bg-ink-900/40 p-3">{filters}</div>
          <div className="px-3 py-2 font-mono text-[11px] text-slate-500">
            {count} / {total} cases
          </div>
          <div className="scroll-thin max-h-[34rem] overflow-y-auto px-2 pb-2 lg:max-h-[42rem]">{list}</div>
        </div>
      </div>
      <div className="min-w-0">
        {hasNav && (
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="font-mono text-[11px] text-slate-500">
              case {sel + 1} of {count}
              <span className="ml-2 hidden text-slate-600 sm:inline">· ↑/↓ to navigate</span>
            </span>
            <div className="flex gap-1.5">
              <button
                onClick={() => setSel((s) => Math.max(0, s - 1))}
                disabled={sel <= 0}
                className="btn border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 enabled:hover:bg-white/10 disabled:opacity-40"
              >
                ← Prev
              </button>
              <button
                onClick={() => setSel((s) => Math.min(count - 1, s + 1))}
                disabled={sel >= count - 1}
                className="btn border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 enabled:hover:bg-white/10 disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          </div>
        )}
        {detail}
      </div>
    </div>
  )
}

function ListRow({ active, onClick, badge, title, meta, status }) {
  const ref = React.useRef(null)
  const mounted = React.useRef(false)
  useEffect(() => {
    // Skip the first run: otherwise the default-selected row scrolls itself
    // into view on mount, dragging the whole page down to the (below-the-fold)
    // Explorer the moment it lazy-loads. Only scroll on real user selection.
    if (!mounted.current) {
      mounted.current = true
      return
    }
    if (active && ref.current) ref.current.scrollIntoView({ block: 'nearest' })
  }, [active])
  return (
    <button
      ref={ref}
      onClick={onClick}
      className={cx(
        'group mb-1 w-full rounded-xl border px-3 py-2.5 text-left transition',
        active ? 'border-brand-400/40 bg-brand-400/10' : 'border-transparent hover:border-white/10 hover:bg-white/[0.04]'
      )}
    >
      <div className="flex items-center gap-2">
        {status}
        {badge}
        <span className="ml-auto truncate font-mono text-[10px] text-slate-500">{meta}</span>
      </div>
      <div className={cx('mt-1.5 line-clamp-2 text-sm leading-snug', active ? 'text-white' : 'text-slate-300')}>{title}</div>
    </button>
  )
}

function StatusDot({ ok }) {
  if (ok === undefined || ok === null) return <span className="h-2 w-2 shrink-0 rounded-full bg-slate-600" />
  return <span className={cx('h-2 w-2 shrink-0 rounded-full', ok ? 'bg-ok' : 'bg-bad')} title={ok ? 'UaC correct' : 'UaC wrong'} />
}

function CatBadge({ children, color = 'slate' }) {
  const map = {
    slate: 'border-slate-600/40 bg-slate-600/10 text-slate-400',
    brand: 'border-brand-400/30 bg-brand-400/10 text-brand-200',
    accent: 'border-accent-400/30 bg-accent-400/10 text-accent-300',
    warn: 'border-warn/30 bg-warn/10 text-warn',
    ok: 'border-ok/30 bg-ok/10 text-ok',
    bad: 'border-bad/30 bg-bad/10 text-bad',
  }
  return <span className={cx('chip', map[color])}>{children}</span>
}

function SearchInput({ value, onChange, placeholder }) {
  return (
    <div className="relative">
      <svg className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 103.4 9.8l3.4 3.4a1 1 0 001.4-1.4l-3.4-3.4A5.5 5.5 0 009 3.5zm-3.5 5.5a3.5 3.5 0 117 0 3.5 3.5 0 01-7 0z" clipRule="evenodd" />
      </svg>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-white/10 bg-ink-950/60 py-2 pl-9 pr-3 text-sm text-slate-200 placeholder:text-slate-600 focus:border-brand-400/50 focus:outline-none focus:ring-1 focus:ring-brand-400/30"
      />
    </div>
  )
}

function Select({ value, onChange, options }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-lg border border-white/10 bg-ink-950/60 px-3 py-2 text-sm text-slate-200 focus:border-brand-400/50 focus:outline-none"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value} className="bg-ink-900">
          {o.label}
        </option>
      ))}
    </select>
  )
}

function DetailShell({ children }) {
  return <div className="card overflow-hidden p-5 sm:p-6">{children}</div>
}

function EmptyDetail() {
  return (
    <div className="card grid h-full min-h-[20rem] place-items-center p-10 text-center text-slate-500">
      <div>
        <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl border border-white/10 bg-white/5 font-mono text-lg">{'<>'}</div>
        Select a case to inspect its context, every system's response, and the grading.
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Per-system response card (LOCOMO / LME)                            */
/* ------------------------------------------------------------------ */
function SystemResponse({ sysKey, meta, rec }) {
  const [open, setOpen] = useState(false)
  const ours = meta?.ours
  return (
    <div className={cx('rounded-xl border bg-ink-900/40 transition', ours ? 'border-brand-400/40 ring-1 ring-brand-400/20' : 'border-white/10')}>
      <div className="flex flex-wrap items-center gap-2 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: SYS_COLORS[sysKey] || '#64748b' }} />
        <span className={cx('text-sm font-semibold', ours ? 'text-brand-200' : 'text-slate-200')}>{meta?.name || sysKey}</span>
        {ours && <span className="chip border-brand-400/30 bg-brand-400/10 text-[10px] text-brand-200">ours</span>}
        {meta?.upper && <span className="chip border-accent-400/30 bg-accent-400/10 text-[10px] text-accent-300">upper bound</span>}
        {meta?.lite && (
          <span className="chip border-white/15 bg-white/5 text-[10px] text-slate-400" title="Same-backbone lite reimplementation under Gemini 3 Flash">lite reimpl.</span>
        )}
        <div className="ml-auto flex items-center gap-1.5">
          <span className="font-mono text-[10px] text-slate-500">Gemini</span>
          <Verdict ok={rec.gemini_correct} label={rec.gemini_correct ? '✓' : '✗'} />
          <span className="ml-1 font-mono text-[10px] text-slate-500">Claude</span>
          <Verdict ok={rec.claude_correct} label={rec.claude_correct ? '✓' : '✗'} />
        </div>
      </div>
      <div className="border-t border-white/5 px-4 py-3">
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{rec.prediction || <span className="italic text-slate-600">(no answer)</span>}</p>
        {(rec.gemini_reason || rec.claude_reason) && (
          <button onClick={() => setOpen((v) => !v)} className="mt-2 inline-flex items-center gap-1 font-mono text-[11px] text-slate-500 hover:text-slate-300">
            <svg className={cx('h-3 w-3 transition', open && 'rotate-90')} viewBox="0 0 20 20" fill="currentColor"><path d="M7 5l6 5-6 5V5z" /></svg>
            judge reasoning
          </button>
        )}
        <AnimatePresence initial={false}>
          {open && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
              <div className="mt-2 space-y-2 border-t border-white/5 pt-2 text-xs">
                {rec.gemini_reason && (
                  <div><span className="font-mono text-slate-500">Gemini: </span><span className="text-slate-400">{rec.gemini_reason}</span></div>
                )}
                {rec.claude_reason && (
                  <div><span className="font-mono text-slate-500">Claude: </span><span className="text-slate-400">{rec.claude_reason}</span></div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* LOCOMO + LME explorers (QA-style)                                  */
/* ------------------------------------------------------------------ */
function QAExplorer({ data, kind, memory }) {
  const { systems, sys_order, cases } = data
  const [q, setQ] = useState('')
  const [filterCat, setFilterCat] = useState('all')
  const [filterStat, setFilterStat] = useState('all')
  const [sel, setSel] = useState(0)

  const catOptions = useMemo(() => {
    const keyOf = (c) => (kind === 'locomo' ? c.category_name : c.type)
    const set = new Map()
    cases.forEach((c) => {
      const k = keyOf(c)
      if (k) set.set(k, (set.get(k) || 0) + 1)
    })
    return [{ value: 'all', label: kind === 'locomo' ? 'All categories' : 'All types' }, ...[...set.entries()].sort().map(([k, n]) => ({ value: k, label: `${k} (${n})` }))]
  }, [cases, kind])

  const filtered = useMemo(() => {
    const ql = q.toLowerCase()
    return cases.filter((c) => {
      const catKey = kind === 'locomo' ? c.category_name : c.type
      if (filterCat !== 'all' && catKey !== filterCat) return false
      const uac = c.systems.uac_v5
      if (filterStat === 'uac_correct' && !(uac && uac.gemini_correct)) return false
      if (filterStat === 'uac_wrong' && !(uac && uac.gemini_correct === false)) return false
      if (filterStat === 'disagree') {
        const vals = sys_order.map((s) => c.systems[s]?.gemini_correct).filter((v) => v !== undefined)
        if (new Set(vals).size < 2) return false
      }
      if (ql && !(`${c.question} ${c.gold}`.toLowerCase().includes(ql))) return false
      return true
    })
  }, [cases, q, filterCat, filterStat, kind, sys_order])

  useEffect(() => setSel(0), [q, filterCat, filterStat])
  useKeyNav(sel, setSel, filtered.length)
  const active = filtered[sel]

  return (
    <Layout
      total={cases.length}
      count={filtered.length}
      sel={sel}
      setSel={setSel}
      filters={
        <>
          <SearchInput value={q} onChange={setQ} placeholder="Search question or answer…" />
          <div className="grid grid-cols-2 gap-2">
            <Select value={filterCat} onChange={setFilterCat} options={catOptions} />
            <Select
              value={filterStat}
              onChange={setFilterStat}
              options={[
                { value: 'all', label: 'Any result' },
                { value: 'uac_correct', label: 'UaC correct' },
                { value: 'uac_wrong', label: 'UaC wrong' },
                { value: 'disagree', label: 'Systems disagree' },
              ]}
            />
          </div>
        </>
      }
      list={filtered.map((c, i) => (
        <ListRow
          key={c.id}
          active={i === sel}
          onClick={() => setSel(i)}
          status={<StatusDot ok={c.systems.uac_v5?.gemini_correct} />}
          badge={<CatBadge color="brand">{kind === 'locomo' ? c.category_name : c.type}</CatBadge>}
          meta={kind === 'locomo' ? c.conv_id : c.id}
          title={c.question}
        />
      ))}
      detail={active ? <QADetail c={active} systems={systems} sys_order={sys_order} kind={kind} memory={memory} /> : <EmptyDetail />}
    />
  )
}

function QADetail({ c, systems, sys_order, kind, memory }) {
  const correctCount = sys_order.filter((s) => c.systems[s]?.gemini_correct).length
  const memKey = kind === 'locomo' ? c.conv_id : c.question_id
  return (
    <DetailShell>
      <div className="flex flex-wrap items-center gap-2">
        <CatBadge color="brand">{kind === 'locomo' ? c.category_name : c.type}</CatBadge>
        <span className="font-mono text-[11px] text-slate-500">{kind === 'locomo' ? c.conv_id : c.question_id}</span>
        <span className="ml-auto font-mono text-[11px] text-slate-500">{correctCount}/{sys_order.length} systems correct</span>
      </div>

      <h3 className="mt-3 text-lg font-semibold leading-snug text-white">{c.question}</h3>

      {/* (b) Context */}
      {kind === 'locomo' && c.context?.length > 0 && (
        <section className="mt-5">
          <SectionLabel n="b" text="Context — evidence turns from the conversation" />
          <div className="mt-2 space-y-2">
            {c.context.map((t, i) => (
              <div key={i} className="rounded-xl border border-white/10 bg-ink-900/40 px-4 py-2.5">
                <div className="flex items-center gap-2 text-[11px] text-slate-500">
                  <span className="font-semibold text-brand-300">{t.speaker}</span>
                  <span className="font-mono">{t.dia_id}</span>
                  {t.date && <span className="ml-auto font-mono">{t.date}</span>}
                </div>
                <p className="mt-1 text-sm text-slate-300">{t.text}</p>
              </div>
            ))}
          </div>
        </section>
      )}
      {kind === 'lme' && (
        <section className="mt-5">
          <SectionLabel n="b" text="Context — evidence sessions (answer turns highlighted)" />
          {c.context?.length > 0 ? (
            <div className="mt-2 space-y-3">
              {c.context.map((sess, si) => (
                <div key={si} className="overflow-hidden rounded-xl border border-white/10 bg-ink-900/40">
                  <div className="flex items-center gap-2 border-b border-white/5 bg-ink-900/60 px-4 py-1.5 font-mono text-[11px] text-slate-500">
                    <span>evidence session {si + 1}</span>
                    {sess.date && <span className="ml-auto">{sess.date}</span>}
                  </div>
                  <div className="divide-y divide-white/5">
                    {sess.turns.map((t, ti) => (
                      <div key={ti} className={cx('px-4 py-2', t.evidence && 'bg-amber-500/[0.07]')}>
                        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider">
                          <span className={t.role === 'user' ? 'text-brand-300' : 'text-accent-300'}>{t.role}</span>
                          {t.evidence && <span className="chip border-warn/30 bg-warn/10 text-[9px] text-warn">⚡ answer evidence</span>}
                        </div>
                        <p className="mt-1 text-sm leading-relaxed text-slate-300">{t.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 rounded-xl border border-white/10 bg-ink-900/40 px-4 py-3 text-sm text-slate-400">
              Question type <span className="font-mono text-slate-200">{c.type}</span>; the gold answer below is the ground truth.
            </p>
          )}
        </section>
      )}

      {/* gold */}
      <section className="mt-5">
        <SectionLabel n="a" text="Benchmark — gold answer" />
        <div className="mt-2 rounded-xl border border-ok/30 bg-emerald-500/5 px-4 py-3">
          <span className="font-mono text-[11px] uppercase tracking-wider text-ok">gold</span>
          <p className="mt-1 whitespace-pre-wrap text-sm text-emerald-100">{c.gold}</p>
        </div>
      </section>

      {/* UaC's extracted memory for this conversation */}
      <MemoryPanel mem={memory?.[memKey]} kind={kind} />

      {/* (c)+(d) responses + grading */}
      <section className="mt-5">
        <SectionLabel n="c" text="Responses & grading — every system, dual-judged" />
        <div className="mt-2 space-y-2.5">
          {sys_order.map((s) =>
            c.systems[s] ? <SystemResponse key={s} sysKey={s} meta={systems[s]} rec={c.systems[s]} /> : null
          )}
        </div>
      </section>
    </DetailShell>
  )
}

function SectionLabel({ n, text }) {
  return (
    <div className="flex items-center gap-2">
      <span className="grid h-5 w-5 place-items-center rounded bg-brand-400/15 font-mono text-[10px] font-bold text-brand-200">{n}</span>
      <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">{text}</span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* UaC memory panel — the regenerated Phase-1 facts + Phase-2 state    */
/* ------------------------------------------------------------------ */
function MemoryPanel({ mem, kind }) {
  const [open, setOpen] = useState(true)
  if (!mem) return null
  const facts = mem.facts || []
  const isAnalytical = kind === 'analytical'
  return (
    <section className="mt-5">
      <button onClick={() => setOpen((v) => !v)} className="flex w-full items-center gap-2 text-left">
        <span className="grid h-5 w-5 place-items-center rounded bg-emerald-400/15 font-mono text-[10px] font-bold text-ok">m</span>
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          UaC memory — what the pipeline extracted for this case
        </span>
        <svg className={cx('ml-auto h-3.5 w-3.5 text-slate-500 transition', open && 'rotate-90')} viewBox="0 0 20 20" fill="currentColor"><path d="M7 5l6 5-6 5V5z" /></svg>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {/* Phase 1 — facts (or raw record preview for analytical) */}
              <div className="rounded-xl border border-brand-400/20 bg-ink-900/40 p-3">
                <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold text-brand-300">
                  Phase 1 · Memorize
                  <span className="font-mono text-slate-500">
                    {isAnalytical ? `${mem.n_records} records` : `${mem.n_facts} facts`}
                  </span>
                </div>
                {isAnalytical ? (
                  <pre className="scroll-thin max-h-72 overflow-auto font-mono text-[11px] leading-relaxed text-slate-400">{JSON.stringify(mem.records_preview, null, 1)}</pre>
                ) : (
                  <ul className="scroll-thin max-h-72 space-y-1 overflow-auto pr-1">
                    {facts.map((f, i) => (
                      <li key={i} className="font-mono text-[11px] leading-snug text-slate-400">{f}</li>
                    ))}
                    {mem.n_facts > facts.length && (
                      <li className="pt-1 font-mono text-[11px] text-slate-600">… {mem.n_facts - facts.length} more facts (append-only)</li>
                    )}
                  </ul>
                )}
              </div>
              {/* Phase 2 — typed state */}
              <div className="min-w-0">
                <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold text-accent-300">
                  Phase 2 · Structure
                  <span className="font-mono text-slate-500">state.py</span>
                </div>
                <div className="scroll-thin max-h-72 overflow-y-auto">
                  <CodeBlock code={mem.state} />
                </div>
              </div>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
              Regenerated by re-running the actual v5 pipeline on this case (Gemini 3 Flash, temperature 1.0) —
              representative of, not necessarily byte-identical to, the graded run.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/* Analytical explorer                                                */
/* ------------------------------------------------------------------ */
function AnalyticalExplorer({ data, memory }) {
  const { systems, sys_order, cases } = data
  const [q, setQ] = useState('')
  const [type, setType] = useState('all')
  const [nfilt, setNfilt] = useState('all')
  const [sel, setSel] = useState(0)

  const typeOptions = useMemo(() => {
    const s = new Set(cases.map((c) => c.type))
    return [{ value: 'all', label: 'All record types' }, ...[...s].sort().map((t) => ({ value: t, label: t }))]
  }, [cases])
  const nOptions = useMemo(() => {
    const s = new Set(cases.map((c) => c.n))
    return [{ value: 'all', label: 'All N' }, ...[...s].sort((a, b) => a - b).map((n) => ({ value: String(n), label: `N = ${n}` }))]
  }, [cases])

  const filtered = useMemo(() => {
    const ql = q.toLowerCase()
    return cases.filter((c) => {
      if (type !== 'all' && c.type !== type) return false
      if (nfilt !== 'all' && String(c.n) !== nfilt) return false
      if (ql && !c.question.toLowerCase().includes(ql)) return false
      return true
    })
  }, [cases, q, type, nfilt])

  useEffect(() => setSel(0), [q, type, nfilt])
  useKeyNav(sel, setSel, filtered.length)
  const active = filtered[sel]

  return (
    <Layout
      total={cases.length}
      count={filtered.length}
      sel={sel}
      setSel={setSel}
      filters={
        <>
          <SearchInput value={q} onChange={setQ} placeholder="Search analytical question…" />
          <div className="grid grid-cols-2 gap-2">
            <Select value={type} onChange={setType} options={typeOptions} />
            <Select value={nfilt} onChange={setNfilt} options={nOptions} />
          </div>
        </>
      }
      list={filtered.map((c, i) => (
        <ListRow
          key={c.id}
          active={i === sel}
          onClick={() => setSel(i)}
          status={<StatusDot ok={c.systems.uac_v5?.correct} />}
          badge={<CatBadge color="accent">{c.type}</CatBadge>}
          meta={`N=${c.n}`}
          title={c.question}
        />
      ))}
      detail={active ? <AnalyticalDetail c={active} systems={systems} sys_order={sys_order} memory={memory} /> : <EmptyDetail />}
    />
  )
}

function AnalyticalDetail({ c, systems, sys_order, memory }) {
  const uac = c.systems.uac_v5
  return (
    <DetailShell>
      <div className="flex flex-wrap items-center gap-2">
        <CatBadge color="accent">{c.type}</CatBadge>
        <CatBadge>N = {c.n}</CatBadge>
        <CatBadge>{c.answer_kind}</CatBadge>
        <span className="ml-auto font-mono text-[11px] text-slate-500">{c.id}</span>
      </div>
      <h3 className="mt-3 text-lg font-semibold leading-snug text-white">{c.question}</h3>

      <section className="mt-5">
        <SectionLabel n="b" text="Context — deterministic ground truth" />
        <p className="mt-2 rounded-xl border border-white/10 bg-ink-900/40 px-4 py-3 text-sm text-slate-400">
          Aggregate query over <span className="font-mono text-slate-200">{c.n}</span> synthetic <span className="font-mono text-slate-200">{c.type}</span> records.
          Scored by exact match — no LLM judge. This is precisely where top-k retrieval is structurally lossy.
        </p>
        <div className="mt-2 rounded-xl border border-ok/30 bg-emerald-500/5 px-4 py-3">
          <span className="font-mono text-[11px] uppercase tracking-wider text-ok">gold</span>
          <p className="mt-1 whitespace-pre-wrap font-mono text-sm text-emerald-100">{c.gold}</p>
        </div>
      </section>

      {/* UaC's structured memory (records -> typed state) */}
      <MemoryPanel mem={memory?.[c.id]} kind="analytical" />

      {/* UaC execution trace */}
      {uac?.log?.length > 0 && (
        <section className="mt-5">
          <SectionLabel n="c" text="UaC response — executed Python trace" />
          <div className="mt-2 space-y-3">
            {uac.log.map((step, i) => (
              <div key={i}>
                <CodeBlock code={step.code} caption={`${step.tool || 'python'} · step ${i + 1}`} />
                {step.stdout && (
                  <div className="mt-1.5 rounded-lg border border-white/10 bg-ink-950/60 px-3 py-2 font-mono text-[12px] text-emerald-300">
                    <span className="text-slate-600">→ </span>{step.stdout.trim()}
                  </div>
                )}
                {step.error && (
                  <div className="mt-1.5 rounded-lg border border-bad/30 bg-rose-500/5 px-3 py-2 font-mono text-[12px] text-rose-300">{step.error}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* all systems' answers */}
      <section className="mt-5">
        <SectionLabel n="d" text="Answers & grading — exact match" />
        <div className="mt-2 overflow-hidden rounded-xl border border-white/10">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-ink-900/60 text-left text-xs text-slate-500">
                <th className="px-4 py-2 font-medium">System</th>
                <th className="px-4 py-2 font-medium">Answer</th>
                <th className="px-4 py-2 font-medium text-right">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {sys_order.map((s) => {
                const rec = c.systems[s]
                if (!rec) return null
                const ours = systems[s]?.ours
                return (
                  <tr key={s} className={cx('border-t border-white/5', ours && 'bg-brand-400/[0.06]')}>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full" style={{ background: SYS_COLORS[s] || '#64748b' }} />
                        <span className={cx('font-medium', ours ? 'text-brand-200' : 'text-slate-300')}>{systems[s]?.name || s}</span>
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-300">{rec.prediction || <span className="italic text-slate-600">—</span>}</td>
                    <td className="px-4 py-2.5 text-right"><Verdict ok={rec.correct} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          <span className="font-mono">retrieval ranks; aggregation enumerates.</span> Any question whose answer depends on every relevant record sits outside what top-k can solve.
        </p>
      </section>
    </DetailShell>
  )
}

/* ------------------------------------------------------------------ */
/* Active Service explorer                                             */
/* ------------------------------------------------------------------ */
const ACTIVE_SYS = { uac_v5: { name: 'UaC + pipeline', ours: true }, mem0: { name: 'Mem0 (live)' }, a_mem: { name: 'A-MEM (live)' } }

function ActiveExplorer({ data, memory }) {
  const { cases } = data
  const [q, setQ] = useState('')
  const [diff, setDiff] = useState('all')
  const [cat, setCat] = useState('all')
  const [sel, setSel] = useState(0)

  const catOptions = useMemo(() => {
    const s = new Set(cases.map((c) => c.category))
    return [{ value: 'all', label: 'All categories' }, ...[...s].sort().map((t) => ({ value: t, label: t.replace(/_/g, ' ') }))]
  }, [cases])

  const filtered = useMemo(() => {
    const ql = q.toLowerCase()
    return cases.filter((c) => {
      if (diff !== 'all' && c.difficulty !== diff) return false
      if (cat !== 'all' && c.category !== cat) return false
      if (ql && !(`${c.description} ${c.category}`.toLowerCase().includes(ql))) return false
      return true
    })
  }, [cases, q, diff, cat])

  useEffect(() => setSel(0), [q, diff, cat])
  useKeyNav(sel, setSel, filtered.length)
  const active = filtered[sel]

  return (
    <Layout
      total={cases.length}
      count={filtered.length}
      sel={sel}
      setSel={setSel}
      filters={
        <>
          <SearchInput value={q} onChange={setQ} placeholder="Search scenario…" />
          <div className="grid grid-cols-2 gap-2">
            <Select value={diff} onChange={setDiff} options={[{ value: 'all', label: 'All difficulty' }, { value: 'standard', label: 'Standard (40)' }, { value: 'hard', label: 'Hard (20)' }]} />
            <Select value={cat} onChange={setCat} options={catOptions} />
          </div>
        </>
      }
      list={filtered.map((c, i) => (
        <ListRow
          key={c.id}
          active={i === sel}
          onClick={() => setSel(i)}
          status={<StatusDot ok={c.runs.uac_v5?.detected} />}
          badge={<CatBadge color={c.difficulty === 'hard' ? 'warn' : 'accent'}>{c.difficulty}</CatBadge>}
          meta={c.id}
          title={c.description}
        />
      ))}
      detail={active ? <ActiveDetail c={active} memory={memory} /> : <EmptyDetail />}
    />
  )
}

function ActiveDetail({ c, memory }) {
  return (
    <DetailShell>
      <div className="flex flex-wrap items-center gap-2">
        <CatBadge color={c.difficulty === 'hard' ? 'warn' : 'accent'}>{c.difficulty}</CatBadge>
        <CatBadge>{c.category.replace(/_/g, ' ')}</CatBadge>
        <span className="ml-auto font-mono text-[11px] text-slate-500">{c.id}</span>
      </div>
      <h3 className="mt-3 text-lg font-semibold leading-snug text-white">{c.description}</h3>

      {/* Context: sessions */}
      <section className="mt-5">
        <SectionLabel n="b" text="Context — facts seeded across sessions" />
        <div className="mt-2 space-y-2">
          {c.sessions.map((s, i) => {
            const isTrigger = c.trigger_session && s.session_id === c.trigger_session.session_id
            return (
              <div key={i} className={cx('rounded-xl border px-4 py-3', isTrigger ? 'border-warn/40 bg-amber-500/5' : 'border-white/10 bg-ink-900/40')}>
                <div className="flex items-center gap-2 text-[11px] text-slate-500">
                  <span className="font-mono">session {s.session_id}</span>
                  <span className="font-mono">{s.timestamp}</span>
                  {isTrigger && <span className="ml-auto chip border-warn/30 bg-warn/10 text-warn">⚡ trigger</span>}
                </div>
                <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{s.conversation}</p>
              </div>
            )
          })}
        </div>
      </section>

      {/* Expected alert + computation */}
      <section className="mt-5">
        <SectionLabel n="a" text="Benchmark — expected proactive alert" />
        <div className="mt-2 overflow-hidden rounded-xl border border-bad/30 bg-rose-500/5">
          <div className="flex items-center gap-2 border-b border-bad/20 bg-rose-500/10 px-4 py-2 font-mono text-[11px] text-bad">
            <span className="uppercase">{c.expected_alert?.severity}</span>·<span>{c.expected_alert?.type}</span>
          </div>
          <p className="px-4 py-3 text-sm leading-relaxed text-rose-100">{c.expected_alert?.message}</p>
          {c.expected_alert?.computation && (
            <div className="border-t border-bad/10 px-4 py-2 font-mono text-[12px] text-amber-200">{c.expected_alert.computation}</div>
          )}
        </div>
        {c.why_retrieval_fails && (
          <p className="mt-2 rounded-xl border border-white/10 bg-ink-900/40 px-4 py-3 text-xs leading-relaxed text-slate-400">
            <span className="font-semibold text-slate-300">Why retrieval fails: </span>{c.why_retrieval_fails}
          </p>
        )}
      </section>

      {/* UaC's extracted memory for this scenario */}
      <MemoryPanel mem={memory?.[c.id]} kind="active" />

      {/* System runs */}
      <section className="mt-5">
        <SectionLabel n="c" text="Responses & grading — did each system alert proactively?" />
        <div className="mt-2 space-y-2.5">
          {Object.entries(c.runs).map(([k, run]) => {
            const meta = ACTIVE_SYS[k] || { name: k }
            return (
              <div key={k} className={cx('rounded-xl border bg-ink-900/40', meta.ours ? 'border-brand-400/40 ring-1 ring-brand-400/20' : 'border-white/10')}>
                <div className="flex items-center gap-2 px-4 py-2.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: SYS_COLORS[k] || '#64748b' }} />
                  <span className={cx('text-sm font-semibold', meta.ours ? 'text-brand-200' : 'text-slate-200')}>{meta.name}</span>
                  {meta.ours && <span className="chip border-brand-400/30 bg-brand-400/10 text-[10px] text-brand-200">ours</span>}
                  <span className="ml-auto">
                    <Verdict ok={run.detected} label={run.detected ? 'Alert raised' : 'Missed'} />
                  </span>
                </div>
                <div className="border-t border-white/5 px-4 py-3">
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{run.response || <span className="italic text-slate-600">(no alert generated)</span>}</p>
                  {run.computation && meta.ours && (
                    <div className="mt-2 rounded-lg border border-white/10 bg-ink-950/60 px-3 py-2 font-mono text-[12px] text-amber-200">{run.computation}</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          UaC's constraint pipeline computes the alert deterministically in code; baselines must infer it from flat text, which fails on multi-step arithmetic.
        </p>
      </section>
    </DetailShell>
  )
}

/* ------------------------------------------------------------------ */
/* Top-level Explorer                                                 */
/* ------------------------------------------------------------------ */
function BenchPane({ bench }) {
  const { data, error } = useJson(bench.file)
  const { data: memory } = useJson(bench.mem) // lazy; optional — null until loaded / if absent
  if (error) return <p className="py-16 text-center text-bad">Failed to load {bench.file}.</p>
  if (!data) return <Spinner label={`Loading ${bench.label} cases…`} />
  if (bench.id === 'locomo' || bench.id === 'lme') return <QAExplorer data={data} kind={bench.id} memory={memory} />
  if (bench.id === 'analytical') return <AnalyticalExplorer data={data} memory={memory} />
  return <ActiveExplorer data={data} memory={memory} />
}

export default function Explorer() {
  const [tab, setTab] = useState('locomo')
  const bench = BENCHES.find((b) => b.id === tab)
  return (
    <section id="explorer" className="border-t border-white/5 py-20 sm:py-28">
      <div className="container-page">
        <div className="mx-auto max-w-3xl text-center">
          <span className="section-eyebrow">Interactive</span>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">Test-case explorer</h2>
          <p className="mt-4 text-pretty text-slate-400">
            Every graded case from all four benchmarks — the real data behind the paper. Pick any case to see its{' '}
            <span className="text-slate-200">context</span>, the <span className="text-slate-200">UaC memory</span> the
            pipeline extracted for it (Phase-1 facts + Phase-2 typed state), every system's{' '}
            <span className="text-slate-200">response</span>, and the <span className="text-slate-200">grading</span>.
          </p>
        </div>

        <div className="mt-10 flex flex-wrap justify-center gap-2">
          {BENCHES.map((b) => (
            <button
              key={b.id}
              onClick={() => setTab(b.id)}
              className={cx(
                'group rounded-xl border px-4 py-2.5 text-left transition',
                tab === b.id ? 'border-brand-400/50 bg-brand-400/10' : 'border-white/10 bg-white/[0.02] hover:border-white/20'
              )}
            >
              <div className={cx('text-sm font-semibold', tab === b.id ? 'text-brand-200' : 'text-slate-200')}>{b.label}</div>
              <div className="font-mono text-[10px] text-slate-500">{b.sub}</div>
            </button>
          ))}
        </div>

        <div className="mt-8">
          <BenchPane key={bench.id} bench={bench} />
        </div>
      </div>
    </section>
  )
}
