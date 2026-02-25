import { useRef, useEffect, useState } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { useLang } from '../i18n/LangContext'
import useMotionValue from '../hooks/useMotionValue'

/* ─── Earth wireframe SVG ─── */
function EarthWireframe({ progress }) {
    const rings = 8
    const meridians = 12
    const hue = Math.round(160 - progress * 160) // emerald→rose

    return (
        <svg viewBox="-110 -110 220 220" className="w-full h-full"
            style={{ filter: `drop-shadow(0 0 ${20 + progress * 20}px hsl(${hue},70%,50%,0.35))` }}>
            <defs>
                <radialGradient id="atm">
                    <stop offset="70%" stopColor="transparent" />
                    <stop offset="100%" stopColor={`rgba(${Math.round(244 * progress)},${Math.round(63 * (1 - progress) * 0.5)},${Math.round(94 * progress)},0.2)`} />
                </radialGradient>
            </defs>
            <circle r="108" fill="url(#atm)" />

            {Array.from({ length: rings }).map((_, i) => {
                const lat = ((i + 1) / (rings + 1)) * 180 - 90
                const y = -Math.sin((lat * Math.PI) / 180) * 100
                const rx = Math.cos((lat * Math.PI) / 180) * 100
                if (rx < 1) return null
                return (
                    <ellipse key={i} cx={0} cy={y} rx={rx} ry={rx * 0.2}
                        fill="none" stroke={`hsl(${hue},78%,55%)`} strokeWidth="0.6" strokeOpacity="0.5" />
                )
            })}

            {Array.from({ length: meridians }).map((_, i) => {
                const angle = (i / meridians) * Math.PI
                return (
                    <ellipse key={i} cx={0} cy={0}
                        rx={Math.abs(Math.sin(angle)) * 100 + 1} ry={100}
                        fill="none" stroke={`hsl(${hue},72%,55%)`} strokeWidth="0.6" strokeOpacity="0.42"
                        transform={`rotate(${(i / meridians) * 180})`} />
                )
            })}

            <circle r="100" fill="none" stroke={`hsl(${hue},78%,55%)`} strokeWidth="1" strokeOpacity="0.65" />

            {/* Heat spots */}
            {progress > 0.35 && [
                [28, -15], [-40, 20], [55, 30], [-20, -40], [10, 50], [70, -45]
            ].map(([cx, cy], i) => (
                <circle key={i} cx={cx} cy={cy}
                    r={3 + (progress - 0.35) * 14}
                    fill={`rgba(244,63,94,${Math.min(1, (progress - 0.35) * 1.6)})`}
                    style={{ filter: 'blur(1.5px)' }}
                />
            ))}

            {/* Axis poles */}
            <line x1={0} y1={-108} x2={0} y2={108} stroke={`hsl(${hue},60%,40%)`} strokeWidth="0.4" strokeOpacity="0.3" />
        </svg>
    )
}

/* ─── CO2 Counter ─── */
function Co2Counter({ progress, t }) {
    const value = Math.round(280 + progress * 147) // 280→427 ppm
    const hue = Math.round(160 - progress * 160)
    return (
        <div className="text-center font-mono">
            <div className="text-xs tracking-widest text-slate-500 mb-3 uppercase">{t.s1.counter_label}</div>
            <div className="tabular-nums leading-none"
                style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 'clamp(4rem,10vw,7rem)',
                    fontWeight: 800,
                    color: `hsl(${hue},78%,60%)`,
                    textShadow: `0 0 40px hsl(${hue},78%,50%,0.4)`,
                }}>
                {value}
                <span className="text-3xl font-normal opacity-60 ml-2">ppm</span>
            </div>
            <div className="text-slate-400 text-sm mt-3 font-mono">
                <span style={{ color: `rgba(244,63,94,${0.4 + progress * 0.6})` }}>
                    {t.s1.counter_sub}
                </span>
            </div>
        </div>
    )
}

