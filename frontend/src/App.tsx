import { useState } from 'react'
import { PatientSearch } from './presentation/components/PatientSearch'
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
          🔍 Buscar Paciente
        </button>
        <button
          className={`nav-tab ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          📄 Incluir Digitalização
        </button>
      </nav>

      {activeTab === 'search' && <PatientSearch />}
      {activeTab === 'upload' && <DocumentUpload />}
    </div>
  )
}

export default App
