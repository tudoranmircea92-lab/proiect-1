import { forwardRef } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type Row = { series: string; before: number; after: number; goal: number }

type Props = {
  data: Row[]
  showBefore?: boolean
  showAfter?: boolean
  showGoal?: boolean
}

const ColorProfileChart = forwardRef<HTMLDivElement, Props>(({ data, showBefore = true, showAfter = true, showGoal = true }, ref) => (
  <div ref={ref} className="rounded bg-white p-2">
    <p className="mb-2 text-xs font-semibold">Color Profile Pre vs Post</p>
    <div className="h-64">
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="series" />
          <YAxis />
          <Tooltip />
          <Legend />
          {showBefore && <Line dataKey="before" stroke="#334155" />}
          {showAfter && <Line dataKey="after" stroke="#4f46e5" />}
          {showGoal && <Line dataKey="goal" stroke="#16a34a" />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  </div>
))

ColorProfileChart.displayName = 'ColorProfileChart'
export default ColorProfileChart
