import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DocumentUpload } from '../DocumentUpload'

// ─── Mock da API ─────────────────────────────────────────────────────────────
vi.mock('../../../infrastructure/http/documentApi', () => ({
  uploadDocument: vi.fn(),
}))

import { uploadDocument } from '../../../infrastructure/http/documentApi'
const mockUpload = vi.mocked(uploadDocument)

// ─── Helpers ──────────────────────────────────────────────────────────────────
const makePdf = (name = 'teste.pdf') =>
  new File(['%PDF-1.4 content'], name, { type: 'application/pdf' })

const makeTxt = () =>
  new File(['texto simples'], 'arquivo.txt', { type: 'text/plain' })

const makeBatchResponse = (count: number) => ({
  total_enviados: count,
  total_sucesso: count,
  total_erros: 0,
  documentos: Array.from({ length: count }, (_, i) => ({
    file: `doc${i + 1}.pdf`,
    document_id: `uuid-${i + 1}`,
    title: `Laudo (${i + 1}/${count})`,
    file_size_bytes: 1024,
    storage_path: `documentos/laudo/uuid-${i + 1}.pdf`,
    checksum_sha256: 'abc123',
  })),
  erros: [],
  message: `${count}/${count} documento(s) enviado(s) com sucesso.`,
})

async function fillForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/título base/i), 'Laudo de Teste')
  await user.selectOptions(screen.getByTestId('document-type-select'), 'LAUDO')
  await user.type(screen.getByLabelText(/nome do paciente/i), 'João Silva')
}

// ─── Tests ────────────────────────────────────────────────────────────────────
describe('DocumentUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render the upload form correctly', () => {
    render(<DocumentUpload />)

    expect(screen.getByTestId('upload-form')).toBeInTheDocument()
    expect(screen.getByTestId('drop-zone')).toBeInTheDocument()
    expect(screen.getByLabelText(/título base/i)).toBeInTheDocument()
    expect(screen.getByTestId('document-type-select')).toBeInTheDocument()
    expect(screen.getByLabelText(/nome do paciente/i)).toBeInTheDocument()
    expect(screen.getByTestId('submit-button')).toBeInTheDocument()
  })

  it('should show error when submitting without any file selected', async () => {
    const user = userEvent.setup()
    render(<DocumentUpload />)

    await fillForm(user)
    await user.click(screen.getByTestId('submit-button'))

    expect(screen.getByTestId('error-message')).toBeInTheDocument()
    expect(screen.getByTestId('error-message')).toHaveTextContent(/ao menos um arquivo/i)
  })

  it('should reject files with unsupported extensions', async () => {
    render(<DocumentUpload />)

    const input = screen.getByTestId('file-input')
    fireEvent.change(input, { target: { files: [makeTxt()] } })

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument()
    })
    expect(screen.getByTestId('error-message')).toHaveTextContent(/formato não suportado/i)
  })

  it('should show file queue when files are added', async () => {
    const user = userEvent.setup()
    render(<DocumentUpload />)

    const input = screen.getByTestId('file-input')
    await user.upload(input, [makePdf('doc1.pdf'), makePdf('doc2.pdf')])

    await waitFor(() => {
      expect(screen.getByTestId('file-queue')).toBeInTheDocument()
    })
    expect(screen.getByText('doc1.pdf')).toBeInTheDocument()
    expect(screen.getByText('doc2.pdf')).toBeInTheDocument()
  })

  it('should show success message after successful single upload', async () => {
    mockUpload.mockResolvedValueOnce(makeBatchResponse(1))

    const user = userEvent.setup()
    render(<DocumentUpload />)

    const input = screen.getByTestId('file-input')
    await user.upload(input, makePdf())
    await fillForm(user)
    await user.click(screen.getByTestId('submit-button'))

    await waitFor(() => {
      expect(screen.getByTestId('success-message')).toBeInTheDocument()
    })

    expect(mockUpload).toHaveBeenCalledOnce()
  })

  it('should show success for multiple files upload', async () => {
    mockUpload.mockResolvedValueOnce(makeBatchResponse(3))

    const user = userEvent.setup()
    render(<DocumentUpload />)

    const input = screen.getByTestId('file-input')
    await user.upload(input, [makePdf('a.pdf'), makePdf('b.pdf'), makePdf('c.pdf')])
    await fillForm(user)
    await user.click(screen.getByTestId('submit-button'))

    await waitFor(() => {
      expect(screen.getByTestId('success-message')).toBeInTheDocument()
    })

    expect(screen.getByTestId('success-message')).toHaveTextContent(/3\/3/i)
  })

  it('should show error message when API returns an error', async () => {
    mockUpload.mockRejectedValueOnce({
      response: { data: { detail: 'Arquivo corrompido.' } },
    })

    const user = userEvent.setup()
    render(<DocumentUpload />)

    const input = screen.getByTestId('file-input')
    await user.upload(input, makePdf())
    await fillForm(user)
    await user.click(screen.getByTestId('submit-button'))

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument()
    })
    expect(screen.getByTestId('error-message')).toHaveTextContent(/corrompido/i)
  })

  it('should disable submit button while uploading', async () => {
    mockUpload.mockImplementationOnce(() => new Promise(() => {}))

    const user = userEvent.setup()
    render(<DocumentUpload />)

    const input = screen.getByTestId('file-input')
    await user.upload(input, makePdf())
    await fillForm(user)
    await user.click(screen.getByTestId('submit-button'))

    expect(screen.getByTestId('submit-button')).toBeDisabled()
  })
})
