/**
 * Validation for ML Studio Modeler nodes and pipeline.
 */

import type { Node, Edge } from "@xyflow/react"

export interface ValidationError {
  field: string
  message: string
  messageKo: string
}

// ── Node-level validation ─────────────────────────────────

export function validateNode(nodeType: string, config: Record<string, any>): ValidationError[] {
  const errors: ValidationError[] = []
  const req = (field: string, en: string, ko: string) => {
    if (!config[field] && config[field] !== 0 && config[field] !== false)
      errors.push({ field, message: en, messageKo: ko })
  }
  const range = (field: string, min: number, max: number, en: string, ko: string) => {
    const v = config[field]
    if (v != null && (v < min || v > max))
      errors.push({ field, message: en, messageKo: ko })
  }

  switch (nodeType) {
    // ── Source ──
    case "source_csv":
      req("bucket", "Bucket is required", "버킷은 필수입니다")
      req("path", "File path is required", "파일 경로는 필수입니다")
      if (config.path && !/\.(csv|tsv)$/i.test(config.path))
        errors.push({ field: "path", message: "Must be a .csv or .tsv file", messageKo: ".csv 또는 .tsv 파일이어야 합니다" })
      break
    case "source_parquet":
      req("bucket", "Bucket is required", "버킷은 필수입니다")
      req("path", "File path is required", "파일 경로는 필수입니다")
      if (config.path && !/\.parquet$/i.test(config.path))
        errors.push({ field: "path", message: "Must be a .parquet file", messageKo: ".parquet 파일이어야 합니다" })
      break
    case "source_database":
      req("query", "SQL query is required", "SQL 쿼리는 필수입니다")
      req("connection", "Database connection is required", "데이터베이스 연결은 필수입니다")
      if (config.query) {
        const upper = config.query.toUpperCase().trim()
        if (!upper.startsWith("SELECT"))
          errors.push({ field: "query", message: "Query must start with SELECT", messageKo: "쿼리는 SELECT로 시작해야 합니다" })
        if (/\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)\b/.test(upper))
          errors.push({ field: "query", message: "Dangerous SQL keywords detected", messageKo: "위험한 SQL 키워드가 감지되었습니다" })
      }
      break

    // ── Transform ──
    case "transform_fillnull":
      if (config.strategy === "constant" && !config.constant_value && config.constant_value !== 0)
        errors.push({ field: "constant_value", message: "Fill value is required when strategy is constant", messageKo: "strategy가 constant일 때 채울 값은 필수입니다" })
      break
    case "transform_drop_cols":
      req("columns", "At least one column name is required", "컬럼 이름을 1개 이상 입력하세요")
      break
    case "transform_typecast": {
      const casts = config.casts || []
      if (casts.length === 0)
        errors.push({ field: "casts", message: "At least one type cast is required", messageKo: "타입 변환을 1개 이상 추가하세요" })
      casts.forEach((c: any, i: number) => {
        if (!c.column) errors.push({ field: `casts_${i}_column`, message: `Cast ${i + 1}: column name required`, messageKo: `Cast ${i + 1}: 컬럼 이름 필수` })
      })
      break
    }
    case "transform_outlier":
      range("threshold", 0.1, 10, "Threshold must be 0.1~10", "임계값은 0.1~10이어야 합니다")
      break
    case "transform_datetime":
      req("column", "Datetime column is required", "datetime 컬럼은 필수입니다")
      if (!config.extract || config.extract.length === 0)
        errors.push({ field: "extract", message: "Select at least one component to extract", messageKo: "추출할 구성 요소를 1개 이상 선택하세요" })
      break
    case "transform_binning":
      req("column", "Column name is required", "컬럼 이름은 필수입니다")
      range("bins", 2, 100, "Bins must be 2~100", "구간 수는 2~100이어야 합니다")
      if (config.labels) {
        const labelCount = config.labels.split(",").filter((s: string) => s.trim()).length
        if (labelCount > 0 && labelCount !== (config.bins || 5))
          errors.push({ field: "labels", message: `Label count (${labelCount}) must match bin count (${config.bins || 5})`, messageKo: `라벨 수(${labelCount})가 구간 수(${config.bins || 5})와 일치해야 합니다` })
      }
      break
    case "transform_sample":
      range("n_rows", 100, 10000000, "Row count must be 100~10,000,000", "행 수는 100~10,000,000이어야 합니다")
      break
    case "transform_sort":
      req("column", "Sort column is required", "정렬 컬럼은 필수입니다")
      break
    case "transform_encode":
      if (config.method === "ordinal" && !config.ordinal_order)
        errors.push({ field: "ordinal_order", message: "Ordinal order is required (e.g., low, medium, high)", messageKo: "순서 지정이 필수입니다 (예: low, medium, high)" })
      break
    case "transform_scale":
      if (config.method === "minmax" && config.range_min >= config.range_max)
        errors.push({ field: "range_min", message: "Min must be less than Max", messageKo: "Min은 Max보다 작아야 합니다" })
      break
    case "transform_filter": {
      const conds = config.conditions || []
      if (conds.length === 0)
        errors.push({ field: "conditions", message: "At least one condition is required", messageKo: "조건을 1개 이상 추가하세요" })
      conds.forEach((c: any, i: number) => {
        if (!c.column) errors.push({ field: `cond_${i}_column`, message: `Condition ${i + 1}: column required`, messageKo: `조건 ${i + 1}: 컬럼 필수` })
        if (c.operator !== "not_null" && !c.value && c.value !== 0)
          errors.push({ field: `cond_${i}_value`, message: `Condition ${i + 1}: value required`, messageKo: `조건 ${i + 1}: 값 필수` })
      })
      break
    }
    case "transform_feature": {
      const feats = config.features || []
      if (feats.length === 0)
        errors.push({ field: "features", message: "At least one feature is required", messageKo: "피처를 1개 이상 추가하세요" })
      feats.forEach((f: any, i: number) => {
        if (!f.name) errors.push({ field: `feat_${i}_name`, message: `Feature ${i + 1}: name required`, messageKo: `피처 ${i + 1}: 이름 필수` })
        if (f.name && !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(f.name))
          errors.push({ field: `feat_${i}_name`, message: `Feature ${i + 1}: invalid name (use letters, numbers, _)`, messageKo: `피처 ${i + 1}: 잘못된 이름 (영문, 숫자, _ 사용)` })
        if (!f.expression) errors.push({ field: `feat_${i}_expr`, message: `Feature ${i + 1}: expression required`, messageKo: `피처 ${i + 1}: 표현식 필수` })
      })
      break
    }
    case "transform_split":
      req("target_column", "Target column is required", "타겟 컬럼은 필수입니다")
      range("test_size", 0.05, 0.5, "Test size must be 0.05~0.5", "테스트 크기는 0.05~0.5이어야 합니다")
      break

    // ── Model ──
    case "model_xgboost":
      range("n_estimators", 10, 10000, "n_estimators must be 10~10,000", "n_estimators는 10~10,000이어야 합니다")
      range("max_depth", 1, 30, "max_depth must be 1~30", "max_depth는 1~30이어야 합니다")
      range("learning_rate", 0.001, 1.0, "learning_rate must be 0.001~1.0", "learning_rate는 0.001~1.0이어야 합니다")
      break
    case "model_lightgbm":
      range("n_estimators", 10, 10000, "n_estimators must be 10~10,000", "n_estimators는 10~10,000이어야 합니다")
      if (config.max_depth !== -1 && config.max_depth != null)
        range("max_depth", 1, 30, "max_depth must be -1 or 1~30", "max_depth는 -1 또는 1~30이어야 합니다")
      range("learning_rate", 0.001, 1.0, "learning_rate must be 0.001~1.0", "learning_rate는 0.001~1.0이어야 합니다")
      break
    case "model_rf":
      range("n_estimators", 10, 5000, "n_estimators must be 10~5,000", "n_estimators는 10~5,000이어야 합니다")
      if (config.max_depth != null)
        range("max_depth", 1, 50, "max_depth must be 1~50 or null", "max_depth는 1~50 또는 null이어야 합니다")
      break
    case "model_linear":
      range("max_iter", 50, 10000, "max_iter must be 50~10,000", "max_iter는 50~10,000이어야 합니다")
      break
    case "model_automl":
      range("time_limit", 60, 7200, "Time limit must be 60~7,200 seconds", "시간 제한은 60~7,200초여야 합니다")
      break

    // ── Output ──
    case "output_mlflow":
      req("experiment_name", "Experiment name is required", "실험 이름은 필수입니다")
      if (config.experiment_name && !/^[a-zA-Z0-9_-]+$/.test(config.experiment_name))
        errors.push({ field: "experiment_name", message: "Use only letters, numbers, hyphens, underscores", messageKo: "영문, 숫자, 하이픈, 언더스코어만 사용하세요" })
      break
    case "output_evaluate":
      if (!config.metrics || (Array.isArray(config.metrics) && config.metrics.length === 0))
        errors.push({ field: "metrics", message: "At least one metric is required", messageKo: "메트릭을 1개 이상 선택하세요" })
      break
    case "output_kserve":
      req("cpu", "CPU allocation is required", "CPU 할당은 필수입니다")
      req("memory", "Memory allocation is required", "메모리 할당은 필수입니다")
      break
    case "output_csv":
    case "output_csv":
      req("bucket", "Bucket is required", "버킷은 필수입니다")
      req("filename", "Filename is required", "파일명은 필수입니다")
      if (config.filename && !/\.csv$/i.test(config.filename))
        errors.push({ field: "filename", message: "Filename must end with .csv", messageKo: "파일명은 .csv로 끝나야 합니다" })
  }

  return errors
}

