import { Card, Input, Select } from './ui'
import { useDataset } from '../lib/datasetContext'

export function GlobalFilterBar() {
  const { products, thicknesses, globalFilters, setGlobalFilters } = useDataset()

  const toggle = (list: string[], val: string) => (list.includes(val) ? list.filter((x) => x !== val) : [...list, val])

  return (
    <Card className="space-y-3">
      <h3 className="text-sm font-medium tracking-tight">Global filter</h3>
      <div className="grid md:grid-cols-4 gap-3">
        <div>
          <label className="text-xs text-slate-600">Products (multi-select)</label>
          <Select value="" onChange={(e: any) => e.target.value && setGlobalFilters({ ...globalFilters, products: toggle(globalFilters.products, e.target.value) })}>
            <option value="">All products</option>
            {products.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </Select>
          {!!globalFilters.products.length && <p className="text-xs mt-1 text-blue-700">{globalFilters.products.join(', ')}</p>}
        </div>
        <div>
          <label className="text-xs text-slate-600">Thickness (optional)</label>
          <Select value="" onChange={(e: any) => e.target.value && setGlobalFilters({ ...globalFilters, thicknesses: toggle(globalFilters.thicknesses, e.target.value) })}>
            <option value="">All thicknesses</option>
            {thicknesses.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </Select>
          {!!globalFilters.thicknesses.length && <p className="text-xs mt-1 text-blue-700">{globalFilters.thicknesses.join(', ')}</p>}
        </div>
        <div>
          <label className="text-xs text-slate-600">Date from</label>
          <Input type="date" value={globalFilters.dateFrom} onChange={(e: any) => setGlobalFilters({ ...globalFilters, dateFrom: e.target.value })} />
        </div>
        <div>
          <label className="text-xs text-slate-600">Date to</label>
          <Input type="date" value={globalFilters.dateTo} onChange={(e: any) => setGlobalFilters({ ...globalFilters, dateTo: e.target.value })} />
        </div>
      </div>
    </Card>
  )
}
