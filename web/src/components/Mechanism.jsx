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
    <div className="relative flex flex-col gap-3 md:flex-row md:items-stretch">
      {nodes.map((n, idx) => (
        <React.Fragment key={n.k}>
          <motion.div {...reveal(idx)} className="flex-1">
            <div className={cx('flex h-full flex-col justify-center rounded-2xl border bg-gradient-to-br p-4 text-center', n.color, n.ring)}>
              <div className="text-sm font-semibold text-white">{n.label}</div>
              <div className="mt-1 whitespace-pre-line text-[11px] leading-snug text-slate-400">{n.sub}</div>
            </div>
          </motion.div>
          {idx < nodes.length - 1 && (
            <div className="flex shrink-0 items-center justify-center">
              <svg className="h-5 w-5 rotate-90 text-slate-600 md:rotate-0" viewBox="0 0 20 20" fill="currentColor"><path d="M7 5l6 5-6 5V5z" /></svg>
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

/* ---------------- Retrieval channels ---------------- */
const CHANNELS = [
  { tag: '[STATE]', name: 'Structured code', d: 'The typed state.py of the routed domain, verbatim. Carries the analytical & constraint workloads.', note: 'roughly neutral for pure recall (−1.3pp, p=0.67)' },
  { tag: '[FACTS]', name: 'Fact-vector top-20', d: 'Cosine search over the append-only fact list. Recovers the long tail the schema compressed away.', note: 'load-bearing for recall (−9.3pp if removed, p=0.0008)' },
  { tag: '[ARCHIVE]', name: 'Raw archive top-10', d: 'Verbatim conversation chunks for direct-quote questions that hinge on exact wording.', note: 'load-bearing for recall (−7.3pp if removed, p=0.008)' },
]

/* ---------------- Worked example tabs ---------------- */
// Every case below is real output from our system: the three "prototype"
// cases are taken verbatim from the reference implementation (state.py,
// the constraint module, and the runner's printed alert); the others are
// scenarios from the Active Service benchmark (evaluation/
// active_service_scenarios.json), with the gold alert quoted verbatim.
const EXAMPLES = {
  travel: {
    label: 'Passport · travel',
    source: 'prototype · constraints/travel_readiness.py',
    severity: 'critical',
    state: `# domains/travel/state.py — generated by Phase 2 (verbatim)
passport = PassportInfo(
    number="AB1234567", country="US",
    expiry_date=date(2025, 2, 18),
    full_name="Jessica Marie Thompson",
)
trips = [
    Trip(destination="Tokyo", country="JP",
         departure_date=date(2025, 1, 15),
         flight_number="JAL-9823", is_international=True),
    Trip(destination="Mexico City", country="MX",
         departure_date=date(2025, 3, 10),
         flight_number="AA-4561", is_international=True),
]`,
    constraint: `# constraints/travel_readiness.py
for trip in trips:
    if not trip.is_international:
        continue
    days_remaining = (passport.expiry_date - trip.departure_date).days
    if days_remaining < 180:            # 6-month validity rule
        alerts.append({
            "severity": "critical", "domain": "travel",
            "message": f"Passport {passport.number} expires "
                f"{passport.expiry_date.isoformat()} -- only "
                f"{days_remaining} days before {trip.destination} "
                f"trip on {trip.departure_date.isoformat()} "
                f"(requires 180-day validity). "
                f"Flight {trip.flight_number} is at risk."})`,
    alert: `[CRITICAL/travel]  Passport AB1234567 expires 2025-02-18
-- only 34 days before Tokyo trip on 2025-01-15 (requires
180-day validity). Flight JAL-9823 is at risk.`,
    why: `The passport was logged in one session and the trip booked in another. The alert needs date arithmetic and the 6-month rule — no embedding similarity search can do calendar math.`,
  },
  health: {
    label: 'Drug allergy · health',
    source: 'prototype · constraints/health_safety.py',
    severity: 'critical',
    state: `# domains/health/state.py — generated by Phase 2 (verbatim)
medical_profile = MedicalProfile(
    allergies=[
        Allergy(allergen="Penicillin", severity="moderate",
                reaction="Rash and hives", drug_class="penicillin"),
    ],
    current_medications=[
        Medication(name="Amoxicillin", dosage="500mg",
            frequency="three times daily", drug_class="penicillin",
            prescriber="Dr. Robert Chen",
            start_date=date(2025, 1, 10)),
    ],
)`,
    constraint: `# constraints/health_safety.py
for med in profile.current_medications:
    for allergy in profile.allergies:
        # amoxicillin is a penicillin-class drug
        if (med.drug_class and allergy.drug_class
                and med.drug_class.lower() == allergy.drug_class.lower()):
            alerts.append({
                "severity": "critical", "domain": "health",
                "message": f"DRUG-ALLERGY CONFLICT: {med.name} "
                    f"({med.dosage}, {med.frequency}) is contraindicated "
                    f"-- patient has a {allergy.severity} allergy to "
                    f"{allergy.allergen} (reaction: {allergy.reaction}). "
                    f"Prescribed by {med.prescriber} on "
                    f"{med.start_date.isoformat()}. "
                    f"Contact prescriber immediately."})`,
    alert: `[CRITICAL/health]  DRUG-ALLERGY CONFLICT: Amoxicillin
(500mg, three times daily) is contraindicated -- patient
has a moderate allergy to Penicillin (reaction: Rash and
hives). Prescribed by Dr. Robert Chen on 2025-01-10.
Contact prescriber immediately.`,
    why: `Allergy and prescription arrive months apart. The link is that amoxicillin is a penicillin-class drug — a typed-key match (drug_class), not a string similarity between "Amoxicillin" and "Penicillin".`,
  },
  finance: {
    label: 'Wire conflict · finance',
    source: 'prototype · constraints/financial_authorization.py',
    severity: 'critical',
    state: `# domains/finance/state.py — generated by Phase 2 (verbatim)
pending_transfers = [
    WireTransfer(amount=15000.00, recipient_name="Patricia Williams",
        destination_institution="Bank of America",
        destination_account_last_four="3310", purpose="Gift to mother",
        requested_by="Patricia Williams (mother)", status="pending"),
    WireTransfer(amount=15000.00, recipient_name="Patricia Williams",
        destination_institution="Wells Fargo",
        destination_account_last_four="6654", purpose="Gift to mother",
        requested_by="James Thompson (husband)", status="pending"),
]`,
    constraint: `# constraints/financial_authorization.py
groups = {}
for t in pending_transfers:
    if t.status != "pending": continue
    groups.setdefault((t.recipient_name, t.amount, t.purpose), []).append(t)

for (recipient, amount, _), transfers in groups.items():
    dests = {(t.destination_institution,
              t.destination_account_last_four) for t in transfers}
    if len(transfers) >= 2 and len(dests) > 1:
        alerts.append({
            "severity": "critical", "domain": "finance",
            "message": f"CONFLICTING wire transfer instructions for "
                f"\${amount:,.2f} to {recipient}: " + " vs. ".join(
                    f"{t.destination_institution} "
                    f"(****{t.destination_account_last_four}) "
                    f"per {t.requested_by}" for t in transfers)
                + ". Verify correct destination with the account holder "
                  "before sending."})`,
    alert: `[CRITICAL/finance]  CONFLICTING wire transfer instructions
for $15,000.00 to Patricia Williams: Bank of America
(****3310) per Patricia Williams (mother) vs. Wells Fargo
(****6654) per James Thompson (husband). Verify correct
destination with the account holder before sending.`,
    why: `Her mother and her husband each gave a different destination bank, in separate sessions. Only a group-by over typed fields (recipient, amount, purpose) surfaces that the two pending transfers disagree.`,
  },
  schedule: {
    label: 'Double-booking · schedule',
    source: 'Active Service benchmark · schedule_02',
    severity: 'critical',
    state: `# Phase 1 — facts from two sessions, two weeks apart
facts = [
  "[2024-10-28] Anniversary dinner: Chez Laurent, Sat Nov 15, 7:00 PM",
  "[2024-11-10] Dinner w/ college roommate: Steakhouse 55, Nov 15, 7:30 PM",
]

# Phase 2 — typed state
reservations = [
  Reservation(venue="Chez Laurent",  start=datetime(2024, 11, 15, 19, 0)),
  Reservation(venue="Steakhouse 55", start=datetime(2024, 11, 15, 19, 30)),
]`,
    constraint: `# pairwise overlap check on the same evening
for a, b in combinations(reservations, 2):
    if a.start.date() != b.start.date():
        continue
    gap_hours = abs((a.start - b.start).total_seconds()) / 3600
    if gap_hours < 2:                   # overlapping seatings
        alerts.append({
            "severity": "critical", "domain": "schedule",
            "message": f"Double booking on {a.start:%B %-d}: "
                f"{a.venue} at {a.start:%-I %p} conflicts with "
                f"{b.venue} at {b.start:%-I:%M %p}. "
                f"Reschedule one of them."})`,
    alert: `[CRITICAL/schedule]  You already have your anniversary
dinner reservation at Chez Laurent on November 15 at 7 PM.
The dinner with your college roommate at Steakhouse 55 at
7:30 PM on the same evening conflicts directly. You'll
need to reschedule one of them.`,
    why: `The two bookings live in completely different conversations — an anniversary and a college reunion, different topics and people. Matching them needs a date overlap, not topical similarity.`,
  },
  deadline: {
    label: 'License expiry · deadline',
    source: 'Active Service benchmark · deadline_06',
    severity: 'critical',
    state: `# Phase 1 — facts, five months apart
facts = [
  "[2024-07-18] Driver's license expires 2024-12-15 (renewal postponed)",
  "[2024-12-01] Road trip LA -> Vegas planned for 2024-12-20",
]

# Phase 2 — typed state
license = DriverLicense(expiry_date=date(2024, 12, 15))
road_trips = [RoadTrip(route="LA -> Vegas", date=date(2024, 12, 20))]`,
    constraint: `for trip in road_trips:
    if license.expiry_date < trip.date:
        days = (trip.date - license.expiry_date).days
        alerts.append({
            "severity": "critical", "domain": "deadline",
            "message": f"License expires {license.expiry_date}, "
                f"{days} days before your {trip.route} road trip on "
                f"{trip.date}. Driving on an expired license is illegal "
                f"and may void insurance. Renew before "
                f"{license.expiry_date}."})`,
    alert: `[CRITICAL/deadline]  Your driver's license expires
December 15, 2024, and your road trip to Vegas is
December 20 -- 5 days after expiration. Driving with an
expired license is illegal and your car insurance may not
cover you in an accident. You said back in July you'd
'get around to' renewing it. You need to visit the DMV or
renew online before December 15.`,
    why: `A casually-mentioned expiry date has to be connected to a future driving activity, then compared. The road-trip session is about route recommendations, not ID validity — retrieval has no reason to surface the license turn.`,
  },
  fooddrug: {
    label: 'Food–drug · health',
    source: 'Active Service benchmark · health_03',
    severity: 'warning',
    state: `# Phase 1 — facts, ~8 months apart
facts = [
  "[2024-07-12] Prescribed simvastatin 40mg daily for cholesterol",
  "[2025-03-01] Started drinking fresh grapefruit juice every morning",
]

# Phase 2 — typed state
medications = [Medication(name="Simvastatin", dosage="40mg",
    cyp3a4_substrate=True)]
diet = DietProfile(daily_items=["grapefruit juice"])`,
    constraint: `# grapefruit inhibits CYP3A4, which metabolizes simvastatin
CYP3A4_INHIBITORS = {"grapefruit", "grapefruit juice"}
for med in medications:
    if not med.cyp3a4_substrate:
        continue
    hits = CYP3A4_INHIBITORS & set(diet.daily_items)
    if hits:
        alerts.append({
            "severity": "warning", "domain": "health",
            "message": f"{', '.join(sorted(hits))} inhibits CYP3A4, "
                f"which metabolizes {med.name} -- elevated drug levels "
                f"raise the risk of muscle damage. Avoid grapefruit or "
                f"ask your doctor about a different statin."})`,
    alert: `[WARNING/health]  Grapefruit juice significantly increases
simvastatin levels in your blood by inhibiting the CYP3A4
enzyme that metabolizes the drug. This can increase the
risk of serious side effects including muscle damage
(rhabdomyolysis). You should avoid grapefruit and
grapefruit juice while taking simvastatin, or ask your
doctor about switching to a statin that isn't affected
(like rosuvastatin or pravastatin).`,
    why: `"Grapefruit juice" and "simvastatin" have zero semantic similarity, so retrieval never co-ranks them — but linking a dietary change to a stored medication through the CYP3A4 pathway is one boolean check over a typed field.`,
  },
}

function WorkedExample() {
  const [tab, setTab] = useState('travel')
  const ex = EXAMPLES[tab]
  const warn = ex.severity === 'warning'
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
      <div className="border-b border-white/5 bg-ink-900/30 px-4 py-2 font-mono text-[11px] text-slate-500">
        source: <span className="text-slate-300">{ex.source}</span>
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
          <div className={cx('overflow-hidden rounded-xl border', warn ? 'border-amber-400/30 bg-amber-500/5' : 'border-bad/30 bg-rose-500/5')}>
            <div className={cx('border-b px-4 py-2 font-mono text-[11px]', warn ? 'border-amber-400/20 bg-amber-500/10 text-amber-300' : 'border-bad/20 bg-rose-500/10 text-bad')}>
              ACTIVE_ALERTS · written into the manifest
            </div>
            <pre className={cx('scroll-thin overflow-x-auto whitespace-pre-wrap p-4 font-mono text-[12.5px] leading-relaxed', warn ? 'text-amber-200' : 'text-rose-200')}>
              {ex.alert}
            </pre>
          </div>
          <p className="mt-4 rounded-xl border border-white/10 bg-ink-900/40 p-4 text-sm leading-relaxed text-slate-400">
            <span className="font-semibold text-slate-300">Why retrieval misses it: </span>
            {ex.why}
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
          <SectionHead eyebrow="End-to-end" title="Conversation → code → constraint → alert">
            Real cases from our system — three taken verbatim from the reference implementation (state,
            constraint, and the alert the runner prints), three from the Active Service benchmark. In each,
            the constraint depends on facts that arrived in different sessions, by different people, sometimes
            months apart, and the agent surfaces the alert <em>before the user asks anything</em>.
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
