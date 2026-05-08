import { useState } from 'react'
import { DocumentSearch } from './presentation/components/DocumentSearch'
import { DocumentUpload } from './presentation/components/DocumentUpload'

type Tab = 'search' | 'upload'

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('search')

  return (
    <div className="app-root">
      <nav className="app-nav">
        <button
          className={`nav-tab ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
        >
          🔍 Buscar Documentos
        </button>
        <button
          className={`nav-tab ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          📄 Incluir Digitalização
        </button>
      </nav>

      {activeTab === 'search' && <DocumentSearch />}
      {activeTab === 'upload' && <DocumentUpload />}
    </div>
  )
}

export default App
