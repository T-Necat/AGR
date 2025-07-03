import { EvaluationResult } from './evaluation.types';

export interface SandboxRequest {
  agent_id: string;
  query: string;
  agent_goal: string;
  agent_persona: string;
  save_to_db?: boolean;
}

export interface SandboxResponse {
  agent_response: string;
  rag_context: string;
  tool_calls: any[] | null;
  evaluation: EvaluationResult;
  session_id: string | null;
}

export interface FeedbackRequest {
    session_id: string;
    feedback: string;
}

export interface BatchEvaluationResponse {
    task_id: string;
}

export type TaskStatus = 'PENDING' | 'PROGRESS' | 'SUCCESS' | 'FAILURE' | 'RETRY';

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  progress: number | null;
  result: any | null; // Can be more specific if result structure is known
}

export interface MetricStatistics {
    [metricName: string]: {
        average_score: number;
        count: number;
    }
} 