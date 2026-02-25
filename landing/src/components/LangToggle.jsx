import { useLang } from '../i18n/LangContext'

export default function LangToggle() {
    const { lang, toggle } = useLang()
    return (
        <button
            onClick={toggle}
            className="fixed top-5 right-6 z-50 font-mono text-xs border border-slate-700 hover:border-emerald-500/50
        text-slate-400 hover:text-emerald-400 px-3 py-1.5 rounded-lg bg-slate-950/80 backdrop-blur-sm
        transition-all duration-200 tracking-widest uppercase"
            aria-label="Switch language"
        >
            {lang === 'es' ? 'EN' : 'ES'}
        </button>
    )
}
