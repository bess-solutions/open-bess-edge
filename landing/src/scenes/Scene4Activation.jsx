import { useRef, useState, useEffect } from 'react'
import { motion, useScroll, useTransform, AnimatePresence } from 'framer-motion'
import { useLang } from '../i18n/LangContext'

function TerminalWindow({ visible, lines }) {
    const [displayed, setDisplayed] = useState([])

    useEffect(() => {
        setDisplayed([])
        if (!visible) return
        const delays = [0, 500, 950, 1400, 1900, 2350, 2750, 3200, 3600, 3700, 4000, 4450]
        const timers = lines.map((text, i) =>
            setTimeout(() => setDisplayed(prev => [...prev, { text, highlight: i === lines.length - 1 }]), delays[i] || i * 380)
        )
        return () => timers.forEach(clearTimeout)
    }, [visible, lines])

    return (
        <div className="bg-slate-950 border border-emerald-500/25 rounded-2xl overflow-hidden shadow-2xl shadow-emerald-500/8"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800/80 bg-slate-900/80">
                <div className="w-2.5 h-2.5 rounded-full bg-rose-500/70" />
                <div className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/70" />
                <span className="text-slate-600 text-xs ml-3">bessai-edge ~ connect --host=BESS-001</span>
            </div>
            <div className="p-5 min-h-56 text-sm space-y-0.5">
                {displayed.map((line, i) => (
                    <motion.div key={i}
                        initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.2 }}
                        className={
                            line.highlight ? 'text-emerald-400 font-bold mt-2' :
                                line.text === '' ? 'py-0.5' :
                                    'text-slate-400'
                        }
                    >
                        {line.text}
                        {i === displayed.length - 1 && (
                            <span className="cursor-blink text-emerald-400 ml-0.5">▌</span>
                        )}
                    </motion.div>
                ))}
            </div>
        </div>
    )
}

function DataBurst({ active }) {
    if (!active) return null
    const rays = Array.from({ length: 20 }, (_, i) => {
        const a = (i / 20) * Math.PI * 2
        const len = 35 + Math.random() * 75
        return { x: Math.cos(a) * len, y: Math.sin(a) * len, delay: i * 0.06 }
    })

    return (
        <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="-200 -200 400 400">
            {rays.map((r, i) => (
                <motion.line key={i} x1={0} y1={0} x2={r.x} y2={r.y}
                    stroke={i % 3 === 0 ? '#10b981' : '#3b82f6'}
                    strokeWidth={0.7} strokeOpacity={0.65}
                    initial={{ pathLength: 0, opacity: 0 }}
                    animate={{ pathLength: 1, opacity: [0, 0.75, 0] }}
                    transition={{ delay: r.delay, duration: 1.1, repeat: Infinity, repeatDelay: 1.8 }} />
            ))}
        </svg>
    )
}

export default function Scene4Activation() {
    const { t } = useLang()
    const ref = useRef(null)
    const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })

    const opacity = useTransform(scrollYProgress, [0.05, 0.18, 0.82, 0.95], [0, 1, 1, 0])
    const textY = useTransform(scrollYProgress, [0.08, 0.38], [50, 0])
    const termOp = useTransform(scrollYProgress, [0.32, 0.5], [0, 1])
    const burstOp = useTransform(scrollYProgress, [0.38, 0.55], [0, 1])
    const glowScale = useTransform(scrollYProgress, [0.28, 0.65], [0, 4.5])
    const glowOpacity = useTransform(scrollYProgress, [0.28, 0.58, 0.85], [0, 1, 0])

    const [termVisible, setTermVisible] = useState(false)
    const [burstActive, setBurstActive] = useState(false)

    useEffect(() => {
        const u1 = termOp.on('change', v => setTermVisible(v > 0.5))
        const u2 = burstOp.on('change', v => setBurstActive(v > 0.5))
        return () => { u1(); u2() }
    }, [termOp, burstOp])

    return (
        <section ref={ref} id="scene-4"
            className="relative min-h-screen flex items-center justify-center overflow-hidden py-24">
            <motion.div className="absolute inset-0"
                style={{ background: 'radial-gradient(ellipse at center, #020f08 0%, #020617 65%)' }} />

            {/* Central glow */}
            <motion.div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{
                    width: '150px', height: '150px',
                    background: 'radial-gradient(circle, rgba(16,185,129,0.14) 0%, transparent 70%)',
                    scale: glowScale, opacity: glowOpacity,
                }} />

            <motion.div className="relative z-10 w-full max-w-5xl mx-auto px-8" style={{ opacity }}>
                {/* Header */}
                <motion.div className="text-center mb-12" style={{ y: textY }}>
                    <p className="text-xs font-mono tracking-widest text-emerald-500 mb-4 uppercase">{t.s4.eyebrow}</p>
                    <h2 className="font-black leading-tight tracking-tight mb-4"
                        style={{ fontSize: 'clamp(2rem,5.5vw,4.5rem)' }}>
                        <span className="text-emerald-400" style={{ textShadow: '0 0 30px rgba(16,185,129,0.45)' }}>
                            {t.s4.h2}
                        </span><br />
                        {t.s4.h2b}
                    </h2>
                    <p className="text-slate-400 text-lg max-w-xl mx-auto leading-relaxed">{t.s4.body}</p>
                </motion.div>

                {/* Gateway + terminal */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
                    {/* Gateway visual */}
                    <motion.div className="relative flex items-center justify-center h-72" style={{ opacity: burstOp }}>
                        {[110, 170, 230].map((size, i) => (
                            <motion.div key={i}
                                className="absolute rounded-full border border-emerald-500/15"
                                style={{ width: `${size}px`, height: `${size}px` }}
                                animate={{ scale: [1, 1.04, 1], opacity: [0.5, 0.12, 0.5] }}
                                transition={{ duration: 2.2 + i * 0.5, repeat: Infinity, delay: i * 0.3 }} />
                        ))}
                        <div className="relative w-48 h-48">
                            <DataBurst active={burstActive} />
                            <div className="absolute inset-0 flex items-center justify-center">
                                <motion.div
                                    className="w-22 h-16 bg-slate-900 border border-emerald-500/55 rounded-xl flex items-center justify-center px-4 py-3"
                                    style={{
                                        width: '88px', height: '64px',
                                        boxShadow: burstActive ? '0 0 24px rgba(16,185,129,0.35)' : 'none'
                                    }}>
                                    <div className="text-center">
                                        <div className="text-emerald-400 font-mono text-xs font-bold leading-tight">BESSAI</div>
                                        <div className="text-emerald-500/55 font-mono text-[8px] leading-tight">EDGE · GW</div>
                                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mx-auto mt-1.5"
                                            style={{ animation: burstActive ? 'blink 0.75s step-end infinite' : 'none' }} />
                                    </div>
                                </motion.div>
                            </div>
                        </div>
                    </motion.div>

                    {/* Terminal */}
                    <motion.div style={{ opacity: termOp }}>
                        <TerminalWindow visible={termVisible} lines={t.s4.terminal_lines} />
                    </motion.div>
                </div>
            </motion.div>
        </section>
    )
}
