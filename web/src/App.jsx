import React, { useEffect, useState, Suspense, lazy } from 'react'
import { cx, Spinner } from './lib/ui.jsx'
import Hero from './components/Hero.jsx'
import Mechanism from './components/Mechanism.jsx'
import Footer from './components/Footer.jsx'

// Heavy below-the-fold sections (Recharts + data) are split out of the initial bundle.
const Results = lazy(() => import('./components/Results.jsx'))
const Explorer = lazy(() => import('./components/Explorer.jsx'))

const SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'mechanism', label: 'Mechanism' },
  { id: 'results', label: 'Results' },
  { id: 'explorer', label: 'Explorer' },
]

function Nav() {
  const [active, setActive] = useState('overview')
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) setActive(e.target.id)
        })
      },
      { rootMargin: '-45% 0px -50% 0px' }
    )
    SECTIONS.forEach((s) => {
      const el = document.getElementById(s.id)
      if (el) obs.observe(el)
    })
    return () => obs.disconnect()
  }, [])

  return (
    <header
      className={cx(
        'fixed inset-x-0 top-0 z-50 transition-all duration-300',
        scrolled ? 'border-b border-white/10 bg-ink-950/80 backdrop-blur-xl' : 'border-b border-transparent'
      )}
    >
      <nav className="container-page flex h-16 items-center justify-between">
        <a href="#overview" className="group flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand-400 to-accent-500 font-mono text-sm font-bold text-ink-950">
            {'{}'}
          </span>
          <span className="font-mono text-sm font-semibold tracking-tight text-slate-100">
            User<span className="text-brand-300">·</span>as<span className="text-brand-300">·</span>Code
          </span>
        </a>
        <div className="hidden items-center gap-1 md:flex">
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className={cx(
                'rounded-lg px-3 py-1.5 text-sm font-medium transition',
                active === s.id ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-slate-100'
              )}
            >
              {s.label}
            </a>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <a
            href="https://github.com/19PINE-AI/user-as-code"
            target="_blank"
            rel="noreferrer"
            className="btn border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 .5C5.4.5 0 5.9 0 12.5c0 5.3 3.4 9.8 8.2 11.4.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 016 0C17.3 4.7 18.3 5 18.3 5c.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0024 12.5C24 5.9 18.6.5 12 .5z" />
            </svg>
            <span className="hidden sm:inline">GitHub</span>
          </a>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="Toggle navigation menu"
            className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-slate-200 md:hidden"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {menuOpen ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>
      </nav>

      {/* Mobile dropdown */}
      <div
        className={cx(
          'overflow-hidden border-t border-white/10 bg-ink-950/95 backdrop-blur-xl transition-[max-height] duration-300 md:hidden',
          menuOpen ? 'max-h-72' : 'max-h-0 border-t-transparent'
        )}
      >
        <div className="container-page flex flex-col py-2">
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              onClick={() => setMenuOpen(false)}
              className={cx(
                'rounded-lg px-3 py-2.5 text-sm font-medium transition',
                active === s.id ? 'bg-white/10 text-white' : 'text-slate-400'
              )}
            >
              {s.label}
            </a>
          ))}
        </div>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <div className="min-h-screen overflow-x-hidden">
      <Nav />
      <main>
        <Hero />
        <Mechanism />
        <Suspense fallback={<div className="container-page py-24"><Spinner label="Loading section…" /></div>}>
          <Results />
          <Explorer />
        </Suspense>
      </main>
      <Footer />
    </div>
  )
}
