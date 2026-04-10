import { useState } from 'react';
import { api } from '../infrastructure/api';
import type { PatientDocumentResponse } from '../domain/legacy_document';

export function usePatientDocuments() {
  const [data, setData] = useState<PatientDocumentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPatientId, setCurrentPatientId] = useState<number | null>(null);
  const [pageSize, setPageSize] = useState(20);

  const fetchDocuments = async (patientId: number, page: number = 1, size: number = pageSize) => {
    try {
      setLoading(true);
      setError(null);
      setCurrentPatientId(patientId);
      const response = await api.get<PatientDocumentResponse>(
        `/api/v1/legacy/patients/${patientId}/documents?page=${page}&page_size=${size}`
      );
      setData(response.data);
    } catch (err: any) {
      console.error(err);
      setError(
        err.response?.data?.detail ||
        'Falha ao conectar na API. Verifique se o servidor FastAPI oficial (porta 8000) está rodando.'
      );
    } finally {
      setLoading(false);
    }
  };

  const goToPage = (page: number) => {
    if (currentPatientId !== null) {
      fetchDocuments(currentPatientId, page, pageSize);
    }
  };

  const changePageSize = (size: number) => {
    setPageSize(size);
    if (currentPatientId !== null) {
      fetchDocuments(currentPatientId, 1, size);
    }
  };

  return { data, loading, error, fetchDocuments, goToPage, pageSize, changePageSize };
}
