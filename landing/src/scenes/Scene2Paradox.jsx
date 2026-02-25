import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { useLang } from '../i18n/LangContext'
import useMotionValue from '../hooks/useMotionValue'

function SolarField({ dissipate }) {
    const panels = Array.from({ length: 24 }, (_, i) => ({
        x: (i % 6) * 80 - 200,
        y: Math.floor(i / 6) * 55 - 90,
    }))

    return (
        <svg viewBox="-260 -120 520 260" className="w-full h-full" style={{ overflow: 'visible' }}>
            {[0, 25, 55, 80, 115].map((y, i) => (
                <path key={i}
                    d={`M-260,${y} Q-130,${y - 14} 0,${y - 3} Q130,${y + 10} 260,${y - 7}`}
                    fill="none" stroke={`rgba(251,191,36,${0.1 - i * 0.015})`} strokeWidth="0.8" />
            ))}

            {panels.map((p, i) => (
                <g key={i} transform={`translate(${p.x},${p.y})`} opacity={Math.max(0.35, 1 - dissipate * 0.55)}>
                    <rect x={-26} y={-16} width={52} height={32} rx={2}
                        fill="rgba(15,23,42,0.92)"
                        stroke={`rgba(16,185,129,${Math.max(0.1, 0.55 - dissipate * 0.45)})`}
                        strokeWidth={0.8} />
                    {[-13, 0, 13].map(gx => (
                        <line key={gx} x1={gx} y1={-16} x2={gx} y2={16}
                            stroke={`rgba(16,185,129,${0.15 - dissipate * 0.1})`} strokeWidth={0.4} />
                    ))}
                    {[-8, 0, 8].map(gy => (
                        <line key={gy} x1={-26} y1={gy} x2={26} y2={gy}
                            stroke={`rgba(16,185,129,${0.15 - dissipate * 0.1})`} strokeWidth={0.4} />
                    ))}
                </g>
            ))}

            {/* Dissipation plumes */}
            {dissipate > 0.08 && panels.slice(0, 12).map((p, i) => (
                <g key={i}>
                    {[0, 1, 2].map(j => (
                        <circle key={j}
                            cx={p.x + Math.sin(i + j) * 10} cy={p.y - 22 - j * 18}
                            r={3 + j * 3}
                            fill={`rgba(251,191,36,${(dissipate - 0.08) * 0.35})`}
                            style={{ animation: `drift-up ${1.6 + j * 0.4}s ease-out ${i * 0.12}s infinite` }} />
                    ))}
                </g>
            ))}

            {/* Lost rays */}
            {dissipate > 0.25 && panels.slice(0, 8).map((p, i) => (
                <line key={i} x1={p.x} y1={p.y - 18}
                    x2={p.x + Math.sin(i + 1) * 25} y2={p.y - 85}
                    stroke={`rgba(251,191,36,${(dissipate - 0.25) * 0.55})`}
                    strokeWidth={1} strokeDasharray="3 6"
                    style={{ animation: `drift-up 2s ease-out ${i * 0.25}s infinite` }} />
            ))}
        </svg>
    )
}

export default function Scene2Paradox() {
    const { t } = useLang()
    const ref = useRef(null)
    const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })

    const opacity = useTransform(scrollYProgress, [0.05, 0.18, 0.76, 0.9], [0, 1, 1, 0])
    const dissipate = useTransform(scrollYProgress, [0.2, 0.72], [0, 1])
    const textY = useTransform(scrollYProgress, [0.08, 0.42], [50, 0])
    const statOpacity = useTransform(scrollYProgress, [0.4, 0.58, 0.78, 0.9], [0, 1, 1, 0])
    const barWidth = useTransform(scrollYProgress, [0.5, 0.72], ['0%', '100%'])
    const [d] = useMotionValue(dissipate)

    return (
        <section ref={ref} id="scene-2"
            className="relative min-h-[80vh] flex items-center justify-center overflow-hidden py-16">
            <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-amber-950/8 to-slate-950" />

            <motion.div className="relative z-10 w-full max-w-5xl mx-auto px-8" style={{ opacity }}>
                <div className="w-full h-52 mb-10">
                    <SolarField dissipate={d} />
                </div>

                <motion.div className="text-center" style={{ y: textY }}>
                    <p className="text-xs font-mono tracking-widest text-amber-400 mb-4 uppercase">{t.s2.eyebrow}</p>
                    <h2 className="font-black leading-tight tracking-tight mb-4"
                        style={{ fontSize: 'clamp(2rem,5vw,4rem)' }}>
                        {t.s2.h2}<br />
                        <span className="text-amber-400">{t.s2.h2b}</span>
                    </h2>
                    <p className="text-slate-400 text-lg max-w-xl mx-auto leading-relaxed">
                        {t.s2.body}
                    </p>
                </motion.div>

                <motion.div className="mt-12 flex justify-center" style={{ opacity: statOpacity }}>
                    <div className="border border-rose-500/25 rounded-xl px-10 py-8 bg-rose-950/15 text-center backdrop-blur-sm max-w-md w-full">
                        <div className="font-mono font-bold text-rose-400 mb-1"
                            style={{ fontSize: 'clamp(2.5rem,6vw,3.5rem)', fontFamily: "'JetBrains Mono',monospace" }}>
                            {t.s2.stat}
                        </div>
                        <div className="text-rose-300/55 font-mono text-xs mt-1 tracking-widest mb-4">
                            {t.s2.stat_label}
                        </div>
                        <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden mb-4">
                            <motion.div className="h-full bg-gradient-to-r from-amber-500 to-rose-500 rounded-full"
                                style={{ width: barWidth }} />
                        </div>
                        <p className="text-slate-400 text-sm leading-relaxed">{t.s2.stat_sub}</p>
                    </div>
                </motion.div>
            </motion.div>
        </section>
    )
}
