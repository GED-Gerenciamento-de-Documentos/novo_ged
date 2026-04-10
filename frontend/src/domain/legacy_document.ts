export interface LegacyDocument {
  row_id: string;
  patient_id: number;
  nome_arquivo: string;
  formato: string;
  drive: string;
  view_url: string;
  download_url: string;
  thumbnail_url: string;
  metadata: Record<string, any>;
}

export interface PatientDocumentResponse {
  patient_id: number;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: LegacyDocument[];
}
