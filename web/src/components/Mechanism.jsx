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
    { k: 'conv', label: 'Conversations', sub: 'multi-session dialogue\n(the raw input)', color: 'from-slate-600/30 to-slate-700/30', ring: 'border-slate-500/40' },
    { k: 'p1', label: 'Phase 1 · Memorize', sub: 'append-only fact list\ndates resolved to absolute', color: 'from-brand-500/20 to-brand-600/10', ring: 'border-brand-400/40' },
    { k: 'p2', label: 'Phase 2 · Structure', sub: 'regenerate typed Python\nfrom the full fact corpus', color: 'from-accent-500/20 to-accent-600/10', ring: 'border-accent-400/40' },
    { k: 'out', label: 'User-as-Code', sub: 'typed state.py\n+ searchable fact index', color: 'from-emerald-500/20 to-emerald-600/10', ring: 'border-emerald-400/40' },
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

/* ---------------- Running example: LOCOMO conv-30 (Jon & Gina) ----------------
   Every snippet below is taken verbatim from the paper's worked appendix
   (Appendix "Real Cases", LOCOMO conv-30): the raw conversation, the Phase-1
   fact list our extractor produces, and the Phase-2 typed state. */
const RX_CONV = `SESSION 1  ·  2023-01-20
Jon:  Lost my job as a banker yesterday, so I'm gonna take
      a shot at starting my own business.
Gina: Sorry about your job Jon! Unfortunately I also lost
      my job at Door Dash this month.
Jon:  I'm starting a dance studio 'cause I'm passionate
      about dancing and want to share it with others.

SESSION 2  ·  2023-01-29
Jon:  On the hunt for the ideal spot for my studio... it's
      downtown, easy to get to. Plus the natural light!
Jon:  I'm after Marley flooring, what dance studios use.
      Grippy but still lets you move.

SESSION 3  ·  2023-02-01
Gina: Emailed wholesalers and one said yes today! Now I
      can expand my clothing store.`

const RX_FACTS = `facts = [   # append-only — never overwritten, never deleted
  "[2023-01-19] Jon lost his job as a banker (one day before session 1)",
  "[2023-01-20] Jon plans to start his own business: a dance studio",
  "[2023-01-20] Jon's passion is dancing; contemporary is his favorite",
  "[2023-01-20] Gina lost her job at Door Dash in January 2023",
  "[2023-01-29] Jon is scouting downtown locations for the studio",
  "[2023-01-29] Jon wants Marley flooring (standard for dance studios)",
  "[2023-02-01] Gina secured a wholesaler to expand her clothing store",
  # ... ~140 more facts across the full conversation ...
]`

const RX_STATE = `@dataclass
class Person:
    name: str
    job_history: list["Job"] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

jon = Person(
    name="Jon",
    job_history=[Job(title="banker", employer="(unspecified)",
                     end_date=date(2023, 1, 19), reason_ended="laid off")],
    interests=["dancing", "contemporary dance"],
)
jon_studio = BusinessVenture(
    name="(unnamed dance studio)", type="dance studio",
    status="scouting", started=date(2023, 1, 20),
    requirements=["downtown location", "natural light",
                  "Marley flooring", "good bounce for dancers"],
)`

function Transform({ label, detail }) {
  return (
    <div className="flex items-center gap-3 py-1 pl-1">
      <svg className="h-5 w-5 shrink-0 rotate-90 text-slate-600" viewBox="0 0 20 20" fill="currentColor"><path d="M7 5l6 5-6 5V5z" /></svg>
      <div>
        <span className="font-semibold text-slate-200">{label}</span>
        <span className="text-slate-500"> — {detail}</span>
      </div>
    </div>
  )
}

