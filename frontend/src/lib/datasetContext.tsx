import { createContext, useContext, useMemo, useState } from 'react'

type DatasetCtx = {
  datasetId: string
  setDatasetId: (v: string) => void
  datasetPath: string
  setDatasetPath: (v: string) => void
  datasetSummary: { rows: number; columns: number } | null
  setDatasetSummary: (v: { rows: number; columns: number } | null) => void
  modelTrained: boolean
  setModelTrained: (v: boolean) => void
}

const Ctx = createContext<DatasetCtx | null>(null)

export function DatasetProvider({ children }: { children: React.ReactNode }) {
  const [datasetId, setDatasetId] = useState('')
  const [datasetPath, setDatasetPath] = useState('')
  const [datasetSummary, setDatasetSummary] = useState<{ rows: number; columns: number } | null>(null)
  const [modelTrained, setModelTrained] = useState(false)
  const value = useMemo(() => ({ datasetId, setDatasetId, datasetPath, setDatasetPath, datasetSummary, setDatasetSummary, modelTrained, setModelTrained }), [datasetId, datasetPath, datasetSummary, modelTrained])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useDataset() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useDataset must be used within DatasetProvider')
  return c
}
