import { createContext, useContext, useMemo, useState } from 'react'

type GroupedColumns = Record<string, string[]>

type GlobalFilters = {
  products: string[]
  thicknesses: string[]
  dateFrom: string
  dateTo: string
}

type DatasetCtx = {
  datasetId: string
  setDatasetId: (v: string) => void
  datasetPath: string
  setDatasetPath: (v: string) => void
  datasetSummary: { rows: number; columns: number } | null
  setDatasetSummary: (v: { rows: number; columns: number } | null) => void
  datasetName: string
  setDatasetName: (v: string) => void
  groupedColumns: GroupedColumns | null
  setGroupedColumns: (v: GroupedColumns | null) => void
  products: string[]
  setProducts: (v: string[]) => void
  thicknesses: string[]
  setThicknesses: (v: string[]) => void
  globalFilters: GlobalFilters
  setGlobalFilters: (v: GlobalFilters) => void
  modelTrained: boolean
  setModelTrained: (v: boolean) => void
}

const Ctx = createContext<DatasetCtx | null>(null)

export function DatasetProvider({ children }: { children: React.ReactNode }) {
  const [datasetId, setDatasetId] = useState('')
  const [datasetPath, setDatasetPath] = useState('')
  const [datasetSummary, setDatasetSummary] = useState<{ rows: number; columns: number } | null>(null)
  const [datasetName, setDatasetName] = useState('')
  const [groupedColumns, setGroupedColumns] = useState<GroupedColumns | null>(null)
  const [products, setProducts] = useState<string[]>([])
  const [thicknesses, setThicknesses] = useState<string[]>([])
  const [globalFilters, setGlobalFilters] = useState<GlobalFilters>({ products: [], thicknesses: [], dateFrom: '', dateTo: '' })
  const [modelTrained, setModelTrained] = useState(false)
  const value = useMemo(
    () => ({ datasetId, setDatasetId, datasetPath, setDatasetPath, datasetSummary, setDatasetSummary, datasetName, setDatasetName, groupedColumns, setGroupedColumns, products, setProducts, thicknesses, setThicknesses, globalFilters, setGlobalFilters, modelTrained, setModelTrained }),
    [datasetId, datasetPath, datasetSummary, datasetName, groupedColumns, products, thicknesses, globalFilters, modelTrained]
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useDataset() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useDataset must be used within DatasetProvider')
  return c
}
