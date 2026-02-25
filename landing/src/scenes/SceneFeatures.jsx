import { useRef, useState } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { useLang } from '../i18n/LangContext'

function FeatureCard({ feature, index }) {
    return (
        <motion.div
            className="group relative border border-slate-800 hover:border-emerald-500/40 rounded-2xl p-6
        bg-slate-900/30 hover:bg-slate-900/60 backdrop-blur-sm transition-all duration-300 cursor-default"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: index * 0.08, duration: 0.5 }}
        >
            {/* Glow on hover */}
            <div className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500
        bg-gradient-to-br from-emerald-500/5 to-transparent pointer-events-none" />

            <div className="text-3xl mb-4">{feature.icon}</div>
            <h3 className="font-bold text-white mb-2 text-base leading-snug">{feature.title}</h3>
            <p className="text-slate-400 text-sm leading-relaxed mb-4">{feature.desc}</p>
            <div className="inline-block font-mono text-xs text-emerald-400/70 border border-emerald-500/20
        rounded-full px-3 py-1 bg-emerald-950/30">
                {feature.tag}
            </div>
        </motion.div>
    )
}

export default function SceneFeatures() {
    const { t } = useLang()
    const sf = t.sf

    return (
        <section id="scene-features" className="relative py-32 overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-slate-900/20 to-slate-950" />
            <div className="absolute inset-0 opacity-30"
                style={{
                    backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.03) 1px, transparent 0)',
                    backgroundSize: '28px 28px'
                }} />

            <div className="relative z-10 max-w-6xl mx-auto px-8">
                {/* Header */}
                <motion.div className="text-center mb-16"
                    initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }} transition={{ duration: 0.7 }}>
                    <p className="text-xs font-mono tracking-widest text-emerald-500 mb-4 uppercase">{sf.eyebrow}</p>
                    <h2 className="font-black leading-tight tracking-tight mb-4"
                        style={{ fontSize: 'clamp(2rem, 5vw, 4rem)' }}>
                        {sf.h2}<br />
                        <span className="text-emerald-400">{sf.h2b}</span>
                    </h2>
                    <p className="text-slate-400 text-lg max-w-xl mx-auto leading-relaxed">{sf.body}</p>
                </motion.div>

                {/* Features grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-20">
                    {sf.features.map((f, i) => (
                        <FeatureCard key={i} feature={f} index={i} />
                    ))}
                </div>

                {/* Hardware specs */}
                <motion.div
                    className="border border-slate-800 rounded-2xl overflow-hidden"
                    initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }} transition={{ duration: 0.6, delay: 0.2 }}>
                    {/* Header */}
                    <div className="flex items-center gap-3 px-6 py-4 bg-slate-900/80 border-b border-slate-800">
                        <div className="w-2 h-2 rounded-full bg-emerald-400" style={{ animation: 'blink 2s ease-in-out infinite' }} />
                        <span className="font-mono text-xs text-slate-400 tracking-widest uppercase">{sf.specs_title}</span>
                        <span className="font-mono text-xs text-slate-700 ml-auto">GW-001 · REV-3.1</span>
                    </div>
                    {/* Specs table */}
                    <div className="divide-y divide-slate-800/60">
                        {sf.specs.map((s, i) => (
                            <div key={i} className="flex items-center px-6 py-4 hover:bg-slate-900/30 transition-colors">
                                <span className="font-mono text-xs text-slate-500 tracking-widest uppercase w-36 flex-shrink-0">
                                    {s.label}
                                </span>
                                <span className="font-mono text-sm text-emerald-400/90">{s.value}</span>
                            </div>
                        ))}
                    </div>
                </motion.div>
            </div>
        </section>
    )
}
