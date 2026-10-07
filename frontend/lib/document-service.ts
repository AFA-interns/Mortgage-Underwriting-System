export type DocumentStatus = 'Uploaded' | 'Processing' | 'Parsed' | 'Failed' | 'Requires Review'

export type UnderwritingDocument = {
  id: string
  name: string
  type: string
  applicant: string
  format: string
  size: string
  uploadedAt: string
  status: DocumentStatus
  file?: File
  previewUrl?: string
}

export type ParsedDocument = {
  documentInformation: Array<{ label: string; value: string }>
  extractedText: string
  extractedFields: Array<{ label: string; value: string; confidence: string }>
}

export async function parseDocument(_file: File | undefined, document: UnderwritingDocument): Promise<ParsedDocument> {
  await new Promise((resolve) => setTimeout(resolve, 1200))
  return {
    documentInformation: [
      { label: 'Document type', value: document.type },
      { label: 'Document number', value: 'XXXX1234' },
      { label: 'Applicant name', value: document.applicant },
      { label: 'Date', value: '12/08/2026' },
    ],
    extractedText: `DEMO EXTRACTED TEXT\n\nThis is sample parsed content for ${document.name}.\n\nThe connected FastAPI service can replace this response with OCR output and extracted document text. No information shown here is a real underwriting result.`,
    extractedFields: [
      { label: 'Applicant Name', value: document.applicant, confidence: '98%' },
      { label: 'Document Number', value: 'XXXX1234', confidence: '96%' },
      { label: 'Date', value: '12/08/2026', confidence: '94%' },
    ],
  }
}

export const mockDocuments: UnderwritingDocument[] = []