export default function Scene1Earth() {
    const { t } = useLang()
    const sectionRef = useRef(null)

    const { scrollYProgress } = useScroll({
        target: sectionRef,
        offset: ['start start', 'end end'],
    })

    // Fix: text1 is visible from the very start, fades out mid-scroll
    // Fix: text2 appears in the second half
    const text1Opacity = useTransform(scrollYProgress, [0, 0.0, 0.5, 0.62], [1, 1, 1, 0])
    const text2Opacity = useTransform(scrollYProgress, [0.55, 0.68, 0.92, 1], [0, 1, 1, 0])
    const progress = useTransform(scrollYProgress, [0, 0.9], [0, 1])
    const globeScale = useTransform(scrollYProgress, [0, 0.6, 1], [0.9, 1.0, 1.15])
    const scrollHintOp = useTransform(scrollYProgress, [0, 0.08], [1, 0])

    const [prog] = useMotionValue(progress)

    return (
        <section ref={sectionRef} id="scene-1" className="relative" style={{ height: '220vh' }}>
            <div className="sticky top-0 h-screen overflow-hidden">

                {/* Background */}
                <div className="absolute inset-0"
                    style={{ background: `radial-gradient(ellipse at center, rgba(${Math.round(40 * prog)},${Math.round(5 * prog)},${Math.round(8 * prog)},1) 0%, #020617 65%)` }} />

                {/* Globe — always perfectly centered */}
                <motion.div className="absolute top-1/2 left-1/2"
                    style={{ width: '520px', height: '520px', x: '-50%', y: '-50%', scale: globeScale }}>
                    <EarthWireframe progress={prog} />
                </motion.div>

                {/* ── Text 1: top-half zone, absolutely positioned, visible from load ── */}
                <motion.div
                    className="absolute inset-x-0 top-0 z-10 flex flex-col items-center justify-center px-8 text-center"
                    style={{ height: '54vh', opacity: text1Opacity }}
                >
                    <motion.p
                        className="text-xs font-mono tracking-widest text-emerald-500 mb-4 uppercase"
                        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.7, delay: 0.3 }}
                    >
                        {t.s1.eyebrow}
                    </motion.p>
                    <motion.h1
                        className="font-black tracking-tight leading-tight mb-4 max-w-2xl"
                        style={{ fontSize: 'clamp(1.9rem, 4.5vw, 3.8rem)' }}
                        initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.8, delay: 0.5 }}
                    >
                        {t.s1.h1_a}<br />
                        <span className="text-emerald-400">{t.s1.h1_b}</span>
                    </motion.h1>
                    <motion.p
                        className="text-slate-400 text-base max-w-lg mx-auto leading-relaxed"
                        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.7, delay: 0.9 }}
                    >
                        {t.s1.body}
                    </motion.p>
                </motion.div>

                {/* ── Text 2: bottom-half zone, CO2 counter ── */}
                <motion.div
                    className="absolute inset-x-0 bottom-0 z-10 flex flex-col items-center justify-center px-8 text-center"
                    style={{ height: '46vh', opacity: text2Opacity }}
                >
                    <Co2Counter progress={prog} t={t} />
                    <p className="text-slate-600 text-xs font-mono mt-4 tracking-wider">
                        {t.s1.source}
                    </p>
                </motion.div>

                {/* Scroll hint */}
                <motion.div
                    className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 font-mono text-xs text-slate-600 tracking-widest flex flex-col items-center gap-2"
                    style={{ opacity: scrollHintOp }}
                    animate={{ y: [0, 5, 0] }}
                    transition={{ repeat: Infinity, duration: 2.2 }}
                >
                    <span>SCROLL</span>
                    <svg width="14" height="22" viewBox="0 0 14 22" fill="none">
                        <rect x="4" y="0" width="6" height="13" rx="3" stroke="#334155" strokeWidth="1.2" />
                        <circle cx="7" cy="4" r="1.8" fill="#334155">
                            <animate attributeName="cy" values="4;9;4" dur="2s" repeatCount="indefinite" />
                        </circle>
                    </svg>
                </motion.div>
            </div>
        </section>
    )
}
