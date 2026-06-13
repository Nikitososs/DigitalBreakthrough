import { useState, useCallback } from 'react'
import { Upload, FileSpreadsheet, Zap, ArrowRight, AlertCircle, Database, Send } from 'lucide-react'
import ThemeToggle from '../components/ThemeToggle'
import UserMenu from '../components/UserMenu'
import { api } from '../api/client'

export default function UploadScreen({
  onUploadStarted,
  onDemoStart,
  onOpenArchive,
  dark,
  onToggleTheme,
  authUser,
  onLogout,
  onOpenAdmin,
}) {
  const canUpload = authUser?.role === 'admin'
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) {
      setFile(f)
      setError('')
    }
  }, [])

  const handleStart = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const res = await api.uploadDataset(file)
      onUploadStarted(res.task_id)
    } catch (err) {
      setError(err.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden" style={{ background: 'var(--bg)' }}>

      {/* Фоновые пятна */}
      <div aria-hidden style={{
        position: 'absolute', top: '-80px', right: '-60px',
        width: '380px', height: '380px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc26261f 0%, #dc262608 45%, transparent 68%)',
        pointerEvents: 'none',
      }} />
      <div aria-hidden style={{
        position: 'absolute', bottom: '-80px', left: '-40px',
        width: '340px', height: '340px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc26261a 0%, #dc262606 45%, transparent 68%)',
        pointerEvents: 'none',
      }} />
      <div aria-hidden style={{
        position: 'absolute', top: '38%', left: '-100px',
        width: '300px', height: '300px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc262614 0%, transparent 65%)',
        pointerEvents: 'none',
      }} />
      <div aria-hidden style={{
        position: 'absolute', top: '20%', right: '8%',
        width: '200px', height: '200px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc262610 0%, transparent 65%)',
        pointerEvents: 'none',
      }} />
      <div aria-hidden style={{
        position: 'absolute', bottom: '20%', right: '-60px',
        width: '260px', height: '260px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc262616 0%, transparent 65%)',
        pointerEvents: 'none',
      }} />

      <div className="flex justify-between items-center gap-2 p-4 relative z-10">
        <UserMenu user={authUser} onLogout={onLogout} onOpenAdmin={onOpenAdmin} />
        <ThemeToggle dark={dark} onToggle={onToggleTheme} />
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-4 pb-16 anim-fade relative z-10">

        {/* Логотип */}
        <div className="mb-10 text-center">
          <div className="inline-flex items-center justify-center w-20 h-20 mb-5 relative">
            <span aria-hidden style={{
              position: 'absolute', inset: '-6px', borderRadius: '28px',
              border: '2px solid #dc262630',
              animation: 'uploadRingPulse 2.4s ease-out infinite',
            }} />
            <span style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '80px', height: '80px', borderRadius: '24px',
              background: 'linear-gradient(145deg, #ef4444 0%, #b91c1c 100%)',
              boxShadow: '0 16px 40px -12px #dc2626aa, inset 0 1px 0 rgb(255 255 255 / 0.18)',
            }}>
              <Zap className="w-9 h-9 text-white" />
            </span>
          </div>
          <h1 className="text-4xl font-bold tracking-tight mb-2" style={{ color: 'var(--text)' }}>
            ZeroProblems
          </h1>
          <p className="text-xs tracking-widest uppercase font-semibold" style={{ color: 'var(--muted)' }}>
            Аналитика обращений граждан
          </p>
        </div>

        {canUpload ? (
          <>
            {/* Зона загрузки */}
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onClick={() => document.getElementById('file-input').click()}
              className="w-full max-w-md cursor-pointer transition-all duration-200"
              style={{
                borderRadius: '28px',
                padding: '40px 32px',
                textAlign: 'center',
                background: dragging
                  ? 'color-mix(in srgb, #dc2626 6%, var(--bg-card))'
                  : file
                    ? 'color-mix(in srgb, #10b981 5%, var(--bg-card))'
                    : 'var(--bg-card)',
                border: `2px dashed ${dragging ? '#dc2626' : file ? '#10b981' : 'var(--border)'}`,
                boxShadow: dragging
                  ? '0 0 0 4px #dc262614, 0 20px 60px -20px rgb(0 0 0 / 0.1)'
                  : '0 20px 60px -20px rgb(0 0 0 / 0.08)',
                transform: dragging ? 'scale(1.01)' : 'scale(1)',
              }}
            >
              <input
                id="file-input"
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files[0]) {
                    setFile(e.target.files[0])
                    setError('')
                  }
                }}
              />

              {file ? (
                <>
                  <div style={{
                    width: '60px', height: '60px', borderRadius: '18px',
                    background: 'color-mix(in srgb, #10b981 14%, var(--bg-card))',
                    border: '1px solid color-mix(in srgb, #10b981 30%, var(--border))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 16px',
                  }}>
                    <FileSpreadsheet className="w-7 h-7" style={{ color: '#10b981' }} />
                  </div>
                  <p className="font-semibold mb-1" style={{ color: 'var(--text)' }}>{file.name}</p>
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>
                    {(file.size / 1024).toFixed(1)} КБ · Готово к загрузке
                  </p>
                </>
              ) : (
                <>
                  <div style={{
                    width: '60px', height: '60px', borderRadius: '18px',
                    background: dragging
                      ? 'color-mix(in srgb, #dc2626 12%, var(--bg-card))'
                      : 'var(--bg-sub)',
                    border: `1px solid ${dragging ? 'color-mix(in srgb, #dc2626 30%, var(--border))' : 'var(--border)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 16px',
                    transition: 'all 0.2s',
                  }}>
                    <Upload className="w-7 h-7" style={{ color: dragging ? '#dc2626' : 'var(--muted)' }} />
                  </div>
                  <p className="font-semibold mb-1" style={{ color: 'var(--text)' }}>
                    {dragging ? 'Отпустите файл' : 'Перетащите Excel файл'}
                  </p>
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>или кликните · .xlsx .xls</p>
                </>
              )}
            </div>

            {error && (
              <div className="mt-4 flex items-center gap-2 text-sm max-w-md"
                style={{ padding: '10px 14px', borderRadius: '12px', background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c' }}
              >
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 flex flex-col items-center gap-3 w-full max-w-md">
              <button
                onClick={handleStart}
                disabled={!file || loading}
                className="w-full flex items-center justify-center gap-2 text-sm font-bold text-white"
                style={{
                  borderRadius: '16px',
                  padding: '13px 20px',
                  background: 'linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)',
                  boxShadow: file && !loading ? '0 8px 24px -8px #dc2626aa, inset 0 1px 0 rgb(255 255 255 / 0.15)' : 'none',
                  opacity: !file || loading ? 0.45 : 1,
                  cursor: !file || loading ? 'not-allowed' : 'pointer',
                  transition: 'opacity 0.15s, box-shadow 0.15s, transform 0.1s',
                }}
                onMouseEnter={e => { if (file && !loading) e.currentTarget.style.transform = 'translateY(-1px)' }}
                onMouseLeave={e => { e.currentTarget.style.transform = '' }}
              >
                {loading ? 'Загрузка…' : 'Начать анализ'}
                {file && !loading && <ArrowRight className="w-4 h-4" />}
              </button>

              {!file && (
                <>
                  <a
                    href="/submit"
                    className="w-full flex items-center justify-center gap-2 text-sm font-bold text-white"
                    style={{
                      borderRadius: '16px', padding: '13px 20px',
                      background: 'linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)',
                      boxShadow: '0 8px 24px -8px #dc262688, inset 0 1px 0 rgb(255 255 255 / 0.15)',
                      transition: 'transform 0.1s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)' }}
                    onMouseLeave={e => { e.currentTarget.style.transform = '' }}
                  >
                    <Send className="w-4 h-4" />
                    Подать обращение
                  </a>

                  <button
                    type="button"
                    onClick={onOpenArchive}
                    className="w-full flex items-center justify-center gap-2 text-sm font-semibold"
                    style={{
                      borderRadius: '16px', padding: '13px 20px',
                      background: 'var(--bg-card)',
                      border: '1px solid color-mix(in srgb, #dc2626 15%, var(--border))',
                      color: 'var(--text)',
                      boxShadow: '0 4px 16px -8px rgb(0 0 0 / 0.08)',
                      transition: 'transform 0.1s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)' }}
                    onMouseLeave={e => { e.currentTarget.style.transform = '' }}
                  >
                    <Database className="w-4 h-4 text-red-600" />
                    Работа с базой
                  </button>

                  <button
                    onClick={onDemoStart}
                    className="text-xs transition-colors hover:text-red-500 mt-1"
                    style={{ color: 'var(--muted)' }}
                  >
                    Пропустить — demo (снимок данных)
                  </button>
                </>
              )}
            </div>
          </>
        ) : (
          <div className="text-center max-w-md w-full">
            <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
              Загрузка датасетов доступна только администратору. Откройте дашборд или базу данных.
            </p>
            <button
              type="button"
              onClick={onOpenArchive}
              className="flex items-center gap-2 px-5 py-3 rounded-2xl text-sm font-semibold mx-auto"
              style={{
                background: 'var(--bg-card)', color: 'var(--text)',
                border: '1px solid color-mix(in srgb, #dc2626 15%, var(--border))',
                boxShadow: '0 4px 16px -8px rgb(0 0 0 / 0.08)',
              }}
            >
              <Database className="w-4 h-4 text-red-600" />
              Работа с базой
            </button>
          </div>
        )}
      </div>

      <style>{`
        @keyframes uploadRingPulse {
          0%   { transform: scale(0.9); opacity: 0.8; }
          100% { transform: scale(1.4); opacity: 0; }
        }
      `}</style>
    </div>
  )
}
