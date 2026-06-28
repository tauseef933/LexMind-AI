import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, FileText, Loader2, X } from 'lucide-react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface DocumentViewerProps {
  caseId: string
  filename: string
  page: number
  onClose: () => void
}

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

export default function DocumentViewer({ caseId, filename, page, onClose }: DocumentViewerProps) {
  const [currentPage, setCurrentPage] = useState(page)
  const [numPages, setNumPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [pageWidth, setPageWidth] = useState(480)

  const encodedName = encodeURIComponent(filename)
  const fileUrl = `${BASE_URL}/uploads/${encodeURIComponent(caseId)}/${encodedName}`
  const isPdf = filename.toLowerCase().endsWith('.pdf')

  useEffect(() => {
    setCurrentPage(page)
    setLoading(true)
    setError(null)
  }, [page, filename])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => {
      setPageWidth(Math.max(280, entry.contentRect.width - 32))
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <div className="flex flex-col h-full w-full bg-slate-50">
      <div className="shrink-0 flex items-center gap-3 px-4 py-3 border-b border-slate-200 bg-white">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#1F3D6E]/10">
          <FileText className="h-4 w-4 text-[#1F3D6E]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900 truncate">{filename}</p>
          <p className="text-xs text-slate-500">
            {isPdf && numPages > 0 ? `Page ${currentPage} of ${numPages}` : `Page ${currentPage}`}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          aria-label="Close document viewer"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {isPdf && (
        <div className="shrink-0 flex items-center justify-center gap-4 px-4 py-2 border-b border-slate-200 bg-white">
          <button
            type="button"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
            className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm font-medium text-slate-700 tabular-nums min-w-[100px] text-center">
            Page {currentPage}{numPages > 0 ? ` / ${numPages}` : ''}
          </span>
          <button
            type="button"
            onClick={() => setCurrentPage((p) => (numPages ? Math.min(numPages, p + 1) : p + 1))}
            disabled={numPages > 0 && currentPage >= numPages}
            className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30 transition-colors"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}

      <div ref={containerRef} className="flex-1 overflow-auto p-4">
        {isPdf ? (
          <div className="flex justify-center">
            {loading && (
              <div className="flex items-center gap-2 text-sm text-slate-500 py-12">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading document…
              </div>
            )}
            {error && (
              <p className="text-sm text-red-600 py-8 text-center">{error}</p>
            )}
            <Document
              file={fileUrl}
              loading={null}
              onLoadSuccess={({ numPages: total }) => {
                setNumPages(total)
                setLoading(false)
                setError(null)
              }}
              onLoadError={(err) => {
                setLoading(false)
                setError(err.message || 'Failed to load PDF')
              }}
              className={loading ? 'hidden' : undefined}
            >
              <Page
                key={currentPage}
                pageNumber={currentPage}
                width={pageWidth}
                renderTextLayer
                renderAnnotationLayer
                className="shadow-lg rounded-sm overflow-hidden"
              />
            </Document>
          </div>
        ) : (
          <iframe
            src={fileUrl}
            title={filename}
            className="w-full h-full min-h-[500px] border-0 rounded-lg shadow-sm bg-white"
          />
        )}
      </div>
    </div>
  )
}
