import { X, Loader2, Download } from 'lucide-react';
import { useState } from 'react';

interface ImageViewerProps {
  url: string | null;
  downloadUrl: string | null;
  title: string;
  onClose: () => void;
}

export function ImageViewer({ url, downloadUrl, title, onClose }: ImageViewerProps) {
  const [loading, setLoading] = useState(true);

  if (!url) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 style={{ fontSize: '1.2rem', fontWeight: 600, color: '#e6edf3', margin: 0 }}>
            Visualizando: {title}
          </h3>
          <div style={{ display: 'flex', gap: '8px' }}>
            {downloadUrl && (
              <a 
                href={downloadUrl} 
                download 
                className="btn-view" 
                style={{ padding: '8px', width: 'auto' }}
                title="Fazer Download Original"
              >
                <Download size={20} />
              </a>
            )}
            <button className="btn-close" onClick={onClose} title="Fechar (Esc)">
              <X size={24} />
            </button>
          </div>
        </div>
        
        <div className="modal-body">
          {loading && (
            <div style={{ position: 'absolute' }} className="loader-container">
              <Loader2 className="spinner" size={40} />
              <p>Carregando conversão da imagem pelo servidor...</p>
            </div>
          )}
          
          <img 
            src={url} 
            alt={title} 
            className="modal-image" 
            style={{ opacity: loading ? 0 : 1, transition: 'opacity 0.3s' }}
            onLoad={() => setLoading(false)}
            onError={(e) => {
              setLoading(false);
              (e.target as HTMLImageElement).style.display = 'none';
              // Mensagem de erro visual
              const div = document.createElement('div');
              div.className = 'error-msg';
              div.innerText = 'Falha ao carregar a imagem. Verifique o console ou a API.';
              e.currentTarget.parentElement?.appendChild(div);
            }}
          />
        </div>
      </div>
    </div>
  );
}
