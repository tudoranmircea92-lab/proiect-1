import React from 'react'
import { Bar } from 'react-chartjs-2'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'
ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

export default function FeatureImportanceChart({ data, title = 'Feature Importance' }) {
  if (!data?.length) return null
  const chartData = {
    labels: data.map((x) => x.feature || x.compartment),
    datasets: [{ label: title, data: data.map((x) => x.importance), backgroundColor: 'rgba(75, 192, 192, 0.35)', borderColor: 'rgba(75, 192, 192, 1)', borderWidth: 1 }],
  }
  return <Bar data={chartData} options={{ responsive: true, plugins: { legend: { display: true } } }} />
}
