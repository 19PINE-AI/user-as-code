import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { CodeBlock, cx } from '../lib/ui.jsx'

function SectionHead({ eyebrow, title, children }) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <span className="section-eyebrow">{eyebrow}</span>
      <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h2>
      {children && <p className="mt-4 text-pretty text-slate-400">{children}</p>}
    </div>
  )
}

function reveal(i = 0) {
  return {
    initial: { opacity: 0, y: 18 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, margin: '-80px' },
    transition: { duration: 0.5, delay: i * 0.05 },
  }
}

/* ---------------- Two-phase pipeline diagram ---------------- */
function PipelineDiagram() {
  const nodes = [
    { k: 'conv', label: 'Conversations', sub: 'multi-session dialogue', color: 'from-slate-600/30 to-slate-700/30', ring: 'border-slate-500/40' },
    { k: 'p1', label: 'Phase 1 · Memorize', sub: 'append-only fact extraction\n~50 facts / session', color: 'from-brand-500/20 to-brand-600/10', ring: 'border-brand-400/40' },
    { k: 'p2', label: 'Phase 2 · Structure', sub: 'periodic LLM → typed Python\nregenerated from full corpus', color: 'from-accent-500/20 to-accent-600/10', ring: 'border-accent-400/40' },
    { k: 'out', label: 'User-as-Code', sub: 'dataclasses · constraints · manifest', color: 'from-emerald-500/20 to-emerald-600/10', ring: 'border-emerald-400/40' },
  ]
  return (
    <div className="relative grid gap-3 md:grid-cols-7 md:items-stretch">
      {nodes.map((n, idx) => (
        <React.Fragment key={n.k}>
          <motion.div {...reveal(idx)} className={cx('md:col-span-2 first:md:col-span-1', idx === 0 && 'md:col-span-1')}>
            <div className={cx('flex h-full flex-col justify-center rounded-2xl border bg-gradient-to-br p-4 text-center', n.color, n.ring)}>
              <div className="text-sm font-semibold text-white">{n.label}</div>
              <div className="mt-1 whitespace-pre-line text-[11px] leading-snug text-slate-400">{n.sub}</div>
            </div>
          </motion.div>
          {idx < nodes.length - 1 && (
            <div className="hidden items-center justify-center md:flex">
              <svg className="h-5 w-5 text-slate-600" viewBox="0 0 20 20" fill="currentColor"><path d="M7 5l6 5-6 5V5z" /></svg>
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  )
}

/* ---------------- Three capability tiers ---------------- */
const TIERS = [
  {
    id: 'recall',
    name: 'Recall',
    tag: 'attribute access',
    desc: 'What every memory system gives you — but here it is a typed field, not a similarity hit.',
    code: `>>> passport.number
'AB1234567'`,
    accent: 'brand',
  },
  {
    id: 'analytical',
    name: 'Analytical inference',
    tag: 'one-line aggregation',
    desc: 'Counts, group-bys, time-window filters — trivial in Python, structurally lossy under top-k retrieval.',
    code: `>>> sum(1 for t in trips
...     if t.is_international
...     and t.departure_date.year == 2025)
2`,
    accent: 'accent',
  },
  {
    id: 'active',
    name: 'Active service',
    tag: 'boolean check, fired on update',
    desc: 'A constraint the interpreter runs deterministically at every state change — the basis of proactive alerts.',
    code: `>>> (passport.expiry_date
...   - trips[0].departure_date).days >= 180
False   # 34 days — renew before Tokyo`,
    accent: 'ok',
  },
]

function Tiers() {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {TIERS.map((t, i) => {
        const color = t.accent === 'accent' ? 'text-accent-300' : t.accent === 'ok' ? 'text-ok' : 'text-brand-300'
        const ring = t.accent === 'accent' ? 'hover:border-accent-400/40' : t.accent === 'ok' ? 'hover:border-ok/40' : 'hover:border-brand-400/40'
        return (
          <motion.div key={t.id} {...reveal(i)} className={cx('card flex flex-col p-5 transition', ring)}>
            <div className="flex items-baseline justify-between">
              <h3 className={cx('text-lg font-semibold', color)}>{t.name}</h3>
              <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">({String.fromCharCode(97 + i)})</span>
            </div>
            <div className="mt-1 font-mono text-[11px] text-slate-500">{t.tag}</div>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">{t.desc}</p>
            <div className="mt-4">
              <CodeBlock code={t.code} />
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}

/* ---------------- Generate–Verify–Review loop ---------------- */
function GVRLoop() {
  const steps = [
    { n: '1', k: 'Generate', d: 'The coding agent writes a Python constraint against the typed state.', color: 'border-brand-400/40 text-brand-300' },
    { n: '2', k: 'Verify', d: 'Execute in a sandbox — results are deterministic, no LLM at check time.', color: 'border-accent-400/40 text-accent-300' },
    { n: '3', k: 'Review', d: 'The agent refines, persists, or promotes the check to a standing constraint.', color: 'border-emerald-400/40 text-ok' },
  ]
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {steps.map((s, i) => (
        <motion.div key={s.k} {...reveal(i)} className="card relative p-5">
          <div className={cx('grid h-9 w-9 place-items-center rounded-xl border font-mono text-sm font-bold', s.color)}>{s.n}</div>
          <h4 className="mt-3 font-semibold text-white">{s.k}</h4>
          <p className="mt-1.5 text-sm text-slate-400">{s.d}</p>
        </motion.div>
      ))}
    </div>
  )
}

/* ---------------- Retrieval channels ---------------- */
const CHANNELS = [
  { tag: '[STATE]', name: 'Structured code', d: 'The typed state.py of the routed domain, verbatim. Carries the analytical & constraint workloads.', note: 'roughly neutral for pure recall (−1.3pp, p=0.67)' },
  { tag: '[FACTS]', name: 'Fact-vector top-20', d: 'Cosine search over the append-only fact list. Recovers the long tail the schema compressed away.', note: 'load-bearing for recall (−9.3pp if removed, p=0.0008)' },
  { tag: '[ARCHIVE]', name: 'Raw archive top-10', d: 'Verbatim conversation chunks for direct-quote questions that hinge on exact wording.', note: 'load-bearing for recall (−7.3pp if removed, p=0.008)' },
]

/* ---------------- Worked example tabs ---------------- */
const EXAMPLES = {
  health: {
    label: 'Drug-allergy (health)',
    state: `# Phase 1 — append-only facts (never overwritten)
facts = [
  "[2024-03-01] User has SEVERE penicillin allergy (anaphylaxis)",
  "[2025-01-10] Dr. Chen prescribed amoxicillin 500mg, 10 days",
]

# Phase 2 — typed state (regenerated from full corpus)
medical_profile = MedicalProfile(
  allergies=[Allergy(allergen="Penicillin", severity="severe",
      reaction="Anaphylaxis", drug_class="penicillin")],
  current_medications=[
      Medication(name="Amoxicillin", drug_class="penicillin",
          prescriber="Dr. Chen", start_date=date(2025, 1, 10)),
  ],
)`,
    constraint: `def check_drug_allergy(profile) -> list[Alert]:
    alerts = []
    for med in profile.current_medications:
        for allergy in profile.allergies:
            if med.drug_class == allergy.drug_class:
                alerts.append(Alert(
                    severity="critical", domain="health",
                    message=f"DRUG-ALLERGY CONFLICT: {med.name} "
                            f"({med.drug_class}-class); patient has "
                            f"{allergy.severity} {allergy.allergen} "
                            f"allergy ({allergy.reaction})."))
    return alerts`,
    alert: `[CRITICAL/health]  DRUG-ALLERGY CONFLICT: Amoxicillin
(penicillin-class), prescribed 2025-01-10 by Dr. Chen;
patient has severe Penicillin allergy (Anaphylaxis).`,
  },
  travel: {
    label: 'Passport validity (travel)',
    state: `# Phase 2 — domains/travel/state.py
passport = PassportInfo(
  number="AB1234567", country="US",
  expiry_date=date(2025, 2, 18),
  full_name="Jessica Marie Thompson",
)
trips = [
  Trip(destination="Tokyo", country="JP",
       departure_date=date(2025, 1, 15),
       is_international=True),
]`,
    constraint: `def check():
    alerts = []
    for trip in trips:
        if not trip.is_international:
            continue
        days = (passport.expiry_date - trip.departure_date).days
        if days < 180:
            alerts.append({
                "severity": "critical", "domain": "travel",
                "message": f"Passport {passport.number} expires "
                    f"{passport.expiry_date} — only {days} days "
                    f"before {trip.destination}."})
    return alerts`,
    alert: `[CRITICAL/travel]  Passport AB1234567 expires
2025-02-18 — only 34 days before Tokyo on 2025-01-15.`,
  },
  finance: {
    label: 'Conflicting wires (finance)',
    state: `# Two pending transfers — same amount & recipient,
# different destinations, different requesters.
pending_transfers = [
  WireTransfer(amount=15000.00, recipient_name="Patricia Williams",
    destination_institution="Bank of America",
    requested_by="Patricia Williams (mother)"),
  WireTransfer(amount=15000.00, recipient_name="Patricia Williams",
    destination_institution="Wells Fargo",
    requested_by="James Thompson (husband)"),
]`,
    constraint: `def check_financial_authorization(transfers):
    groups = {}
    for t in transfers:
        if t.status != "pending": continue
        groups.setdefault((t.recipient_name, t.amount,
                           t.purpose), []).append(t)
    alerts = []
    for (recipient, amount, _), group in groups.items():
        dests = {t.destination_institution for t in group}
        if len(dests) > 1:
            alerts.append(Alert(severity="critical",
                message=f"CONFLICTING wire instructions for "
                        f"\${amount:,.0f} to {recipient}."))
    return alerts`,
    alert: `[CRITICAL/finance]  CONFLICTING wire transfer
instructions for $15,000.00 to Patricia Williams:
Bank of America (****3310) per mother vs. Wells Fargo
(****6654) per husband. Verify before sending.`,
  },
}

function WorkedExample() {
  const [tab, setTab] = useState('health')
  const ex = EXAMPLES[tab]
  return (
    <div className="card overflow-hidden">
      <div className="flex flex-wrap gap-1 border-b border-white/10 bg-ink-900/50 p-2">
        {Object.entries(EXAMPLES).map(([k, v]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={cx(
              'rounded-lg px-3.5 py-1.5 text-sm font-medium transition',
              tab === k ? 'bg-brand-400/15 text-brand-200' : 'text-slate-400 hover:text-slate-100'
            )}
          >
            {v.label}
          </button>
        ))}
      </div>
      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <div className="space-y-4">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-300">
              <span className="grid h-5 w-5 place-items-center rounded bg-brand-400/15 font-mono text-[10px]">1</span>
              Conversation → typed state
            </div>
            <CodeBlock code={ex.state} />
          </div>
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent-300">
              <span className="grid h-5 w-5 place-items-center rounded bg-accent-400/15 font-mono text-[10px]">2</span>
              Constraint the agent writes once
            </div>
            <CodeBlock code={ex.constraint} />
          </div>
        </div>
        <div className="lg:sticky lg:top-24 lg:self-start">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ok">
            <span className="grid h-5 w-5 place-items-center rounded bg-emerald-400/15 font-mono text-[10px]">3</span>
            Alert surfaced proactively — no query
          </div>
          <div className="overflow-hidden rounded-xl border border-bad/30 bg-rose-500/5">
            <div className="border-b border-bad/20 bg-rose-500/10 px-4 py-2 font-mono text-[11px] text-bad">
              ACTIVE_ALERTS · written into the manifest
            </div>
            <pre className="scroll-thin overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-rose-200">
              {ex.alert}
            </pre>
          </div>
          <p className="mt-4 rounded-xl border border-white/10 bg-ink-900/40 p-4 text-sm leading-relaxed text-slate-400">
            The relevant facts arrive in different sessions, possibly months apart, and{' '}
            <span className="text-slate-200">the user never asks the question</span>. Free-text retrieval
            would have to rank a year-old turn highly against an unrelated query — unreliable. A boolean
            check over a shared typed key is deterministic.
          </p>
        </div>
      </div>
    </div>
  )
}

/* ---------------- The contrast: bag-of-facts vs code ---------------- */
function Contrast() {
  const rows = [
    ['Conflicting reports', 'Coexist unresolved', 'Version history + typed override'],
    ['Aggregate over records', 'Top-k misses the population', 'One-line comprehension over all records'],
    ['Logical constraints', 'Cannot be expressed', 'Boolean check the interpreter runs'],
    ['Cross-session links', 'Need both turns in one window', 'Shared key joins them in the schema'],
  ]
  return (
    <div className="card overflow-hidden">
      <div className="grid grid-cols-3 gap-px bg-white/5 text-sm">
        <div className="bg-ink-850 px-4 py-3 font-semibold text-slate-300">Task</div>
        <div className="bg-ink-850 px-4 py-3 font-semibold text-bad">Bag-of-facts / retrieval</div>
        <div className="bg-ink-850 px-4 py-3 font-semibold text-ok">User as Code</div>
        {rows.map((r, i) => (
          <React.Fragment key={i}>
            <div className="bg-ink-900/60 px-4 py-3 font-medium text-slate-200">{r[0]}</div>
            <div className="bg-ink-900/40 px-4 py-3 text-slate-400">{r[1]}</div>
            <div className="bg-ink-900/40 px-4 py-3 text-slate-300">{r[2]}</div>
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

export default function Mechanism() {
  return (
    <section id="mechanism" className="border-t border-white/5 py-20 sm:py-28">
      <div className="container-page space-y-20">
        <div className="space-y-8">
          <SectionHead eyebrow="The mechanism" title="What “User as Code” actually means">
            Free-text and fact-store formats separate <em>representation</em> from <em>verification</em>.
            Any representation a Python interpreter can read directly collapses the two:{' '}
            <code className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[13px] text-brand-200">passport.expiry_date</code>{' '}
            can be stored <em>and</em> compared in one medium.
          </SectionHead>
          <motion.div {...reveal(1)}><Contrast /></motion.div>
        </div>

        <div className="space-y-8">
          <SectionHead eyebrow="Architecture" title="A two-phase pipeline">
            The decisive insight, isolated by ablation: <span className="text-slate-200">memorizing and structuring
            must be separate concerns.</span> Append-only extraction preserves coverage (+19pp on LOCOMO);
            periodic regeneration from the <em>complete</em> corpus adds typed structure without incremental loss.
          </SectionHead>
          <motion.div {...reveal(1)}><PipelineDiagram /></motion.div>
          <div className="grid gap-4 md:grid-cols-3">
            {[
              { t: 'Phase 1 · Memorize', d: 'An LLM extracts every fact as a flat string from each session — appended, never overwritten. Relative dates ("yesterday") resolved to absolute against the session timestamp.', tag: 'per session · append-only' },
              { t: 'Phase 2 · Structure', d: 'An LLM regenerates the entire typed Python from the accumulated facts: date() for dates, typed lists for collections, notes:list[str] as a safety net. No incremental drift.', tag: 'periodic · from full corpus' },
              { t: 'Archive', d: 'Raw conversation chunks indexed in ChromaDB as a retrieval fallback for direct-quote queries that hinge on exact phrasing.', tag: 'raw · fallback' },
            ].map((c, i) => (
              <motion.div key={c.t} {...reveal(i)} className="card p-5">
                <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{c.tag}</div>
                <h4 className="mt-1 font-semibold text-white">{c.t}</h4>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{c.d}</p>
              </motion.div>
            ))}
          </div>
        </div>

        <div className="space-y-8">
          <SectionHead eyebrow="Three tiers, one medium" title="Recall, aggregation, and proactive alerting">
            Once memory is code, three capabilities become three uses of the same typed state — each one line of Python.
          </SectionHead>
          <Tiers />
        </div>

        <div className="space-y-8">
          <SectionHead eyebrow="The active-service loop" title="Generate → Verify → Review">
            The interpreter is a tool the LLM uses to verify its own outputs, not a rule layer it must obey.
            When an ad-hoc check proves useful, the agent promotes it to a standing constraint whose alerts surface
            in <code className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[13px] text-brand-200">ACTIVE_ALERTS</code> at the start of every future session.
          </SectionHead>
          <GVRLoop />
        </div>

        <div className="space-y-8">
          <SectionHead eyebrow="End-to-end" title="Conversation → code → constraint → alert">
            Three real-deployment scenarios where the user is in genuine danger from agent error — and the alert
            depends on facts surfaced in different sessions, by different people, months apart.
          </SectionHead>
          <motion.div {...reveal(1)}><WorkedExample /></motion.div>
        </div>

        <div className="space-y-8">
          <SectionHead eyebrow="At query time" title="Multi-strategy retrieval">
            Three channels compose rather than compete — each covers a different failure mode of the others.
          </SectionHead>
          <div className="grid gap-4 md:grid-cols-3">
            {CHANNELS.map((c, i) => (
              <motion.div key={c.tag} {...reveal(i)} className="card p-5">
                <span className="chip border-brand-400/30 bg-brand-400/10 font-mono text-brand-200">{c.tag}</span>
                <h4 className="mt-3 font-semibold text-white">{c.name}</h4>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{c.d}</p>
                <div className="mt-3 border-t border-white/5 pt-3 font-mono text-[11px] text-slate-500">{c.note}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
