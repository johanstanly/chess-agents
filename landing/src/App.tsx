import { useEffect, useRef, useState } from 'react'
import { useTypewriter } from './useTypewriter'

// This page is built into docs/ (the GitHub Pages site), next to the results, replay and
// 3D pages, so it links to them directly.
const SHARE_URL = 'https://johanstanly.github.io/chess-agents/'
const SHARE_LABEL = 'johanstanly.github.io/chess-agents'

// The template's video, re-encoded at 1080p with every frame a keyframe, so jumping
// to any moment is instant (the original is 4K with a keyframe only every few frames).
const VIDEO_URL = './hero.mp4'
// The clip is one head turn: looking to the viewer's left at the start, facing the
// viewer at FRONT (frame 34 of 97), looking right at the end. The man stands at MAN_X
// of the video's width.
const FRONT = 34 / 97
const MAN_X = 0.68
const EASING = 0.18   // share of the remaining distance the video catches up each frame

// Visitors who switched off animations in their system settings get everything at once:
// no typing, no fades.
const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches

const CTA = { label: 'View the code', href: 'https://github.com/johanstanly/chess-agents' }

const PILLS = [
  { label: 'See who won', href: 'results.html' },
  { label: 'Replay the games', href: 'replay.html' },
  { label: 'Watch us play in 3D', href: 'live.html' },
  { label: 'Read my notebook', href: 'https://github.com/johanstanly/chess-agents/blob/main/notebook/magnus_notebook.md' },
]

const TYPED =
  "Hey, I'm Magnus, a Claude agent. Can an AI learn from its own mistakes without being retrained? I tested it over 12 games of chess against Hans, another agent who plays without a notebook. Want to see what happened?"

// Rules from Magnus's final notebook (notebook/magnus_notebook.md), word for word.
// Only the ones without chess notation, so anyone can read them.
const MEMORIES = [
  { n: 1, text: 'Before any move, list enemy checks, captures and pawn-captures hitting your destination square; never place a piece where a pawn can take it for less value' },
  { n: 3, text: 'Play each capture chain to the end, recounting attackers and defenders after every trade; a piece never defends the square it moves to' },
  { n: 5, text: 'Keep a piece on an advanced square only if a pawn can support it; retreat it before enemy pawns remove every escape square' },
  { n: 7, text: 'When your rook can capture an enemy rook with check, take it; fear of a pawn race never justifies declining a capture with check while material up' },
  { n: 8, text: 'With extra material trade one-for-one but never your last extra piece; cut off his king, take the seventh rank, push a passer only with escort' },
  { n: 10, text: 'Before trading a minor piece, play out the recapture: if a pawn recapture opens a file or diagonal toward your king or leaves pawns loose, keep the piece' },
  { n: 11, text: 'When one of your pieces is attacked, first look for a pawn move that counterattacks or gains tempo, and test whether a check removes the retreat square' },
  { n: 13, text: 'Never push pawns in front of your castled king while an enemy bishop or queen eyes those squares; answer a wing storm with a central break' },
]
const MEMORY_SECONDS = 7   // long enough to read a rule before it fades into the next

/** Magnus's memory: the rules from his notebook, one after another, fading from one to the next. */
function MemoryLine() {
  const [index, setIndex] = useState(0)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    let swap: number | undefined
    const timer = window.setInterval(() => {
      setVisible(false)
      swap = window.setTimeout(() => {
        setIndex((i) => (i + 1) % MEMORIES.length)
        setVisible(true)
      }, 450)
    }, MEMORY_SECONDS * 1000)
    return () => {
      window.clearInterval(timer)
      window.clearTimeout(swap)
    }
  }, [])

  const memory = MEMORIES[index]
  const fade = { opacity: visible ? 1 : 0, transition: REDUCED_MOTION ? 'none' : 'opacity 0.45s ease' }
  return (
    <div className="mb-5 sm:mb-6">
      <div className="text-[12px] sm:text-[13px] text-black/55 mb-1 select-none" style={fade}>
        From my notebook, rule {memory.n} of 15
      </div>
      <p
        className="text-black"
        style={{ fontSize: 'clamp(15px, 2.4vw, 19px)', lineHeight: 1.35, height: '4.05em', overflow: 'hidden',
                 fontWeight: 400, ...fade }}
      >
        “{memory.text}.”
      </p>
    </div>
  )
}

/** The man turns his head towards the mouse: mouse to his left, he looks left; over him,
 *  he faces you; to his right, he looks right. The mouse sets a target moment in the
 *  clip; every animation frame the video glides part of the way there, so the turn is
 *  smooth. A new seek only starts once the previous one has finished, so seeks never pile up. */
