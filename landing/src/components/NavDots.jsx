import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

const SCENES = [
    { id: 'scene-1', label: 'La Evidencia' },
    { id: 'scene-2', label: 'La Paradoja' },
    { id: 'scene-3', label: 'El Eslabón Perdido' },
    { id: 'scene-4', label: 'La Activación' },
    { id: 'scene-5', label: 'La Sincronización' },
    { id: 'scene-6', label: 'El Llamado' },
]

export default function NavDots() {
    const [active, setActive] = useState(0)

    useEffect(() => {
        const observers = SCENES.map((scene, i) => {
            const el = document.getElementById(scene.id)
            if (!el) return null
            const obs = new IntersectionObserver(([entry]) => {
                if (entry.isIntersecting) setActive(i)
            }, { threshold: 0.3 })
            obs.observe(el)
            return obs
        }).filter(Boolean)

        return () => observers.forEach(o => o.disconnect())
    }, [])

    return (
        <nav className="fixed right-6 top-1/2 -translate-y-1/2 z-50 flex flex-col gap-4" aria-label="Navigation">
            {SCENES.map((scene, i) => (
                <button
                    key={i}
                    aria-label={`Go to ${scene.label}`}
                    onClick={() => document.getElementById(scene.id)?.scrollIntoView({ behavior: 'smooth' })}
                    className="group relative flex items-center justify-end gap-3"
                >
                    {/* Label tooltip */}
                    <span className="font-mono text-xs text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap
            bg-slate-900/80 px-2 py-1 rounded border border-slate-800">
                        {scene.label}
                    </span>
                    {/* Dot */}
                    <motion.div
                        className="rounded-full border transition-colors duration-200"
                        animate={{
                            width: active === i ? '10px' : '6px',
                            height: active === i ? '10px' : '6px',
                            borderColor: active === i ? '#10b981' : '#334155',
                            backgroundColor: active === i ? '#10b981' : 'transparent',
                        }}
                    />
                </button>
            ))}
        </nav>
    )
}
