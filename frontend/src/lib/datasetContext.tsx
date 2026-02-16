import { createContext, useContext, useMemo, useState } from 'react'

type DatasetCtx = {
  datasetId: string
  setDatasetId: (v: string) => void
  datasetPath: string
  setDatasetPath: (v: string) => void
}

const Ctx = createContext<DatasetCtx | null>(null)

export function DatasetProvider({ children }: { children: React.ReactNode }) {
  const [datasetId, setDatasetId] = useState('')
  const [datasetPath, setDatasetPath] = useState('')
  const value = useMemo(() => ({ datasetId, setDatasetId, datasetPath, setDatasetPath }), [datasetId, datasetPath])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useDataset() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useDataset must be used within DatasetProvider')
  return c
}