// ── Pipeline-level validation ─────────────────────────────

export interface PipelineError {
  nodeId?: string
  message: string
  messageKo: string
}

function getNodeCategory(nodeType: string): string {
  if (nodeType.startsWith("source_")) return "source"
  if (nodeType.startsWith("transform_")) return "transform"
  if (nodeType.startsWith("model_")) return "model"
  if (nodeType.startsWith("output_")) return "output"
  return ""
}

export function validatePipeline(nodes: Node[], edges: Edge[]): PipelineError[] {
  const errors: PipelineError[] = []

  if (nodes.length === 0) {
    errors.push({ message: "Pipeline is empty. Add at least one node.", messageKo: "파이프라인이 비어있습니다. 노드를 추가하세요." })
    return errors
  }

  // 1. Must have at least one Source
  const sources = nodes.filter((n) => getNodeCategory((n.data as any).nodeType) === "source")
  if (sources.length === 0)
    errors.push({ message: "Pipeline must have at least one Source node", messageKo: "파이프라인에 Source 노드가 1개 이상 필요합니다" })

  // 2. Check for isolated nodes (no edges)
  const connectedIds = new Set<string>()
  edges.forEach((e) => { connectedIds.add(e.source); connectedIds.add(e.target) })
  nodes.forEach((n) => {
    if (!connectedIds.has(n.id) && nodes.length > 1)
      errors.push({ nodeId: n.id, message: `"${(n.data as any).label}" is not connected`, messageKo: `"${(n.data as any).label}"이(가) 연결되지 않았습니다` })
  })

  // 3. Check for cycles (simple DFS)
  const adj = new Map<string, string[]>()
  nodes.forEach((n) => adj.set(n.id, []))
  edges.forEach((e) => adj.get(e.source)?.push(e.target))
  const visited = new Set<string>()
  const inStack = new Set<string>()
  let hasCycle = false
  function dfs(id: string) {
    if (inStack.has(id)) { hasCycle = true; return }
    if (visited.has(id)) return
    visited.add(id)
    inStack.add(id)
    for (const next of adj.get(id) || []) dfs(next)
    inStack.delete(id)
  }
  nodes.forEach((n) => { if (!visited.has(n.id)) dfs(n.id) })
  if (hasCycle)
    errors.push({ message: "Pipeline contains a cycle (circular connection)", messageKo: "파이프라인에 순환 연결이 있습니다" })

  // 4. Check Split → no Transform after
  const splitNodes = nodes.filter((n) => (n.data as any).nodeType === "transform_split")
  for (const split of splitNodes) {
    const targets = edges.filter((e) => e.source === split.id).map((e) => e.target)
    for (const tid of targets) {
      const targetNode = nodes.find((n) => n.id === tid)
      if (targetNode && getNodeCategory((targetNode.data as any).nodeType) === "transform")
        errors.push({ nodeId: tid, message: "No Transform after Split (causes data leakage)", messageKo: "Split 이후에 Transform을 추가하지 마세요 (데이터 누수)" })
    }
  }

  // 5. Node-level validation
  for (const node of nodes) {
    const nodeErrors = validateNode((node.data as any).nodeType, (node.data as any).config || {})
    for (const err of nodeErrors) {
      errors.push({ nodeId: node.id, message: `${(node.data as any).label}: ${err.message}`, messageKo: `${(node.data as any).label}: ${err.messageKo}` })
    }
  }

  return errors
}
