import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { useLang } from '../i18n/LangContext'

function FAQItem({ item, index, isOpen, onToggle }) {
    return (
        <motion.div
            className="border border-slate-800 hover:border-slate-700 rounded-xl overflow-hidden transition-colors duration-200"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-40px' }}
            transition={{ delay: index * 0.06, duration: 0.45 }}
        >
            <button
                className="w-full flex items-center justify-between px-6 py-5 text-left hover:bg-slate-900/40 transition-colors"
                onClick={onToggle}
            >
                <span className={`font-semibold text-base leading-snug pr-6 transition-colors ${isOpen ? 'text-emerald-400' : 'text-white'}`}>
                    {item.q}
                </span>
                <motion.div
                    animate={{ rotate: isOpen ? 180 : 0 }}
                    transition={{ duration: 0.25 }}
                    className="flex-shrink-0"
                >
                    <ChevronDown size={18} className={isOpen ? 'text-emerald-400' : 'text-slate-600'} />
                </motion.div>
            </button>

            <AnimatePresence initial={false}>
                {isOpen && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: [0.04, 0.62, 0.23, 0.98] }}
                    >
                        <div className="px-6 pb-6 pt-0 text-slate-400 text-base leading-relaxed border-t border-slate-800/60">
                            <div className="pt-4">{item.a}</div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    )
}

export default function SceneFAQ() {
    const { t } = useLang()
    const faq = t.faq
    const [openIndex, setOpenIndex] = useState(null)

    function toggle(i) {
        setOpenIndex(prev => prev === i ? null : i)
    }

    return (
        <section id="scene-faq" className="relative py-32 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-blue-950/5 to-slate-950" />

            <div className="relative z-10 max-w-3xl mx-auto px-8">
                {/* Header */}
                <motion.div className="text-center mb-16"
                    initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }} transition={{ duration: 0.7 }}>
                    <p className="text-xs font-mono tracking-widest text-blue-400 mb-4 uppercase">{faq.eyebrow}</p>
                    <h2 className="font-black leading-tight tracking-tight mb-4"
                        style={{ fontSize: 'clamp(2rem, 5vw, 3.8rem)' }}>
                        {faq.h2}<br />
                        <span className="text-blue-400">{faq.h2b}</span>
                    </h2>
                    <p className="text-slate-400 text-lg leading-relaxed">{faq.body}</p>
                </motion.div>

                {/* Accordion */}
                <div className="space-y-3">
                    {faq.items.map((item, i) => (
                        <FAQItem
                            key={i}
                            item={item}
                            index={i}
                            isOpen={openIndex === i}
                            onToggle={() => toggle(i)}
                        />
                    ))}
                </div>

                {/* CTA below */}
                <motion.div className="text-center mt-14"
                    initial={{ opacity: 0 }} whileInView={{ opacity: 1 }}
                    viewport={{ once: true }} transition={{ delay: 0.4 }}>
                    <p className="text-slate-500 text-sm mb-4 font-mono">
                        ¿Tienes otra pregunta? →
                    </p>
                    <a href="mailto:contacto@bess-solutions.cl"
                        className="inline-flex items-center gap-2 text-emerald-400 hover:text-emerald-300 font-mono text-sm
              border border-emerald-500/25 hover:border-emerald-500/50 px-5 py-2.5 rounded-lg transition-all">
                        contacto@bess-solutions.cl
                    </a>
                </motion.div>
            </div>
        </section>
    )
}
