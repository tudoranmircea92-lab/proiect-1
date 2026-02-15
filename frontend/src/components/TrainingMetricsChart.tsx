import { forwardRef } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type MetricRow = { name: string; mae: number; rmse: number; deltaE: number }

type Props = {
  data: MetricRow[]
}

const TrainingMetricsChart = forwardRef<HTMLDivElement, Props>(({ data }, ref) => (
  <div ref={ref} className="rounded bg-white p-2">
    <p className="mb-2 text-xs font-semibold">Training Metrics Trend</p>
    <div className="h-56">
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line dataKey="mae" stroke="#0ea5e9" />
          <Line dataKey="rmse" stroke="#f97316" />
          <Line dataKey="deltaE" stroke="#16a34a" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  </div>
))

TrainingMetricsChart.displayName = 'TrainingMetricsChart'
export default TrainingMetricsChart
