# AgentCore Runtime running the backend container (task 3.9 image, pushed by task 4.4).
# No authorizer_configuration: inbound auth is IAM (SigV4), and only the proxy may invoke.

resource "aws_bedrockagentcore_agent_runtime" "backend" {
  agent_runtime_name = "mia_backend"
  description        = "MIA backend (FastAPI, /ping + /invocations)"
  role_arn           = aws_iam_role.runtime.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.backend.repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  environment_variables = {
    MIA_STORAGE     = "aws"
    MIA_DATA_BUCKET = aws_s3_bucket.data.bucket
    AWS_REGION      = var.region
    # Owner asked for more sessions per visitor (spec 4.7a); PRD default in code is 5.
    MIA_VISITOR_DAILY_LIMIT = tostring(var.visitor_daily_limit)
    # Each RunRecord also to stdout -> CloudWatch; scripts/pull_runs.py (spec 4.7b).
    MIA_RUNS_STDOUT = "1"
  }

  depends_on = [aws_iam_role_policy.runtime]
}

resource "aws_bedrockagentcore_agent_runtime_endpoint" "live" {
  name                  = "live"
  agent_runtime_id      = aws_bedrockagentcore_agent_runtime.backend.agent_runtime_id
  agent_runtime_version = aws_bedrockagentcore_agent_runtime.backend.agent_runtime_version
}

# Resource policy: allow the proxy role, deny every other principal (even admins of the account).
data "aws_iam_policy_document" "runtime_invoke" {
  statement {
    sid       = "AllowProxy"
    effect    = "Allow"
    actions   = ["bedrock-agentcore:InvokeAgentRuntime"]
    resources = [aws_bedrockagentcore_agent_runtime.backend.agent_runtime_arn]

    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.proxy.arn]
    }
  }

  statement {
    sid       = "DenyEveryoneElse"
    effect    = "Deny"
    actions   = ["bedrock-agentcore:InvokeAgentRuntime"]
    resources = [aws_bedrockagentcore_agent_runtime.backend.agent_runtime_arn]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = [aws_iam_role.proxy.arn]
    }
  }
}

resource "aws_bedrockagentcore_resource_policy" "runtime" {
  resource_arn = aws_bedrockagentcore_agent_runtime.backend.agent_runtime_arn
  policy       = data.aws_iam_policy_document.runtime_invoke.json
}
