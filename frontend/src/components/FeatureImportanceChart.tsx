import { forwardRef } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type Row = { feature: string; importance: number }

type Props = {
  data: Row[]
  title: string
}

const FeatureImportanceChart = forwardRef<HTMLDivElement, Props>(({ data, title }, ref) => (
  <div ref={ref} className="rounded bg-white p-2">
    <p className="mb-2 text-xs font-semibold">{title}</p>
    <div className="h-56">
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="feature" hide />
          <YAxis />
          <Tooltip />
          <Bar dataKey="importance" fill="#4f46e5" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>
))

FeatureImportanceChart.displayName = 'FeatureImportanceChart'
export default FeatureImportanceChart
