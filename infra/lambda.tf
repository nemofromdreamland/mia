# Lambda proxy (task 3.11 code). Build the zip first: uv run python scripts/build_proxy.py

resource "aws_cloudwatch_log_group" "proxy" {
  name              = "/aws/lambda/mia-proxy"
  retention_in_days = 7
}

resource "aws_lambda_function" "proxy" {
  function_name    = "mia-proxy"
  role             = aws_iam_role.proxy.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "proxy.handler.lambda_handler"
  timeout          = 30
  memory_size      = 256
  filename         = "${path.module}/../build/proxy.zip"
  source_code_hash = filebase64sha256("${path.module}/../build/proxy.zip")

  environment {
    variables = {
      AGENT_RUNTIME_ARN       = var.agent_runtime_arn
      AGENT_RUNTIME_QUALIFIER = "DEFAULT"
    }
  }

  depends_on = [aws_cloudwatch_log_group.proxy]
}
