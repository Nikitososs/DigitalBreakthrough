import { useState, useEffect, useCallback } from 'react'

import UploadScreen from './screens/UploadScreen'
import ProgressScreen from './screens/ProgressScreen'
import DashboardScreen from './screens/DashboardScreen'
import DrilldownScreen from './screens/DrilldownScreen'
import ArchiveScreen from './screens/ArchiveScreen'
import LoginScreen from './screens/LoginScreen'
import AdminScreen from './screens/AdminScreen'

import { api, setUnauthorizedHandler } from './api/client'
import { clearAuth, getStoredUser, getToken } from './auth/storage'
import { LIVE_TASK_ID } from './constants'

const TASK_KEY = 'zeroproblems_task_id'
const DEMO_KEY = 'zeroproblems_demo'
const THEME_KEY = 'omsk_pulse_theme'
const ARCHIVE_KEY = 'zeroproblems_from_archive'

export default function App() {
  const [authUser, setAuthUser] = useState(() => getStoredUser())
  const [authChecked, setAuthChecked] = useState(false)
  const [screen, setScreen] = useState('upload')
  const [taskId, setTaskId] = useState(() => localStorage.getItem(TASK_KEY) || null)
  const [isDemo, setIsDemo] = useState(() => localStorage.getItem(DEMO_KEY) === '1')
  const [fromArchive, setFromArchive] = useState(() => localStorage.getItem(ARCHIVE_KEY) === '1')
  const [selectedDistrict, setSelectedDistrict] = useState(null)
  const [operatorInitialDistrict, setOperatorInitialDistrict] = useState(null)
  const [initialDashboardRole, setInitialDashboardRole] = useState(null)
  const [initialLiveOn, setInitialLiveOn] = useState(false)
  const [dark, setDark] = useState(false)
  const [bootstrapped, setBootstrapped] = useState(false)

  const handleLogout = useCallback(() => {
    clearAuth()
    setAuthUser(null)
    setBootstrapped(false)
    setScreen('upload')
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(handleLogout)
  }, [handleLogout])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light')
  }, [dark])

  useEffect(() => {
    if (!getToken()) {
      setAuthUser(null)
      setAuthChecked(true)
      return
    }
    const storedUser = getStoredUser()
    if (localStorage.getItem(DEMO_KEY) === '1' && storedUser) {
      setAuthUser(storedUser)
      setAuthChecked(true)
      return
    }
    api.me()
      .then((user) => setAuthUser(user))
      .catch(() => {
        clearAuth()
        setAuthUser(null)
      })
      .finally(() => setAuthChecked(true))
  }, [])

  useEffect(() => {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'dark') setDark(true)
  }, [])

  useEffect(() => {
    if (!authUser || bootstrapped) return

    const params = new URLSearchParams(window.location.search)
    const openLive = params.get('live') === '1' || params.get('task') === LIVE_TASK_ID

    if (openLive) {
      localStorage.setItem(TASK_KEY, LIVE_TASK_ID)
      localStorage.setItem(ARCHIVE_KEY, '1')
      localStorage.removeItem(DEMO_KEY)
      setTaskId(LIVE_TASK_ID)
      setFromArchive(true)
      setIsDemo(false)
      setInitialDashboardRole(params.get('role') === 'analyst' ? 'analyst' : 'operator')
      setInitialLiveOn(true)
      setScreen('dashboard')
      setBootstrapped(true)
      window.history.replaceState({}, '', window.location.pathname)
      return
    }

    const demo = localStorage.getItem(DEMO_KEY) === '1'
    const tid = localStorage.getItem(TASK_KEY)
    const archive = localStorage.getItem(ARCHIVE_KEY) === '1'

    if (demo) {
      setIsDemo(true)
      setScreen('dashboard')
      setBootstrapped(true)
      return
    }

    if (!tid) {
      api.getArchiveJobs()
        .then((data) => {
          const defaultId = data.default_task_id || data.jobs?.[0]?.task_id
          if (defaultId) {
            localStorage.setItem(TASK_KEY, defaultId)
            localStorage.setItem(ARCHIVE_KEY, '1')
            setTaskId(defaultId)
            setFromArchive(true)
            if (authUser.role === 'operator') {
              setInitialDashboardRole(authUser.role)
            }
            setScreen('dashboard')
            return
          }
          if (authUser.role !== 'admin') {
            setScreen('archive')
          }
        })
        .catch(() => {})
        .finally(() => setBootstrapped(true))
      return
    }

    setTaskId(tid)
    setFromArchive(archive)

    if (archive) {
      setScreen('dashboard')
      setBootstrapped(true)
      return
    }

    api.getJob(tid)
      .then((job) => {
        if (job.status === 'completed') setScreen('dashboard')
        else if (job.status === 'failed') setScreen('progress')
        else setScreen('progress')
      })
      .catch(() => setScreen('upload'))
      .finally(() => setBootstrapped(true))
  }, [authUser, bootstrapped])

  const handleUploadStarted = (id) => {
    setIsDemo(false)
    setFromArchive(false)
    localStorage.removeItem(DEMO_KEY)
    localStorage.removeItem(ARCHIVE_KEY)
    localStorage.setItem(TASK_KEY, id)
    setTaskId(id)
    setScreen('progress')
  }

  const handleDemoStart = () => {
    setIsDemo(true)
    setFromArchive(false)
    localStorage.setItem(DEMO_KEY, '1')
    localStorage.removeItem(TASK_KEY)
    localStorage.removeItem(ARCHIVE_KEY)
    setTaskId(null)
    setScreen('progress')
  }

  const handleOpenArchive = () => setScreen('archive')

  const handleArchiveOpenJob = (id, { asOperator = false } = {}) => {
    setIsDemo(false)
    setFromArchive(true)
    localStorage.removeItem(DEMO_KEY)
    localStorage.setItem(ARCHIVE_KEY, '1')
    localStorage.setItem(TASK_KEY, id)
    setTaskId(id)
    setInitialDashboardRole(asOperator ? 'operator' : null)
    setInitialLiveOn(id === LIVE_TASK_ID)
    setScreen('dashboard')
  }

  const handleAnalysisDone = () => setScreen('dashboard')

  const handleDistrictClick = (d) => {
    setSelectedDistrict(d)
    setScreen('drilldown')
  }

  const handleSendToOperator = (districtName) => {
    setOperatorInitialDistrict(districtName)
    setSelectedDistrict(null)
    setScreen('dashboard')
  }

  const handleBack = () => {
    setSelectedDistrict(null)
    setScreen('dashboard')
  }

  const handleReset = () => {
    localStorage.removeItem(TASK_KEY)
    localStorage.removeItem(DEMO_KEY)
    localStorage.removeItem(ARCHIVE_KEY)
    setTaskId(null)
    setIsDemo(false)
    setFromArchive(false)
    setSelectedDistrict(null)
    setScreen('upload')
  }

  const handleBackToArchive = () => {
    setSelectedDistrict(null)
    setScreen('archive')
  }

  const toggleTheme = () => setDark((d) => !d)

  if (!authChecked) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }} />
    )
  }

  if (!authUser) {
    return (
      <LoginScreen
        dark={dark}
        onToggleTheme={toggleTheme}
        onLoggedIn={(user) => {
          setAuthUser(user)
          setAuthChecked(true)
        }}
      />
    )
  }

  if (screen === 'admin') {
    return (
      <AdminScreen
        dark={dark}
        onToggleTheme={toggleTheme}
        onBack={() => setScreen(bootstrapped ? 'dashboard' : 'upload')}
      />
    )
  }

  if (!bootstrapped) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }} />
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      {screen === 'upload' && (
        <UploadScreen
          onUploadStarted={handleUploadStarted}
          onDemoStart={handleDemoStart}
          onOpenArchive={handleOpenArchive}
          dark={dark}
          onToggleTheme={toggleTheme}
          authUser={authUser}
          onLogout={handleLogout}
          onOpenAdmin={() => setScreen('admin')}
        />
      )}

      {screen === 'archive' && (
        <ArchiveScreen
          onOpenJob={handleArchiveOpenJob}
          onBack={() => setScreen('upload')}
          onNewUpload={handleReset}
          dark={dark}
          onToggleTheme={toggleTheme}
          authUser={authUser}
          onLogout={handleLogout}
          onOpenAdmin={() => setScreen('admin')}
        />
      )}

      {screen === 'progress' && (
        <ProgressScreen
          taskId={isDemo ? null : taskId}
          onDone={handleAnalysisDone}
          onReset={handleReset}
        />
      )}

      {(screen === 'dashboard' || screen === 'drilldown') && (
        <div className={screen === 'dashboard' ? 'contents' : 'hidden'} aria-hidden={screen !== 'dashboard'}>
          <DashboardScreen
            taskId={isDemo ? null : taskId}
            isDemo={isDemo}
            fromArchive={fromArchive}
            onDistrictClick={handleDistrictClick}
            onReset={handleReset}
            onOpenArchive={handleOpenArchive}
            onBackToArchive={handleBackToArchive}
            dark={dark}
            onToggleTheme={toggleTheme}
            initialOperatorDistrict={operatorInitialDistrict}
            onOperatorDistrictConsumed={() => setOperatorInitialDistrict(null)}
            initialDashboardRole={initialDashboardRole}
            onInitialDashboardRoleConsumed={() => setInitialDashboardRole(null)}
            initialLiveOn={initialLiveOn}
            onInitialLiveOnConsumed={() => setInitialLiveOn(false)}
            authUser={authUser}
            onLogout={handleLogout}
            onOpenAdmin={() => setScreen('admin')}
          />
        </div>
      )}

      {screen === 'drilldown' && selectedDistrict && (
        <DrilldownScreen
          district={selectedDistrict}
          taskId={isDemo ? null : taskId}
          isDemo={isDemo}
          onBack={handleBack}
          onSendToOperator={handleSendToOperator}
          dark={dark}
          onToggleTheme={toggleTheme}
        />
      )}
    </div>
  )
}
