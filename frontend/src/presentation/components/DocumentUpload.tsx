import { useState, useRef } from 'react'
import type { DragEvent, ChangeEvent, FormEvent } from 'react'
import { uploadDocument } from '../../infrastructure/http/documentApi'
import type { UploadedDocument, UploadError } from '../../infrastructure/http/documentApi'

// ─── Types ───────────────────────────────────────────────────────────────────
type UploadStatus = 'idle' | 'uploading' | 'success' | 'error'

const DOCUMENT_TYPES = [
  { value: 'EXAME', label: 'Exame' },
  { value: 'LAUDO', label: 'Laudo' },
  { value: 'PRONTUARIO', label: 'Prontuário' },
  { value: 'CONTRATO', label: 'Contrato' },
  { value: 'RECEITA', label: 'Receita Médica' },
  { value: 'RELATORIO', label: 'Relatório' },
  { value: 'OUTRO', label: 'Outro' },
]

const ACCEPTED_TYPES = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif']

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(2)} MB`
}

function getFileIcon(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase()
  if (ext === 'pdf') return '📄'
  if (['jpg', 'jpeg', 'png'].includes(ext ?? '')) return '🖼️'
  return '📎'
}

// ─── Component ────────────────────────────────────────────────────────────────
export function DocumentUpload() {
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [title, setTitle] = useState('')
  const [documentType, setDocumentType] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [ownerRecord, setOwnerRecord] = useState('')
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<UploadStatus>('idle')
  const [successDocs, setSuccessDocs] = useState<UploadedDocument[]>([])
  const [errorFiles, setErrorFiles] = useState<UploadError[]>([])
  const [successMessage, setSuccessMessage] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const ACCEPTED_EXT = ACCEPTED_TYPES.map(e => e.replace('.', ''))

  const addFiles = (newFiles: File[]) => {
    const valid: File[] = []
    const invalid: string[] = []

    for (const f of newFiles) {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
      if (ACCEPTED_EXT.includes(ext)) {
        // Evitar duplicatas pelo nome
        if (!files.find(existing => existing.name === f.name)) {
          valid.push(f)
        }
      } else {
        invalid.push(f.name)
      }
    }

    if (invalid.length > 0) {
      setErrorMsg(`Arquivo(s) ignorado(s) — formato não suportado: ${invalid.join(', ')}`)
      setStatus('error')
    } else {
      setStatus('idle')
      setErrorMsg('')
    }

    if (valid.length > 0) {
      setFiles(prev => [...prev, ...valid])
      if (!title && valid[0]) setTitle(valid[0].name.replace(/\.[^.]+$/, ''))
    }
  }

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    addFiles(Array.from(e.dataTransfer.files))
  }

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(Array.from(e.target.files))
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (files.length === 0 || !title || !documentType || !ownerName) {
      setErrorMsg('Preencha todos os campos e selecione ao menos um arquivo.')
      setStatus('error')
      return
    }

    setStatus('uploading')
    setProgress(0)
    setErrorMsg('')

    try {
      const result = await uploadDocument(
        { files, title, document_type: documentType, owner_name: ownerName, owner_record_number: ownerRecord || undefined },
        setProgress,
      )
      setSuccessDocs(result.documentos)
      setErrorFiles(result.erros)
      setSuccessMessage(result.message)
      setStatus('success')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? (err as { message?: string })?.message ?? 'Erro desconhecido.'
      setErrorMsg(msg)
      setStatus('error')
    }
  }

  const reset = () => {
    setFiles([]); setTitle(''); setDocumentType(''); setOwnerName(''); setOwnerRecord('')
    setStatus('idle'); setProgress(0); setErrorMsg(''); setSuccessDocs([]); setErrorFiles([])
    if (inputRef.current) inputRef.current.value = ''
  }

  const totalSize = files.reduce((acc, f) => acc + f.size, 0)

  return (
    <div className="upload-page">
      <h2 className="upload-title">
        <span className="upload-icon">📄</span> Incluir Digitalização
      </h2>
      <p className="upload-subtitle">
        Simule um scanner selecionando múltiplos arquivos de uma vez. Endpoint:{' '}
        <code>/upload-dev</code>
      </p>

      {status === 'success' ? (
        <div className="upload-success" data-testid="success-message">
          <div className="success-icon">✅</div>
          <h3>{successMessage}</h3>

          {successDocs.length > 0 && (
            <div className="success-details">
              <p style={{ marginBottom: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                Documentos salvos:
              </p>
              {successDocs.map((doc) => (
                <div key={doc.document_id} className="success-doc-item">
                  <span>{getFileIcon(doc.file)} {doc.file}</span>
                  <code>{doc.document_id}</code>
                </div>
              ))}
            </div>
          )}

          {errorFiles.length > 0 && (
            <div className="error-msg" style={{ marginBottom: '20px' }}>
              ⚠️ {errorFiles.length} arquivo(s) com erro:
              {errorFiles.map((e) => (
                <div key={e.file} style={{ fontSize: '0.85rem', marginTop: '4px' }}>
                  • {e.file}: {e.error}
                </div>
              ))}
            </div>
          )}

          <button className="btn-primary" onClick={reset}>
            Enviar mais documentos
          </button>
        </div>
      ) : (
        <form className="upload-form" onSubmit={handleSubmit} noValidate data-testid="upload-form">
          {/* Drop Zone */}
          <div
            className={`drop-zone ${dragging ? 'dragging' : ''} ${files.length > 0 ? 'has-file' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            role="button"
            aria-label="Área de upload — clique ou arraste arquivos"
            data-testid="drop-zone"
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED_TYPES.join(',')}
              multiple
              onChange={onFileChange}
              style={{ display: 'none' }}
              data-testid="file-input"
            />

            {files.length === 0 ? (
              <div className="drop-placeholder">
                <span className="drop-icon">☁️</span>
                <p>Arraste os arquivos aqui ou <strong>clique para selecionar</strong></p>
                <p className="drop-hint">Múltiplos arquivos permitidos • PDF, JPG, PNG, TIFF • Máx. 50MB por arquivo</p>
              </div>
            ) : (
              <div className="drop-placeholder">
                <span className="drop-icon">📚</span>
                <p><strong>{files.length} arquivo(s)</strong> selecionado(s) — {formatBytes(totalSize)} no total</p>
                <p className="drop-hint">Clique para adicionar mais arquivos</p>
              </div>
            )}
          </div>

          {/* File Queue */}
          {files.length > 0 && (
            <div className="file-queue" data-testid="file-queue">
              {files.map((f, i) => (
                <div key={`${f.name}-${i}`} className="file-queue-item">
                  <span className="file-queue-icon">{getFileIcon(f.name)}</span>
                  <div className="file-queue-info">
                    <span className="file-name">{f.name}</span>
                    <span className="file-size">{formatBytes(f.size)}</span>
                  </div>
                  <button
                    type="button"
                    className="file-queue-remove"
                    onClick={(e) => { e.stopPropagation(); removeFile(i) }}
                    aria-label={`Remover ${f.name}`}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Fields */}
          <div className="upload-fields">
            <div className="field-group">
              <label htmlFor="upload-title">
                Título Base *
                {files.length > 1 && (
                  <span className="field-hint"> (será numerado automaticamente: Título 1/2, 2/2…)</span>
                )}
              </label>
              <input
                id="upload-title"
                type="text"
                className="search-input"
                placeholder="Ex: Laudo de Ressonância Magnética"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="field-group">
              <label htmlFor="upload-type">Tipo de Documento *</label>
              <select
                id="upload-type"
                className="search-input"
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                required
                data-testid="document-type-select"
              >
                <option value="">Selecione o tipo...</option>
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            <div className="field-group">
              <label htmlFor="upload-owner">Nome do Paciente / Titular *</label>
              <input
                id="upload-owner"
                type="text"
                className="search-input"
                placeholder="Nome completo"
                value={ownerName}
                onChange={(e) => setOwnerName(e.target.value)}
                required
              />
            </div>

            <div className="field-group">
              <label htmlFor="upload-record">Número do Prontuário (opcional)</label>
              <input
                id="upload-record"
                type="text"
                className="search-input"
                placeholder="Ex: 00123456"
                value={ownerRecord}
                onChange={(e) => setOwnerRecord(e.target.value)}
              />
            </div>
          </div>

          {/* Progress */}
          {status === 'uploading' && (
            <div className="progress-container" data-testid="progress-bar">
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <p className="progress-label">
                Enviando {files.length} arquivo(s)... {progress}%
              </p>
            </div>
          )}

          {/* Error */}
          {status === 'error' && errorMsg && (
            <div className="error-msg" data-testid="error-message">
              ⚠️ {errorMsg}
            </div>
          )}

          {/* Actions */}
          <div className="upload-actions">
            {files.length > 0 && (
              <button type="button" className="btn-secondary" onClick={reset}>
                Limpar tudo
              </button>
            )}
            <button
              type="submit"
              className="btn-primary"
              disabled={status === 'uploading' || files.length === 0}
              data-testid="submit-button"
            >
              {status === 'uploading'
                ? `⏳ Enviando ${files.length} arquivo(s)...`
                : `📤 Enviar ${files.length > 0 ? files.length : ''} Documento(s)`}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