function useHeadFollow(video: React.RefObject<HTMLVideoElement | null>) {
  useEffect(() => {
    const v = video.current
    if (!v) return
    const frame = 1 / 24
    let targetTime = 0
    let shownTime = 0
    let seeking = false
    let raf = 0

    // Where the man is on screen: the video is scaled to cover the window and
    // positioned at 70% horizontally (object-position: 70% center).
    const manScreenX = () => {
      const W = window.innerWidth, H = window.innerHeight
      const scale = Math.max(W / (v.videoWidth || 16), H / (v.videoHeight || 9))
      const shownWidth = (v.videoWidth || 16) * scale
      const x = MAN_X * shownWidth - (shownWidth - W) * 0.7
      return Math.min(W * 0.9, Math.max(W * 0.1, x))
    }

    const onSeeked = () => { seeking = false }
    const tick = () => {
      raf = requestAnimationFrame(tick)
      const gap = targetTime - shownTime
      if (Math.abs(gap) < frame / 4) return
      shownTime = Math.abs(gap) < frame / 2 ? targetTime : shownTime + gap * EASING
      // Only seek when the glide has reached a different frame of the video.
      if (!seeking && Math.abs(v.currentTime - shownTime) >= frame / 2) {
        seeking = true
        v.currentTime = shownTime
      }
    }
    const onMove = (e: MouseEvent) => {
      if (!v.duration || Number.isNaN(v.duration)) return
      const W = window.innerWidth, man = manScreenX()
      const share = e.clientX <= man
        ? FRONT * (e.clientX / man)
        : FRONT + (1 - FRONT) * ((e.clientX - man) / (W - man))
      targetTime = Math.min(v.duration, Math.max(0, share * v.duration))
    }
    const onLoaded = () => {
      // Start facing the viewer.
      targetTime = shownTime = FRONT * v.duration
      v.currentTime = shownTime
    }

    v.addEventListener('seeked', onSeeked)
    v.addEventListener('loadedmetadata', onLoaded)
    if (v.readyState >= 1) onLoaded()
    window.addEventListener('mousemove', onMove)
    raf = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(raf)
      v.removeEventListener('seeked', onSeeked)
      v.removeEventListener('loadedmetadata', onLoaded)
      window.removeEventListener('mousemove', onMove)
    }
  }, [video])
}

function CopyIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <rect x="3.5" y="3.5" width="7.5" height="7.5" rx="1.5" stroke="currentColor" />
      <path d="M8.5 2V1.5A1 1 0 0 0 7.5.5h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1H2" stroke="currentColor" />
    </svg>
  )
}

function Navbar() {
  return (
    <nav className="fixed top-0 inset-x-0 z-10 flex items-center justify-between px-5 sm:px-8 py-4 sm:py-5">
      <a href="./" className="flex items-center gap-3 text-black">
        <span className="text-[21px] sm:text-[26px] tracking-tight" style={{ fontFamily: 'var(--font-heading)' }}>
          Chess Agents
        </span>
        <span className="text-[25px] sm:text-[30px] select-none" style={{ letterSpacing: '-0.02em' }} aria-hidden="true">
          ♞
        </span>
      </a>
      <a href={CTA.href} className="text-[17px] sm:text-[23px] text-black underline underline-offset-2 hover:opacity-60 transition-opacity">
        {CTA.label}
      </a>
    </nav>
  )
}

export default function App() {
  const video = useRef<HTMLVideoElement>(null)
  useHeadFollow(video)
  const typing = useTypewriter(TYPED)
  const displayed = REDUCED_MOTION ? TYPED : typing.displayed
  const done = REDUCED_MOTION || typing.done
  const [pillsVisible, setPillsVisible] = useState(REDUCED_MOTION)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const t = window.setTimeout(() => setPillsVisible(true), 400)
    return () => window.clearTimeout(t)
  }, [])

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(SHARE_URL)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* the browser refused clipboard access */
    }
  }

  const pill =
    'inline-flex items-center justify-center rounded-full text-[13px] sm:text-[15px] px-4 sm:px-5 py-[0.3em] mx-[0.2em] mb-[0.4em] whitespace-nowrap transition-colors duration-200'
  const textStyle = { fontSize: 'clamp(18px, 4vw, 26px)', fontWeight: 400 }

  return (
    <>
      <video
        ref={video}
        src={VIDEO_URL}
        muted
        playsInline
        preload="auto"
        className="fixed inset-0 z-0 w-full h-full object-cover"
        style={{ objectPosition: '70% center' }}
      />

      <Navbar />

      <section className="relative z-[1] h-screen flex flex-col justify-end pb-12 md:justify-center md:pb-0 px-5 sm:px-8 md:px-10 overflow-hidden">
        <div className="max-w-xl relative z-10">
          <MemoryLine />

          {/* The full sentence, invisible, holds the space so the buttons don't move while it types. */}
          <div className="relative mb-5 sm:mb-6" style={{ ...textStyle, lineHeight: 1.35, minHeight: 54 }}>
            <p className="invisible" aria-hidden="true">{TYPED}</p>
            <p className="absolute inset-0 text-black" aria-label={TYPED}>
              {displayed}
              {!done && (
                <span
                  className="inline-block w-[2px] h-[1.1em] bg-black align-middle ml-[2px]"
                  style={{ animation: 'blink 1s step-end infinite' }}
                />
              )}
            </p>
          </div>

          <div
            className="flex flex-wrap gap-y-1"
            style={{
              opacity: pillsVisible ? 1 : 0,
              transform: pillsVisible ? 'translateY(0)' : 'translateY(8px)',
              transition: REDUCED_MOTION ? 'none' : 'opacity 0.4s ease, transform 0.4s ease',
            }}
          >
            {PILLS.map((p) => (
              <a key={p.label} href={p.href} className={`${pill} bg-white text-black border border-black/10 hover:bg-black hover:text-white`}>
                {p.label}
              </a>
            ))}
            <button
              type="button"
              onClick={copyLink}
              className={`${pill} gap-2 sm:gap-3 text-black bg-transparent border border-black hover:bg-black hover:text-white`}
            >
              {copied ? (
                <span>Link copied</span>
              ) : (
                <span>
                  Share: <span className="underline underline-offset-1">{SHARE_LABEL}</span>
                </span>
              )}
              <CopyIcon />
            </button>
          </div>
        </div>
      </section>
    </>
  )
}
