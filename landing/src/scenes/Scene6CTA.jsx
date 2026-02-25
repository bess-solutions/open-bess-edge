import { motion } from 'framer-motion'
import { ArrowRight, Zap, Github, Linkedin, Twitter, Mail } from 'lucide-react'
import { useLang } from '../i18n/LangContext'

const SOCIAL_ICONS = {
    github: Github,
    linkedin: Linkedin,
    twitter: Twitter,
    mail: Mail,
}

export default function Scene6CTA() {
    const { t } = useLang()
    const s = t.s6

    return (
        <section id="scene-6" className="relative overflow-hidden">
            {/* CTA block */}
            <div className="relative py-20 px-8">
                <div className="absolute inset-0 bg-gradient-to-b from-slate-950 to-black" />
                <div className="absolute inset-0 opacity-20"
                    style={{
                        backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.05) 1px, transparent 0)',
                        backgroundSize: '30px 30px'
                    }} />

                {/* Top accent */}
                <motion.div
                    className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-24 bg-gradient-to-b from-emerald-500/40 to-transparent"
                    initial={{ scaleY: 0 }} whileInView={{ scaleY: 1 }}
                    viewport={{ once: true }} transition={{ duration: 0.7 }} />

                <div className="relative z-10 max-w-3xl mx-auto text-center">
                    {/* Eyebrow */}
                    <motion.div className="flex items-center justify-center gap-4 mb-8"
                        initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}>
                        <div className="h-px w-16 bg-emerald-500/35" />
                        <span className="font-mono text-xs tracking-widest text-emerald-500 uppercase">{s.eyebrow}</span>
                        <div className="h-px w-16 bg-emerald-500/35" />
                    </motion.div>

                    {/* Headline */}
                    <motion.h2 className="font-black tracking-tight leading-tight mb-6"
                        style={{ fontSize: 'clamp(2.5rem, 7vw, 4.5rem)' }}
                        initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }} transition={{ delay: 0.1 }}>
                        {s.h2}<br />
                        <span className="text-emerald-400">{s.h2b}</span>
                    </motion.h2>

                    {/* Body */}
                    <motion.p className="text-slate-400 text-xl leading-relaxed mb-12 max-w-lg mx-auto"
                        initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }} transition={{ delay: 0.2 }}>
                        {s.body}
                    </motion.p>

                    {/* CTAs */}
                    <motion.div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16"
                        initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }} transition={{ delay: 0.3 }}>
                        <a href="mailto:contacto@bess-solutions.cl"
                            className="group flex items-center gap-3 bg-emerald-500 hover:bg-emerald-400 text-black font-bold px-8 py-4
                rounded-xl transition-all duration-200 text-base shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/45 hover:scale-105">
                            <Zap size={18} />
                            {s.cta_primary}
                            <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
                        </a>
                        <a href="https://github.com/open-bess-edge" target="_blank" rel="noopener noreferrer"
                            className="group flex items-center gap-3 border border-slate-700 hover:border-slate-500 text-slate-300 hover:text-white
                font-semibold px-8 py-4 rounded-xl transition-all duration-200 hover:bg-slate-800/45">
                            <Github size={18} />
                            {s.cta_secondary}
                        </a>
                    </motion.div>

                    {/* Stats */}
                    <motion.div className="grid grid-cols-3 gap-6 max-w-sm mx-auto"
                        initial={{ opacity: 0 }} whileInView={{ opacity: 1 }}
                        viewport={{ once: true }} transition={{ delay: 0.5 }}>
                        {s.stats.map((stat, i) => (
                            <div key={i} className="text-center">
                                <div className="font-mono text-base font-bold text-emerald-400 mb-1">{stat.val}</div>
                                <div className="font-mono text-xs text-slate-600 tracking-widest uppercase">{stat.lbl}</div>
                            </div>
                        ))}
                    </motion.div>
                </div>
            </div>

            {/* ── FOOTER ──────────────────────────────────── */}
            <footer className="relative bg-black border-t border-slate-900">
                <div className="max-w-6xl mx-auto px-8 py-12">

                    {/* Top: logo + nav columns */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-14">
                        {/* Brand */}
                        <div className="col-span-2 md:col-span-1">
                            <div className="flex items-center gap-2 mb-4">
                                <div className="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
                                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-400"
                                        style={{ animation: 'blink 2.5s ease-in-out infinite' }} />
                                </div>
                                <span className="font-mono font-bold text-white tracking-tight">BESSAI</span>
                                <span className="font-mono text-xs text-emerald-400/60 tracking-widest">EDGE</span>
                            </div>
                            <p className="text-slate-500 text-sm leading-relaxed mb-5">
                                Open source intelligence layer for Battery Energy Storage Systems.
                            </p>
                            {/* Social links */}
                            <div className="flex items-center gap-3">
                                {s.social.map((soc) => {
                                    const Icon = SOCIAL_ICONS[soc.icon]
                                    return Icon ? (
                                        <a key={soc.name} href={soc.href}
                                            target={soc.href.startsWith('mailto') ? '_self' : '_blank'}
                                            rel="noopener noreferrer"
                                            aria-label={soc.name}
                                            className="w-8 h-8 flex items-center justify-center rounded-lg border border-slate-800
                        text-slate-600 hover:text-emerald-400 hover:border-emerald-500/40 transition-all duration-200">
                                            <Icon size={14} />
                                        </a>
                                    ) : null
                                })}
                            </div>
                        </div>

                        {/* Nav columns */}
                        {['product', 'resources', 'company'].map((key) => {
                            const col = s.footer_nav[key]
                            return (
                                <div key={key}>
                                    <h4 className="font-mono text-xs font-semibold tracking-widest uppercase text-slate-400 mb-4">
                                        {col.title}
                                    </h4>
                                    <ul className="space-y-2.5">
                                        {col.links.map((link, i) => (
                                            <li key={i}>
                                                <a href={link.href}
                                                    target={link.href.startsWith('http') ? '_blank' : '_self'}
                                                    rel="noopener noreferrer"
                                                    className="text-slate-500 hover:text-slate-300 text-sm transition-colors duration-150">
                                                    {link.label}
                                                </a>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )
                        })}
                    </div>

                    {/* Divider */}
                    <div className="border-t border-slate-900 pt-8 flex flex-col sm:flex-row items-center justify-between gap-3">
                        <p className="font-mono text-xs text-slate-700">{s.legal}</p>
                        <p className="font-mono text-xs text-slate-800">{s.legal2}</p>
                    </div>
                </div>
            </footer>
        </section>
    )
}
