export type TrainRun = {
  run_id: string
  product_name: string
  model_type: string
  metrics: {
    mae?: Record<string, number>
    rmse?: Record<string, number>
    mae_avg?: number
    rmse_avg?: number
    delta_e?: number
  }
  included_features: string[]
  excluded_features: string[]
}

export type ScanSummary = {
  rows: number
  columns: string[]
  products: string[]
  detected_targets: string[]
  compartments: string[]
  selected_files?: string[]
  resolved_paths?: string[]
  status?: string
  message?: string
  has_product_name?: boolean
  missing_product_name_message?: string
  recommended_columns?: string[]
  preview_rows?: Record<string, string | number>[]
  summary_stats?: Record<string, { mean: number; std: number; min: number; max: number }>
  chart_data?: {
    feature_importance: { feature: string; importance: number; group?: string; compartment?: string }[]
    importance_by_compartment?: { compartment: string; importance: number }[]
    total_controllable_share?: number
    total_context_share?: number
    metrics: { name: string; mae: number; rmse: number; deltaE: number }[]
  }
}

export type ImportanceResponse = {
  by_feature: { feature: string; importance: number }[]
  by_compartment: { compartment: string; importance: number }[]
  share: { controllable: number; context: number }
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
