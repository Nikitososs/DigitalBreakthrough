import { useEffect, useState } from 'react'

import SubmitComplaintScreen from './screens/SubmitComplaintScreen'

const THEME_KEY = 'omsk_pulse_theme'

export default function CitizenSubmitApp() {
  const [dark, setDark] = useState(false)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light')
  }, [dark])

  useEffect(() => {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'dark') setDark(true)
  }, [])

  return (
    <div className="citizen-submit-app">
      <SubmitComplaintScreen
        useLiveStream
        standalone
        dark={dark}
        onToggleTheme={() => setDark((d) => !d)}
      />
    </div>
  )
}
