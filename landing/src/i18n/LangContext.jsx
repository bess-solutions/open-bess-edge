import { createContext, useContext, useState, useEffect } from 'react'
import { TRANSLATIONS, detectLanguage } from './translations'

const LangContext = createContext(null)

export function LangProvider({ children }) {
    const [lang, setLang] = useState(() => detectLanguage())
    const t = TRANSLATIONS[lang]

    // Expose toggle for the UI language switcher
    function toggle() {
        setLang(prev => prev === 'es' ? 'en' : 'es')
    }

    return (
        <LangContext.Provider value={{ t, lang, toggle }}>
            {children}
        </LangContext.Provider>
    )
}

export function useLang() {
    const ctx = useContext(LangContext)
    if (!ctx) throw new Error('useLang must be inside LangProvider')
    return ctx
}
