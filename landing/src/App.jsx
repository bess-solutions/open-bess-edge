import { LangProvider } from './i18n/LangContext'
import Scene1Earth from './scenes/Scene1Earth'
import Scene2Paradox from './scenes/Scene2Paradox'
import Scene3BlackBox from './scenes/Scene3BlackBox'
import Scene4Activation from './scenes/Scene4Activation'
import SceneFeatures from './scenes/SceneFeatures'
import Scene5Sync from './scenes/Scene5Sync'
import SceneFAQ from './scenes/SceneFAQ'
import Scene6CTA from './scenes/Scene6CTA'
import NavDots from './components/NavDots'
import LangToggle from './components/LangToggle'

export default function App() {
  return (
    <LangProvider>
      <main className="bg-slate-950 text-white overflow-x-hidden">
        <NavDots />
        <LangToggle />
        <Scene1Earth />
        <Scene2Paradox />
        <Scene3BlackBox />
        <Scene4Activation />
        <SceneFeatures />
        <Scene5Sync />
        <SceneFAQ />
        <Scene6CTA />
      </main>
    </LangProvider>
  )
}
