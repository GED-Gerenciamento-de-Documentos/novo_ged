import { useState } from 'react';
import { Search, FileText, Calendar, HardDrive, Loader2, Image as ImageIcon, ChevronLeft, ChevronRight } from 'lucide-react';
import { usePatientDocuments } from '../../application/usePatientDocuments';
import { ImageViewer } from './ImageViewer';
import type { LegacyDocument } from '../../domain/legacy_document';

export function PatientSearch() {
  const [patientId, setPatientId] = useState('');
  const { data, loading, error, fetchDocuments, goToPage, pageSize, changePageSize } = usePatientDocuments();
  const [modalFile, setModalFile] = useState<{ url: string, downloadUrl: string, title: string } | null>(null);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientId.trim()) return;
    fetchDocuments(Number(patientId), 1);
  };

  const formatDate = (dateStr: string) => {
    try {
      if (!dateStr) return 'Desconhecida';
      return new Date(dateStr).toLocaleDateString('pt-BR');
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="container">
      <h1 className="header-title">Arquivos Legado do GED</h1>
      
      <form className="search-container" onSubmit={handleSearch}>
        <input 
          type="number" 
          className="search-input" 
          placeholder="Digite o Patient ID (ex: 1004662)" 
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
          required
        />
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? <Loader2 className="spinner" size={20} /> : <Search size={20} />}
          Buscar
        </button>
      </form>

      {error && <div className="error-msg">{error}</div>}

      {loading && !data && (
        <div className="loader-container">
          <Loader2 className="spinner" size={48} />
          <p style={{ marginTop: '16px', color: 'var(--text-secondary)' }}>
            Consultando Oracle e verificando arquivos de rede...
          </p>
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="empty-state">
          <FileText size={64} style={{ marginBottom: '16px', opacity: 0.5 }} />
          <h3>Nenhum documento encontrado</h3>
          <p style={{ marginTop: '8px' }}>O paciente {data.patient_id} não possui arquivos legados no banco de dados.</p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', textAlign: 'center' }}>
            Encontrados <strong>{data.total}</strong> documentos para o paciente <strong>{data.patient_id}</strong>
          </p>

          {/* Controles de paginação — topo */}
          <div className="pagination-bar">
            <div className="pagination-info">
              Página <strong>{data.page}</strong> de <strong>{data.total_pages}</strong>
              &nbsp;·&nbsp;
              {(data.page - 1) * pageSize + 1}–{Math.min(data.page * pageSize, data.total)} de {data.total}
            </div>
            <div className="pagination-controls">
              <select
                className="page-size-select"
                value={pageSize}
                onChange={(e) => changePageSize(Number(e.target.value))}
              >
                {[20, 50, 92, 100].map(n => (
                  <option key={n} value={n}>{n} por página</option>
                ))}
              </select>
              <button className="btn-page" onClick={() => goToPage(1)} disabled={data.page === 1} title="Primeira página">«</button>
              <button className="btn-page" onClick={() => goToPage(data.page - 1)} disabled={data.page === 1} title="Página anterior"><ChevronLeft size={16} /></button>
              {Array.from({ length: data.total_pages }, (_, i) => i + 1)
                .filter(p => p === 1 || p === data.total_pages || Math.abs(p - data.page) <= 2)
                .reduce<(number | '...')[]>((acc, p, idx, arr) => {
                  if (idx > 0 && (p as number) - (arr[idx - 1] as number) > 1) acc.push('...');
                  acc.push(p);
                  return acc;
                }, [])
                .map((p, i) =>
                  p === '...' ? (
                    <span key={`ellipsis-${i}`} className="btn-page" style={{ cursor: 'default', opacity: 0.4 }}>…</span>
                  ) : (
                    <button
                      key={p}
                      className={`btn-page${data.page === p ? ' active' : ''}`}
                      onClick={() => goToPage(p as number)}
                    >{p}</button>
                  )
                )
              }
              <button className="btn-page" onClick={() => goToPage(data.page + 1)} disabled={data.page === data.total_pages} title="Próxima página"><ChevronRight size={16} /></button>
              <button className="btn-page" onClick={() => goToPage(data.total_pages)} disabled={data.page === data.total_pages} title="Última página">»</button>
            </div>
          </div>

          <div className="docs-grid">
            {data.items.map((doc: LegacyDocument) => (
              <div className="doc-card" key={doc.row_id}>
                <div className="doc-card-header">
                  <h4 className="doc-title">{doc.nome_arquivo || "Sem Nome"}</h4>
                  <span className="doc-badge">{doc.formato || "ND"}</span>
                </div>

                <div style={{ margin: '8px 0', textAlign: 'center', minHeight: '160px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', overflow: 'hidden' }}>
                  <img
                    src={doc.thumbnail_url}
                    alt={`Prévia: ${doc.nome_arquivo}`}
                    loading="lazy"
                    style={{ maxWidth: '100%', maxHeight: '200px', objectFit: 'contain' }}
                    onError={(e) => {
                      const box = (e.currentTarget as HTMLImageElement).parentElement;
                      if (box) box.style.display = 'none';
                    }}
                  />
                </div>

                <div className="doc-meta">
                  <div className="doc-meta-item">
                    <Calendar size={16} /> Data de Inclusão: {formatDate(doc.metadata.dtinclusao || doc.metadata.creationdate)}
                  </div>
                  <div className="doc-meta-item">
                    <HardDrive size={16} /> Mapeamento Rede: Unidade {doc.drive}:
                  </div>
                </div>

                <div style={{ marginTop: 'auto' }}>
                  <button 
                    className="btn-view"
                    onClick={() => setModalFile({
                      url: doc.view_url,
                      downloadUrl: doc.download_url,
                      title: doc.nome_arquivo || `Documento ${doc.row_id}`
                    })}
                  >
                    <ImageIcon size={18} />
                    Visualizar Imagem
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {modalFile && (
        <ImageViewer 
          url={modalFile.url} 
          downloadUrl={modalFile.downloadUrl}
          title={modalFile.title} 
          onClose={() => setModalFile(null)} 
        />
      )}
    </div>
  );
}
