import { useState } from 'react';
import { Search, FileText, Calendar, Cloud, Database, Loader2, Image as ImageIcon, Download, ChevronLeft, ChevronRight, HardDrive } from 'lucide-react';
import { api } from '../../infrastructure/api';
import { ImageViewer } from './ImageViewer';

interface DocumentSearchResponse {
  items: any[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export function DocumentSearch() {
  const [ownerName, setOwnerName] = useState('');
  const [storageType, setStorageType] = useState('CLOUD');
  
  const [data, setData] = useState<DocumentSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [modalFile, setModalFile] = useState<{ url: string, downloadUrl: string, title: string } | null>(null);

  const fetchDocuments = async (currentPage: number, currentSize: number, currentStorage: string) => {
    try {
      setLoading(true);
      setError(null);
      
      const params = new URLSearchParams();
      if (ownerName) params.append('owner_name', ownerName);
      if (currentStorage) params.append('storage_type', currentStorage);
      params.append('page', String(currentPage));
      params.append('page_size', String(currentSize));

      const response = await api.get<DocumentSearchResponse>(`/api/v1/documents?${params.toString()}`);
      setData(response.data);
      setPage(currentPage);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Falha ao conectar na API para buscar documentos.');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchDocuments(1, pageSize, storageType);
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
      <h1 className="header-title">Busca Unificada de Documentos</h1>
      <p style={{textAlign: 'center', color: 'var(--text-secondary)', marginBottom: '32px'}}>
        Busque documentos recém-digitalizados (Nuvem AWS) ou consulte o acervo histórico (Legado Oracle).
      </p>
      
      <form className="search-container" onSubmit={handleSearch} style={{ flexWrap: 'wrap', gap: '16px', borderRadius: '12px', padding: '24px', background: 'var(--bg-secondary)' }}>
        
        <div style={{ display: 'flex', flex: 1, minWidth: '300px', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '14px', fontWeight: 'bold' }}>Nome do Paciente / Titular</label>
          <input 
            type="text" 
            className="search-input" 
            placeholder="Ex: João da Silva..." 
            value={ownerName}
            onChange={(e) => setOwnerName(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', minWidth: '200px', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '14px', fontWeight: 'bold' }}>Ambiente de Armazenamento</label>
          <select 
            className="search-input" 
            style={{ appearance: 'auto' }}
            value={storageType}
            onChange={(e) => {
              setStorageType(e.target.value);
            }}
          >
            <option value="CLOUD">AWS S3 (Nuvem)</option>
            <option value="LEGACY_NFS">Oracle 11g (Legado)</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button type="submit" className="btn-primary" disabled={loading} style={{ height: '48px' }}>
            {loading ? <Loader2 className="spinner" size={20} /> : <Search size={20} />}
            Buscar Documentos
          </button>
        </div>
      </form>

      {error && <div className="error-msg" style={{marginTop: '24px'}}>{error}</div>}

      {loading && !data && (
        <div className="loader-container">
          <Loader2 className="spinner" size={48} />
          <p style={{ marginTop: '16px', color: 'var(--text-secondary)' }}>
            Consultando repositórios...
          </p>
        </div>
      )}

      {data && data.items.length === 0 && !loading && (
        <div className="empty-state" style={{marginTop: '40px'}}>
          <FileText size={64} style={{ marginBottom: '16px', opacity: 0.5 }} />
          <h3>Nenhum documento encontrado</h3>
          <p style={{ marginTop: '8px' }}>Não foram encontrados documentos para estes filtros no ambiente selecionado.</p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <div style={{marginTop: '40px'}}>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', textAlign: 'center' }}>
            Encontrados <strong>{data.total}</strong> documentos
          </p>

          {/* Paginação */}
          <div className="pagination-bar" style={{marginBottom: '24px'}}>
            <div className="pagination-info">
              Página <strong>{data.page}</strong> de <strong>{data.total_pages}</strong>
            </div>
            <div className="pagination-controls">
              <button className="btn-page" onClick={() => fetchDocuments(data.page - 1, pageSize, storageType)} disabled={!data.has_previous}><ChevronLeft size={16} /></button>
              <button className="btn-page active">{data.page}</button>
              <button className="btn-page" onClick={() => fetchDocuments(data.page + 1, pageSize, storageType)} disabled={!data.has_next}><ChevronRight size={16} /></button>
            </div>
          </div>

          <div className="docs-grid">
            {data.items.map((doc: any) => (
              <div className="doc-card" key={doc.id}>
                <div className="doc-card-header">
                  <h4 className="doc-title">{doc.title || "Sem Nome"}</h4>
                  <span className="doc-badge" style={{background: doc.storage_type === 'CLOUD' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(251, 146, 60, 0.2)', color: doc.storage_type === 'CLOUD' ? '#38bdf8' : '#fb923c'}}>
                    {doc.file_format || "ND"}
                  </span>
                </div>

                <div className="doc-meta" style={{marginTop: '16px'}}>
                  <div className="doc-meta-item">
                    <Database size={16} /> Paciente: {doc.owner_name}
                  </div>
                  <div className="doc-meta-item">
                    <Calendar size={16} /> Data do Documento: {formatDate(doc.document_date)}
                  </div>
                  <div className="doc-meta-item">
                    {doc.storage_type === 'CLOUD' ? <Cloud size={16} color="#38bdf8"/> : <HardDrive size={16} color="#fb923c"/>} 
                    Ambiente: <strong>{doc.storage_type === 'CLOUD' ? 'AWS S3' : 'Legado Oracle'}</strong>
                  </div>
                </div>

                <div style={{ marginTop: '24px', display: 'flex', gap: '8px' }}>
                  <button 
                    className="btn-view"
                    style={{flex: 1, padding: '8px', fontSize: '14px', display: 'flex', justifyContent: 'center'}}
                    onClick={() => setModalFile({
                      url: `/api/v1/documents/${doc.id}/view`,
                      downloadUrl: `/api/v1/documents/${doc.id}/download`,
                      title: doc.title
                    })}
                  >
                    <ImageIcon size={18} />
                    Visualizar
                  </button>
                  <a 
                    href={`http://localhost:8000/api/v1/documents/${doc.id}/download`} 
                    target="_blank"
                    rel="noreferrer"
                    className="btn-primary"
                    style={{padding: '8px 16px', background: 'rgba(255,255,255,0.1)', color: 'white'}}
                    title="Baixar Original"
                  >
                    <Download size={18} />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
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