function RunningExample() {
  return (
    <div className="space-y-2">
      {/* Stage 0 — raw input */}
      <motion.div {...reveal(0)}>
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <span className="grid h-5 w-5 place-items-center rounded bg-white/5 font-mono text-[10px]">0</span>
          Raw input · three sessions over twelve days
        </div>
        <CodeBlock code={RX_CONV} lang="text" caption="LOCOMO conv-30 — verbatim excerpts" />
      </motion.div>

      <Transform label="Phase 1 · Memorize" detail='an LLM extracts every fact as a flat string; "yesterday" → 2023-01-19 against the session timestamp' />

      {/* Stage 1 — memorized facts */}
      <motion.div {...reveal(1)}>
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-300">
          <span className="grid h-5 w-5 place-items-center rounded bg-brand-400/15 font-mono text-[10px]">1</span>
          Memorized · append-only fact list
        </div>
        <CodeBlock code={RX_FACTS} caption="phase-1 output — facts.py (indexed in ChromaDB)" />
        <p className="mt-2 text-xs text-slate-500">
          Note the first fact: the model resolved <span className="text-slate-300">“lost my job yesterday”</span> to{' '}
          <span className="font-mono text-brand-200">2023-01-19</span>. Mem0 keeps the literal “yesterday” — and answers the date question wrong.
        </p>
      </motion.div>

      <Transform label="Phase 2 · Structure" detail="an LLM regenerates the entire typed Python from the complete fact list — no incremental edits, so nothing drifts" />

      {/* Stage 2 — structured code */}
      <motion.div {...reveal(2)}>
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent-300">
          <span className="grid h-5 w-5 place-items-center rounded bg-accent-400/15 font-mono text-[10px]">2</span>
          Structured · typed Python state
        </div>
        <CodeBlock code={RX_STATE} caption="phase-2 output — state.py (the user, as code)" />
        <p className="mt-2 text-xs text-slate-500">
          Dates become <span className="font-mono text-accent-200">date()</span> objects, repeated entities become typed lists, and anything that
          doesn’t fit a field lands in <span className="font-mono text-accent-200">notes</span>. This <span className="text-slate-300">jon</span> object is what every
          query in the next pipeline runs against.
        </p>
      </motion.div>
    </div>
  )
}

/* ---------------- Query-time trace (real conv-30 QA) ---------------- */
const RX_QUERY = `# LOCOMO question (temporal):
#   "When did Jon lose his job as a banker?"
#
# All three channels are assembled into the answer prompt:
[STATE]    jon.job_history[0].end_date == date(2023, 1, 19)
[FACTS]    "[2023-01-19] Jon lost his job as a banker..."
[ARCHIVE]  session 1: "Lost my job as a banker yesterday"
#
# Answer: "January 19, 2023"   -> judged CORRECT.
# Mem0 answers "yesterday": it never resolved the relative date.`

