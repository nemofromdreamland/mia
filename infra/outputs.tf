output "tables" {
  description = "DynamoDB table names."
  value       = [aws_dynamodb_table.sessions.name, aws_dynamodb_table.turns.name, aws_dynamodb_table.meta.name]
}

output "data_bucket" {
  description = "MIA_DATA_BUCKET for the container."
  value       = aws_s3_bucket.data.bucket
}

output "ecr_repository_url" {
  description = "Where scripts/push_image.sh pushes the backend image."
  value       = aws_ecr_repository.backend.repository_url
}

output "runtime_role_arn" {
  description = "Execution role of the AgentCore runtime (task 4.5)."
  value       = aws_iam_role.runtime.arn
}

output "proxy_role_arn" {
  description = "Execution role of the Lambda proxy (task 4.2)."
  value       = aws_iam_role.proxy.arn
}

output "api_url" {
  description = "Public API base URL (VITE_API_BASE_URL for the frontend, task 4.6)."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "guardrail" {
  description = "Guardrail id/version (must match config/guardrails.yaml)."
  value = {
    id      = aws_bedrock_guardrail.robustness.guardrail_id
    version = aws_bedrock_guardrail_version.robustness.version
  }
}

output "agent_runtime_arn" {
  description = "AgentCore runtime the proxy invokes."
  value       = aws_bedrockagentcore_agent_runtime.backend.agent_runtime_arn
}
