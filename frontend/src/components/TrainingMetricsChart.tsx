import { forwardRef } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type MetricRow = { name: string; mae: number; rmse: number; deltaE: number }

type Props = {
  data: MetricRow[]
}

const TrainingMetricsChart = forwardRef<HTMLDivElement, Props>(({ data }, ref) => (
  <div ref={ref} className="rounded bg-white p-2">
    <p className="mb-2 text-xs font-semibold">Training Metrics (horizontal bars)</p>
    <div className="h-56">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis type="category" dataKey="name" width={90} />
          <Tooltip />
          <Legend />
          <Bar dataKey="mae" fill="#0ea5e9" />
          <Bar dataKey="rmse" fill="#f97316" />
          <Bar dataKey="deltaE" fill="#16a34a" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>
))

TrainingMetricsChart.displayName = 'TrainingMetricsChart'
export default TrainingMetricsChart
