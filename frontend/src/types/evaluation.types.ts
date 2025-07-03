export interface MetricEvaluation {
  score: number;
  reasoning: string;
}

export interface EvaluationMetrics {
  goal_adherence: MetricEvaluation;
  groundedness: MetricEvaluation;
  answer_relevance: MetricEvaluation;
  persona_compliance: MetricEvaluation;
  style_and_courtesy: MetricEvaluation;
  conciseness: MetricEvaluation;
  knowledge_boundary_violation: MetricEvaluation;
  security_policy_violation: MetricEvaluation;
  tool_accuracy: MetricEvaluation;
  user_sentiment: MetricEvaluation;
  [key: string]: MetricEvaluation;
}

export interface EvaluationResult {
  overall_score: number;
  metrics: EvaluationMetrics;
  reasoning: string;
  g_eval_results: any; 
  outlier_analysis: any;
}

export interface EvaluationSession {
    id: number;
    session_id: string;
    created_at: string;
    agent_id: string;
    user_query: string;
    agent_response: string | null;
    rag_context: string | null;
    agent_goal: string;
    agent_persona: string;
    user_feedback: string | null;
    feedback_sentiment: string | null;
    metric_results: {
        metric_name: string;
        score: number;
        reasoning: string;
    }[];
} 