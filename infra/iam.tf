# Least privilege per component (TRD, "Segurança e LGPD").

locals {
  region_arn_prefix = "arn:aws:bedrock-agentcore:${var.region}:${local.account_id}"
}

# ---------- Runtime (AgentCore container) ----------

data "aws_iam_policy_document" "runtime_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["${local.region_arn_prefix}:*"]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name               = "mia-runtime"
  assume_role_policy = data.aws_iam_policy_document.runtime_trust.json
}

data "aws_iam_policy_document" "runtime" {
  statement {
    sid = "Tables"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchWriteItem",
    ]
    resources = flatten([
      for table in [aws_dynamodb_table.sessions, aws_dynamodb_table.turns, aws_dynamodb_table.meta] :
      [table.arn, "${table.arn}/index/*"]
    ])
  }

  statement {
    sid       = "Reports"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.data.arn}/sessions/*"]
  }

  statement {
    sid       = "ListReports"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["sessions/*"]
    }
  }

  statement {
    sid     = "Models"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = concat(
      [for id in var.bedrock_inference_profiles : "arn:aws:bedrock:${var.region}:${local.account_id}:inference-profile/${id}"],
      flatten([
        for region in var.bedrock_profile_regions : [
          for id in var.bedrock_foundation_models : "arn:aws:bedrock:${region}::foundation-model/${id}"
        ]
      ]),
    )
  }

  # Voice (spec 5): Nova 2 Sonic bidirectional streaming, us-east-1 foundation model.
  statement {
    sid       = "VoiceModel"
    actions   = ["bedrock:InvokeModelWithBidirectionalStream"]
    resources = ["arn:aws:bedrock:${var.region}::foundation-model/amazon.nova-2-sonic-v1:0"]
  }

  statement {
    sid       = "Guardrails"
    actions   = ["bedrock:ApplyGuardrail"]
    resources = ["arn:aws:bedrock:${var.region}:${local.account_id}:guardrail/*"]
  }

  statement {
    sid       = "Secrets"
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter/mia/*"]
  }

  statement {
    sid       = "PullImage"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [aws_ecr_repository.backend.arn]
  }

  statement {
    sid       = "EcrToken"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # this action has no resource-level scope
  }

  statement {
    sid = "Logs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"]
  }

  statement {
    sid       = "LogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${var.region}:${local.account_id}:log-group:*"]
  }

  statement {
    sid       = "Traces"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"] # X-Ray has no resource-level scope
  }

  statement {
    sid       = "Metrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "mia-runtime"
  role   = aws_iam_role.runtime.id
  policy = data.aws_iam_policy_document.runtime.json
}

# ---------- Proxy (Lambda behind API Gateway) ----------

data "aws_iam_policy_document" "proxy_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "proxy" {
  name               = "mia-proxy"
  assume_role_policy = data.aws_iam_policy_document.proxy_trust.json
}

data "aws_iam_policy_document" "proxy" {
  statement {
    sid = "InvokeRuntime"
    # WebSocketStream: the presigned voice URL is signed with this role (spec 5).
    actions = [
      "bedrock-agentcore:InvokeAgentRuntime",
      "bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream",
    ]
    resources = [
      aws_bedrockagentcore_agent_runtime.backend.agent_runtime_arn,
      "${aws_bedrockagentcore_agent_runtime.backend.agent_runtime_arn}/runtime-endpoint/*",
    ]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/lambda/mia-*"]
  }
}

resource "aws_iam_role_policy" "proxy" {
  name   = "mia-proxy"
  role   = aws_iam_role.proxy.id
  policy = data.aws_iam_policy_document.proxy.json
}