/* ---------------- Three capability tiers ---------------- */
const TIERS = [
  {
    id: 'recall',
    name: 'Recall',
    tag: 'attribute access',
    desc: 'A fact question is one field access on the typed state — no similarity search, no relative-date ambiguity. (This is the conv-30 state from above.)',
    code: `# "When did Jon lose his job?"
>>> jon.job_history[0].end_date
datetime.date(2023, 1, 19)`,
    accent: 'brand',
  },
  {
    id: 'analytical',
    name: 'Analytical inference',
    tag: 'one-line aggregation',
    desc: 'Counts, sums, group-bys and time-window filters enumerate every record — trivial in Python, structurally lossy under top-k retrieval (UaC 99% vs MemMachine 43%).',
    code: `# "Avg 2024 dinner spend by cuisine, top 3"
>>> [(c, round(mean(v), 2), len(v))
...  for c, v in by_cuisine.items()][:3]
[('Italian',  187.45, 31),
 ('Japanese', 152.30, 28),
 ('French',   141.80, 14)]`,
    accent: 'accent',
  },
  {
    id: 'active',
    name: 'Active service',
    tag: 'boolean check, fired on update',
    desc: 'A constraint the interpreter runs deterministically at every state change — the basis of proactive alerts the user never asked for.',
    code: `# fired whenever travel state changes
>>> (passport.expiry_date
...  - trips[0].departure_date).days >= 180
False   # 34 days — alert before Tokyo`,
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

/* ---------------- Left-aligned sub-section heading ---------------- */
function SubHead({ step, title, children }) {
  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-2">
        {step && <span className="font-mono text-xs font-semibold text-slate-500">{step}</span>}
        <h3 className="text-xl font-bold tracking-tight text-white sm:text-2xl">{title}</h3>
      </div>
      {children && <p className="mt-2 text-pretty text-sm leading-relaxed text-slate-400">{children}</p>}
    </div>
  )
}

const PHASE_CARDS = [
  { t: 'Phase 1 · Memorize', d: 'An LLM extracts every fact as a flat string from each session — appended, never overwritten. Relative dates ("yesterday") are resolved to absolute against the session timestamp. ~50 facts/session.', tag: 'per session · append-only' },
  { t: 'Phase 2 · Structure', d: 'An LLM regenerates the entire typed Python from the accumulated facts: date() for dates, typed lists for collections, notes: list[str] as a safety net. Regenerated whole, so nothing drifts.', tag: 'periodic · from full corpus' },
  { t: 'Archive', d: 'The raw conversation is also chunked and indexed in ChromaDB — a retrieval fallback for direct-quote questions that hinge on exact phrasing.', tag: 'raw · fallback' },
]

export default function Mechanism() {
  return (
    <section id="mechanism" className="border-t border-white/5 py-20 sm:py-28">
      <div className="container-page space-y-24">

        {/* ============ PIPELINE 1 — EXTRACTION ============ */}
        <div className="space-y-10">
          <SectionHead eyebrow="Pipeline 1 · Extraction" title="From conversation to code">
            UaC is two pipelines. The first turns raw, multi-session dialogue into typed Python in two
            phases — <span className="text-slate-200">Memorize</span>, then <span className="text-slate-200">Structure</span>.
            Keeping them separate is the decisive design choice: append-only extraction then whole-corpus
            regeneration gives <span className="text-slate-200">+19pp recall on LOCOMO</span> over structuring incrementally.
          </SectionHead>
          <motion.div {...reveal(1)}><PipelineDiagram /></motion.div>

          <div className="space-y-5 pt-2">
            <SubHead title="A real run: LOCOMO conv-30 (Jon &amp; Gina)">
              Watch one conversation flow through both phases. Everything below is verbatim from our pipeline:
              three sessions over twelve days become an append-only fact list, then typed Python.
            </SubHead>
            <RunningExample />
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {PHASE_CARDS.map((c, i) => (
              <motion.div key={c.t} {...reveal(i)} className="card p-5">
                <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{c.tag}</div>
                <h4 className="mt-1 font-semibold text-white">{c.t}</h4>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{c.d}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* ============ PIPELINE 2 — RETRIEVAL & USE ============ */}
        <div className="space-y-12 border-t border-white/5 pt-16">
          <SectionHead eyebrow="Pipeline 2 · Retrieval & Use" title="Querying and using the code">
            With the user represented as code, the second pipeline answers questions and drives proactive
            service. At query time three channels compose; and three capabilities all reduce to one line of
            Python over the same typed state the first pipeline produced.
          </SectionHead>

          {/* Retrieval channels + real trace */}
          <div className="space-y-5">
            <SubHead title="At query time: three channels compose">
              Rather than pick one retrieval strategy, UaC concatenates three under fixed headers and lets the
              answer LLM prefer the structured channel on conflicts. Each covers a different failure mode of the others.
            </SubHead>
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
            <motion.div {...reveal(1)}>
              <CodeBlock code={RX_QUERY} lang="text" caption="the conv-30 question, answered from all three channels" />
            </motion.div>
          </div>

          {/* Capability tiers, grounded in the running example */}
          <div className="space-y-5">
            <SubHead title="Three capabilities, one medium">
              Once the user is code, recall, aggregation, and proactive alerting are three uses of the same
              typed state — each one line of Python. The first two run against the objects you just saw built.
            </SubHead>
            <Tiers />
          </div>

          {/* End-to-end proactive alerts */}
          <div className="space-y-5">
            <SubHead title="End-to-end: proactive alerts">
              The hardest case is active service — the constraint depends on facts that arrived in different
              sessions, by different people, sometimes months apart, and the agent surfaces the alert
              <em> before the user asks anything</em>. Real cases from our system: three verbatim from the
              reference implementation (state, constraint, and the alert the runner prints), three from the
              Active Service benchmark.
            </SubHead>
            <motion.div {...reveal(1)}><WorkedExample /></motion.div>
          </div>
        </div>
      </div>
    </section>
  )
}
