# Public edge (TRD, "Infraestrutura"): HTTP API -> Lambda proxy, with throttling.

resource "aws_apigatewayv2_api" "http" {
  name          = "mia-api"
  protocol_type = "HTTP"

  # CORS only for the CloudFront domain (TRD, "Borda pública").
  cors_configuration {
    allow_origins = ["https://${aws_cloudfront_distribution.web.domain_name}"]
    allow_methods = ["GET", "POST", "DELETE"]
    allow_headers = ["content-type", "x-visitor-id"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_integration" "proxy" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.proxy.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

# One explicit route per operation (Backend Schema, "API"): unknown routes get 404
# from the API Gateway without invoking the Lambda.
resource "aws_apigatewayv2_route" "proxy" {
  for_each = toset([
    "GET /cases",
    "POST /sessions",
    "GET /sessions",
    "GET /sessions/{id}",
    "POST /sessions/{id}/start",
    "POST /sessions/{id}/turns",
    "POST /sessions/{id}/end",
    "GET /sessions/{id}/report",
    "DELETE /sessions/{id}",
    "GET /recruiter/candidates",
    "GET /recruiter/candidates/{id}",
  ])

  api_id    = aws_apigatewayv2_api.http.id
  route_key = each.value
  target    = "integrations/${aws_apigatewayv2_integration.proxy.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = 5
    throttling_burst_limit = 10
  }
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.proxy.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
