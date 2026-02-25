import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'
import { useLang } from '../i18n/LangContext'
import useMotionValue from '../hooks/useMotionValue'

function BessContainer({ rusty }) {
    return (
        <svg viewBox="-160 -90 320 200" className="w-full h-full">
            <ellipse cx={0} cy={108} rx={130} ry={10} fill="rgba(0,0,0,0.4)" />

            {/* Container body */}
            <rect x={-140} y={-70} width={280} height={160} rx={6}
                fill="rgba(12,18,32,0.97)"
                stroke={`rgba(${71 + Math.round(rusty * 55)},${85 - Math.round(rusty * 28)},${105 - Math.round(rusty * 45)},0.65)`}
                strokeWidth={1.5} />

            {/* Corrugated ridges */}
            {Array.from({ length: 14 }).map((_, i) => (
                <line key={i} x1={-140 + i * 22} y1={-70} x2={-140 + i * 22} y2={90}
                    stroke="rgba(25,35,50,0.7)" strokeWidth={1} />
            ))}

            {/* Doors */}
            <rect x={-120} y={-50} width={100} height={120} rx={3}
                fill="rgba(10,18,32,0.6)" stroke="rgba(55,65,85,0.4)" strokeWidth={0.8} />
            <rect x={20} y={-50} width={100} height={120} rx={3}
                fill="rgba(10,18,32,0.6)" stroke="rgba(55,65,85,0.4)" strokeWidth={0.8} />
            <rect x={-8} y={-8} width={16} height={18} rx={2}
                fill="none" stroke="rgba(55,65,85,0.4)" strokeWidth={1.2} />

            {/* Rust spots */}
            {rusty > 0.15 && [[-80, 20], [65, -28], [-25, 52], [88, 35], [-55, -40]].map(([cx, cy], i) => (
                <ellipse key={i} cx={cx} cy={cy} rx={5 + i * 2} ry={3 + i}
                    fill={`rgba(160,55,18,${Math.min(0.55, (rusty - 0.15) * 0.6)})`} />
            ))}

            {/* Warning light */}
            <circle cx={105} cy={-55} r={7}
                fill={rusty > 0.08 ? 'rgba(251,191,36,0.92)' : 'rgba(55,65,85,0.3)'}
                style={{ filter: rusty > 0.08 ? 'drop-shadow(0 0 7px rgba(251,191,36,0.75))' : 'none' }}>
                {rusty > 0.08 && <animate attributeName="opacity" values="1;0.15;1" dur="1.1s" repeatCount="indefinite" />}
            </circle>

            {/* Status bar */}
            <rect x={-52} y={-66} width={104} height={20} rx={2}
                fill="rgba(0,0,0,0.75)" stroke="rgba(55,65,85,0.3)" strokeWidth={0.7} />
            <text x={0} y={-52} textAnchor="middle" fontSize={6.5}
                fill={rusty > 0.2 ? '#f87171' : '#4b5563'}
                fontFamily="'JetBrains Mono', monospace">
                {rusty > 0.2 ? '⚠ STATUS: BLIND / OFFLINE' : '-- NO SIGNAL --'}
            </text>
        </svg>
    )
}

export default function Scene3BlackBox() {
    const { t } = useLang()
    const ref = useRef(null)
    const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })

    const opacity = useTransform(scrollYProgress, [0.05, 0.18, 0.78, 0.9], [0, 1, 1, 0])
    const textY = useTransform(scrollYProgress, [0.08, 0.4], [45, 0])
    const containerY = useTransform(scrollYProgress, [0.08, 0.4], [65, 0])
    const rustyMV = useTransform(scrollYProgress, [0.28, 0.72], [0, 1])
    const badgeOpacity = useTransform(scrollYProgress, [0.42, 0.58, 0.8, 0.9], [0, 1, 1, 0])

    const [rusty] = useMotionValue(rustyMV)

    return (
        <section ref={ref} id="scene-3"
            className="relative min-h-screen flex items-center justify-center overflow-hidden py-16">
            <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-slate-900/30 to-slate-950" />
            <div className="absolute bottom-0 left-0 right-0 h-28 bg-gradient-to-t from-amber-950/15 to-transparent" />

            <motion.div className="relative z-10 w-full max-w-5xl mx-auto px-8" style={{ opacity }}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">

                    {/* Container visual */}
                    <motion.div className="w-full h-60" style={{ y: containerY }}>
                        <BessContainer rusty={rusty} />
                    </motion.div>

                    {/* Text */}
                    <motion.div style={{ y: textY }}>
                        <p className="text-xs font-mono tracking-widest text-slate-500 mb-4 uppercase">{t.s3.eyebrow}</p>
                        <h2 className="font-black leading-tight tracking-tight mb-5"
                            style={{ fontSize: 'clamp(1.9rem,4.5vw,3.5rem)' }}>
                            {t.s3.h2}<br />
                            <span className="text-slate-500">{t.s3.h2b}</span>
                        </h2>
                        <p className="text-slate-400 leading-relaxed mb-7 text-base">{t.s3.body}</p>

                        <motion.div className="space-y-2.5" style={{ opacity: badgeOpacity }}>
                            {t.s3.pains.map((item, i) => (
                                <motion.div key={i}
                                    className="font-mono text-sm text-rose-300/75 border border-rose-900/25 rounded-lg px-4 py-2.5 bg-rose-950/10"
                                    initial={{ x: 20, opacity: 0 }} whileInView={{ x: 0, opacity: 1 }}
                                    viewport={{ once: true }} transition={{ delay: i * 0.1 }}>
                                    {item}
                                </motion.div>
                            ))}
                        </motion.div>
                    </motion.div>
                </div>

                <motion.div className="mt-10 flex items-center gap-3 justify-center font-mono text-xs text-amber-400/55 tracking-widest"
                    style={{ opacity: badgeOpacity }}>
                    <AlertTriangle size={12} />
                    <span>{t.s3.badge}</span>
                    <AlertTriangle size={12} />
                </motion.div>
            </motion.div>
        </section>
    )
}
