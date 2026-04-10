import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface UploadDocumentPayload {
  files: File[]
  title: string
  document_type: string
  owner_name: string
  owner_record_number?: string
}

export interface UploadedDocument {
  file: string
  document_id: string
  title: string
  file_size_bytes: number
  storage_path: string
  checksum_sha256: string
}

export interface UploadError {
  file: string
  error: string
}

export interface UploadDocumentResponse {
  total_enviados: number
  total_sucesso: number
  total_erros: number
  documentos: UploadedDocument[]
  erros: UploadError[]
  message: string
  warning?: string
}

export async function uploadDocument(
  payload: UploadDocumentPayload,
  onProgress?: (percent: number) => void,
): Promise<UploadDocumentResponse> {
  const formData = new FormData()

  // Adicionar cada arquivo com o mesmo campo 'files' (List[UploadFile] no FastAPI)
  for (const file of payload.files) {
    formData.append('files', file)
  }

  formData.append('title', payload.title)
  formData.append('document_type', payload.document_type)
  formData.append('owner_name', payload.owner_name)
  if (payload.owner_record_number) {
    formData.append('owner_record_number', payload.owner_record_number)
  }

  const response = await axios.post<UploadDocumentResponse>(
    `${API_BASE}/api/v1/documents/upload-dev`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (event) => {
        if (onProgress && event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      },
    },
  )

  return response.data
}
