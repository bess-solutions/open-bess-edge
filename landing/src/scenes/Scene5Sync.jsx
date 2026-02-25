import { useRef, useEffect, useState } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { useLang } from '../i18n/LangContext'
import useMotionValue from '../hooks/useMotionValue'

function GridNetwork({ active }) {
    const nodes = [
        { x: 50, y: 50 }, { x: 25, y: 25 }, { x: 75, y: 25 },
        { x: 14, y: 60 }, { x: 86, y: 60 }, { x: 34, y: 82 },
        { x: 66, y: 82 }, { x: 50, y: 9 }, { x: 9, y: 36 }, { x: 91, y: 36 },
    ]
    const connections = [
        [0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [0, 6],
        [1, 7], [2, 7], [1, 8], [2, 9], [3, 5], [4, 6], [7, 8], [7, 9],
    ]

    return (
        <svg viewBox="0 0 100 100" className="w-full h-full">
            {connections.map(([a, b], i) => (
                <motion.line key={i}
                    x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y}
                    stroke="#3b82f6" strokeWidth={0.35}
                    initial={{ pathLength: 0, opacity: 0 }}
                    animate={active ? { pathLength: 1, opacity: 0.45 } : { pathLength: 0, opacity: 0 }}
                    transition={{ delay: i * 0.1, duration: 0.55 }} />
            ))}

            {/* Data packets */}
            {active && connections.map(([a, b], i) => (
                <motion.circle key={i} r={0.9} fill="#22d3ee"
                    style={{ filter: 'drop-shadow(0 0 1.5px #22d3ee)' }}
                    animate={{ opacity: [0, 0.9, 0] }}
                    transition={{ delay: i * 0.18 + 1.2, duration: 1.8, repeat: Infinity, repeatDelay: 0.4 }}>
                    <animateMotion
                        path={`M${nodes[a].x},${nodes[a].y} L${nodes[b].x},${nodes[b].y}`}
                        dur="2.2s" repeatCount="indefinite" begin={`${i * 0.2}s`} />
                </motion.circle>
            ))}

            {/* Nodes */}
            {nodes.map((n, i) => (
                <g key={i}>
                    <motion.circle cx={n.x} cy={n.y} r={2.2}
                        fill="#0f172a" stroke="#10b981" strokeWidth={0.55}
                        initial={{ scale: 0, opacity: 0 }}
                        animate={active ? { scale: 1, opacity: 1 } : { scale: 0, opacity: 0 }}
                        transition={{ delay: i * 0.09, duration: 0.35, type: 'spring', stiffness: 200 }} />
                    {active && (
                        <motion.circle cx={n.x} cy={n.y} r={2.2}
                            fill="none" stroke="#10b981" strokeWidth={0.35}
                            animate={{ scale: [1, 3.5], opacity: [0.5, 0] }}
                            transition={{ delay: i * 0.14 + 1.4, duration: 2.2, repeat: Infinity, repeatDelay: 0.6 }} />
                    )}
                </g>
            ))}
        </svg>
    )
}

export default function Scene5Sync() {
    const { t } = useLang()
    const ref = useRef(null)
    const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })

    const opacity = useTransform(scrollYProgress, [0.05, 0.18, 0.8, 0.95], [0, 1, 1, 0])
    const textY = useTransform(scrollYProgress, [0.08, 0.38], [40, 0])
    const activeMV = useTransform(scrollYProgress, [0.28, 0.52], [0, 1])
    const stableOp = useTransform(scrollYProgress, [0.52, 0.68], [0, 1])

    const [isActive] = useMotionValue(activeMV)

    return (
        <section ref={ref} id="scene-5"
            className="relative min-h-screen flex items-center justify-center overflow-hidden py-16">
            <motion.div className="absolute inset-0"
                style={{ background: 'radial-gradient(ellipse at 50% 100%, #020c1a 0%, #020617 60%)' }} />

            <motion.div className="relative z-10 w-full max-w-5xl mx-auto px-8" style={{ opacity }}>
                <motion.div className="text-center mb-12" style={{ y: textY }}>
                    <p className="text-xs font-mono tracking-widest text-blue-400 mb-4 uppercase">{t.s5.eyebrow}</p>
                    <h2 className="font-black leading-tight tracking-tight mb-4"
                        style={{ fontSize: 'clamp(2rem,5vw,4.2rem)' }}>
                        {t.s5.h2}<br />
                        <span className="text-emerald-400">{t.s5.h2b}</span>
                    </h2>
                    <p className="text-slate-400 text-lg max-w-xl mx-auto leading-relaxed">{t.s5.body}</p>
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
                    <div className="h-72">
                        <GridNetwork active={isActive > 0.5} />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        {t.s5.metrics.map((m, i) => (
                            <motion.div key={i}
                                className="border border-slate-800/80 rounded-xl p-4 bg-slate-900/35 backdrop-blur-sm hover:border-slate-700 transition-colors"
                                initial={{ y: 24, opacity: 0 }} whileInView={{ y: 0, opacity: 1 }}
                                viewport={{ once: true }} transition={{ delay: i * 0.1, duration: 0.45 }}>
                                <div className="text-xl mb-2">{m.icon}</div>
                                <div className="text-slate-500 text-xs font-mono mb-1.5 leading-snug">{m.label}</div>
                                <div className={`font-mono text-xs font-semibold ${i % 2 === 0 ? 'text-emerald-400' : 'text-blue-400'} leading-snug`}>
                                    {m.value}
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>

                <motion.div className="mt-12 text-center" style={{ opacity: stableOp }}>
                    <div className="inline-flex items-center gap-3 font-mono text-xs text-emerald-400/65 tracking-widest border border-emerald-500/18 rounded-full px-6 py-2.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400"
                            style={{ animation: 'blink 2.2s ease-in-out infinite' }} />
                        {t.s5.stable}
                    </div>
                </motion.div>
            </motion.div>
        </section>
    )
}
