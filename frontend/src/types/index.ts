export type TrainRun = {
  run_id: string
  product_name: string
  model_type: string
  metrics: Record<string, unknown>
  included_features: string[]
  excluded_features: string[]
}

export type RegistryRun = {
  run_id: string
  product_name: string
  model_type: string
  metrics: Record<string, unknown>
  created_at: string
  is_active: boolean
}

export type OptimizeResult = {
  model_run_id: string
  product_name: string
  selected_compartments: { compartment: string; score: number }[]
  recommendation: Record<string, number>
  deltas: Record<string, number>
  before_color: Record<string, number>
  predicted_color: Record<string, number>
  score: number
  changed_keys: string[]
  created_at: string
}
