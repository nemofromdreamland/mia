"""Static checks on the Terraform code in `infra/` (task 4.1). Regex over HCL text, no AWS call."""

import re
from pathlib import Path

import pytest

from mia import repo_dynamo

INFRA = Path(__file__).resolve().parent.parent / "infra"


def read_infra() -> str:
    """All `infra/*.tf` files, concatenated."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(INFRA.glob("*.tf")))


def resource_block(kind: str, name: str, keyword: str = "resource") -> str:
    """Text of `<keyword> "<kind>" "<name>" { ... }` (braces balanced)."""
    text = read_infra()
    match = re.search(rf'{keyword}\s+"{kind}"\s+"{name}"\s*\{{', text)
    assert match, f"missing resource {kind}.{name}"
    depth, index = 1, match.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        index += 1
    return text[match.start() : index]


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text)


# ---------- R1: DynamoDB ----------


@pytest.mark.parametrize(
    ("resource", "table", "hash_key", "range_key"),
    [
        ("sessions", repo_dynamo.SESSIONS_TABLE, "visitor_id", "session_id"),
        ("turns", repo_dynamo.TURNS_TABLE, "session_id", "turn_no"),
        ("meta", repo_dynamo.META_TABLE, "pk", "sk"),
    ],
)
def test_tables_match_the_code(resource: str, table: str, hash_key: str, range_key: str) -> None:
    block = squash(resource_block("aws_dynamodb_table", resource))
    assert f'name = "{table}"' in block
    assert f'hash_key = "{hash_key}"' in block
    assert f'range_key = "{range_key}"' in block
    assert 'billing_mode = "PAY_PER_REQUEST"' in block


def test_turn_no_is_a_number() -> None:
    block = squash(resource_block("aws_dynamodb_table", "turns"))
    assert 'name = "turn_no" type = "N"' in block


def test_by_case_index_on_sessions() -> None:
    block = squash(resource_block("aws_dynamodb_table", "sessions"))
    assert f'name = "{repo_dynamo.BY_CASE_INDEX}"' in block
    assert 'attribute_name = "case_id" key_type = "HASH"' in block
    assert 'attribute_name = "ended_at" key_type = "RANGE"' in block
    assert 'projection_type = "ALL"' in block


def test_ttl_only_on_meta() -> None:
    assert 'attribute_name = "expires_at" enabled = true' in squash(
        resource_block("aws_dynamodb_table", "meta")
    )
    for name in ("sessions", "turns"):
        assert "ttl" not in resource_block("aws_dynamodb_table", name)


# ---------- R2: data bucket ----------


def test_data_bucket_name() -> None:
    assert "mia-data-${" in resource_block("aws_s3_bucket", "data")


def test_data_bucket_blocks_public_access() -> None:
    block = squash(resource_block("aws_s3_bucket_public_access_block", "data"))
    for flag in ("block_public_acls", "block_public_policy", "ignore_public_acls"):
        assert f"{flag} = true" in block
    assert "restrict_public_buckets = true" in block


def test_data_bucket_encryption_ownership_and_tls() -> None:
    sse = "aws_s3_bucket_server_side_encryption_configuration"
    assert '"AES256"' in resource_block(sse, "data")
    assert '"BucketOwnerEnforced"' in resource_block("aws_s3_bucket_ownership_controls", "data")
    assert "aws:SecureTransport" in read_infra()


def test_sessions_expire_in_30_days() -> None:
    block = squash(resource_block("aws_s3_bucket_lifecycle_configuration", "data"))
    assert 'prefix = "sessions/"' in block
    assert "expiration { days = 30 }" in block


# ---------- R8: nothing billed while idle, nothing forbidden in the Free Plan ----------

FORBIDDEN = (
    "aws_nat_gateway",
    "aws_lb",
    "aws_alb",
    "aws_elb",
    "aws_instance",
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_organizations_",
    "aws_controltower_",
    "aws_ssoadmin_",
    "aws_identitystore_",
)


def test_no_forbidden_resources() -> None:
    kinds = re.findall(r'resource\s+"([a-z0-9_]+)"', read_infra())
    assert kinds
    bad = [kind for kind in kinds if kind.startswith(FORBIDDEN)]
    assert bad == []


def test_no_secret_in_infra() -> None:
    texts = [
        p.read_text(encoding="utf-8") for p in INFRA.rglob("*") if p.suffix in {".tf", ".example"}
    ]
    for text in texts:
        assert not re.search(r"gsk_[A-Za-z0-9]{10}|AIza[0-9A-Za-z_-]{20}|[ps]k-lf-[0-9a-f]", text)


# ---------- R3: ECR ----------


def test_ecr_repository() -> None:
    block = squash(resource_block("aws_ecr_repository", "backend"))
    assert 'name = "mia-backend"' in block
    assert 'image_tag_mutability = "IMMUTABLE"' in block
    assert "scan_on_push = true" in block


def test_ecr_keeps_only_five_images() -> None:
    block = squash(resource_block("aws_ecr_lifecycle_policy", "backend"))
    assert "countNumber = 5" in block or '"countNumber": 5' in block


# ---------- R4: SSM ----------

SECRET_NAMES = ("GEMINI_API_KEY", "GROQ_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


def test_ssm_secure_strings_with_ignored_value() -> None:
    block = squash(resource_block("aws_ssm_parameter", "secrets"))
    for name in SECRET_NAMES:
        assert f'"{name}"' in block
    assert 'name = "/mia/${each.key}"' in block
    assert 'type = "SecureString"' in block
    assert "ignore_changes = [value]" in block


# ---------- R5, R6: IAM ----------


def test_runtime_role_trusts_only_agentcore() -> None:
    text = squash(read_infra())
    assert 'name = "mia-runtime"' in squash(resource_block("aws_iam_role", "runtime"))
    assert '"bedrock-agentcore.amazonaws.com"' in text
    assert "aws:SourceAccount" in text


def test_proxy_role_trusts_lambda_and_only_invokes_runtime() -> None:
    assert 'name = "mia-proxy"' in squash(resource_block("aws_iam_role", "proxy"))
    assert '"lambda.amazonaws.com"' in read_infra()
    assert "data.aws_iam_policy_document.proxy.json" in resource_block(
        "aws_iam_role_policy", "proxy"
    )
    proxy = squash(resource_block("aws_iam_policy_document", "proxy", keyword="data"))
    assert "bedrock-agentcore:InvokeAgentRuntime" in proxy
    assert "dynamodb:" not in proxy and "s3:" not in proxy


def test_runtime_policy_scopes() -> None:
    text = squash(read_infra())
    for action in (
        "dynamodb:GetItem",
        "dynamodb:Query",
        "s3:GetObject",
        "bedrock:InvokeModel",
        "bedrock:ApplyGuardrail",
        "ssm:GetParameter",
        "ecr:BatchGetImage",
    ):
        assert action in text
    assert '"${aws_s3_bucket.data.arn}/sessions/*"' in text


def test_no_wildcard_actions_in_iam() -> None:
    text = squash((INFRA / "iam.tf").read_text(encoding="utf-8"))
    assert not re.search(r'actions = \[[^\]]*"\*"', text)
    assert not re.search(r'actions = \[[^\]]*"(dynamodb|s3|bedrock|ssm|ecr):\*"', text)


# ---------- R7: Budget ----------


def test_budget_counts_usage_before_credits() -> None:
    block = squash(resource_block("aws_budgets_budget", "monthly"))
    assert 'budget_type = "COST"' in block and 'time_unit = "MONTHLY"' in block
    assert "include_credit = false" in block
    assert "var.budget_email" in block and "var.budget_limit_usd" in block


def test_budget_alerts() -> None:
    block = squash(resource_block("aws_budgets_budget", "monthly"))
    actual = re.findall(
        r'threshold = (\d+) threshold_type = "PERCENTAGE" notification_type = "ACTUAL"', block
    )
    forecast = re.findall(
        r'threshold = (\d+) threshold_type = "PERCENTAGE" notification_type = "FORECASTED"', block
    )
    assert sorted(map(int, actual)) == [50, 80, 100]
    assert forecast == ["100"]


def test_budget_email_has_no_default() -> None:
    match = re.search(r'variable "budget_email" \{[^}]*\}', squash(read_infra()))
    assert match
    block = match.group(0)
    assert "default" not in block and "sensitive = true" in block


# ---------- 4.2 R2: Lambda proxy ----------


def test_proxy_lambda() -> None:
    block = squash(resource_block("aws_lambda_function", "proxy"))
    for expected in (
        'function_name = "mia-proxy"',
        'runtime = "python3.12"',
        'architectures = ["arm64"]',
        'handler = "proxy.handler.lambda_handler"',
        "timeout = 30",
        "memory_size = 256",
        "role = aws_iam_role.proxy.arn",
        "AGENT_RUNTIME_ARN = var.agent_runtime_arn",
        'AGENT_RUNTIME_QUALIFIER = "DEFAULT"',
        'filebase64sha256("${path.module}/../build/proxy.zip")',
    ):
        assert expected in block


def test_proxy_log_group_keeps_7_days() -> None:
    block = squash(resource_block("aws_cloudwatch_log_group", "proxy"))
    assert 'name = "/aws/lambda/mia-proxy"' in block and "retention_in_days = 7" in block


# ---------- 4.2 R3–R5: HTTP API ----------


def handler_route_keys() -> set[str]:
    """`METHOD /path` for every proxy route, with `{id}` placeholders like the API Gateway."""
    import proxy.handler as handler

    keys = set()
    for method, pattern, _action in handler.ROUTES:
        path = pattern.pattern.strip("^$").replace("(?P<sid>[A-Za-z0-9]+)", "{id}")
        keys.add(f"{method} {path}")
    return keys


def test_routes_match_the_proxy() -> None:
    block = resource_block("aws_apigatewayv2_route", "proxy")
    declared = set(re.findall(r'"((?:GET|POST|DELETE) /[^"]*)"', read_infra()))
    assert "for_each" in block
    assert declared == handler_route_keys()
    assert len(declared) == 11


def test_integration_is_lambda_payload_2() -> None:
    block = squash(resource_block("aws_apigatewayv2_integration", "proxy"))
    assert 'integration_type = "AWS_PROXY"' in block
    assert 'payload_format_version = "2.0"' in block
    assert "aws_lambda_function.proxy.invoke_arn" in block


def test_stage_throttling() -> None:
    block = squash(resource_block("aws_apigatewayv2_stage", "default"))
    assert 'name = "$default"' in block and "auto_deploy = true" in block
    assert "throttling_rate_limit = 5" in block and "throttling_burst_limit = 10" in block


def test_cors_only_for_configured_origins() -> None:
    block = squash(resource_block("aws_apigatewayv2_api", "http"))
    assert 'protocol_type = "HTTP"' in block
    assert 'dynamic "cors_configuration"' in block
    assert "var.cors_allowed_origins" in block
    assert '"x-visitor-id"' in block and '"content-type"' in block


def test_api_gateway_may_invoke_the_lambda() -> None:
    block = squash(resource_block("aws_lambda_permission", "api"))
    assert 'principal = "apigateway.amazonaws.com"' in block
    assert "aws_apigatewayv2_api.http.execution_arn" in block


# ---------- 4.3: Bedrock Guardrail ----------


def guardrail_script():  # type: ignore[no-untyped-def]
    import importlib.util

    path = INFRA.parent / "scripts" / "create_guardrail.py"
    spec = importlib.util.spec_from_file_location("create_guardrail", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guardrail_policy_matches_the_script() -> None:
    request = guardrail_script().guardrail_request()
    block = resource_block("aws_bedrock_guardrail", "robustness")
    flat = squash(block)
    assert f'name = "{request["name"]}"' in flat
    topic = request["topicPolicyConfig"]["topicsConfig"][0]
    assert topic["name"] in block and topic["definition"] in block
    for example in topic["examples"]:
        assert example in block
    assert 'type = "PROMPT_ATTACK"' in flat and 'input_strength = "HIGH"' in flat
    for word in request["wordPolicyConfig"]["wordsConfig"]:
        assert f'"{word["text"]}"' in block
    for pii in request["sensitiveInformationPolicyConfig"]["piiEntitiesConfig"]:
        assert f'type = "{pii["type"]}" action = "{pii["action"]}"' in flat
    regex = request["sensitiveInformationPolicyConfig"]["regexesConfig"][0]
    hcl_pattern = regex["pattern"].replace("\\", "\\\\")
    assert f'pattern = "{hcl_pattern}"' in flat
    assert f'blocked_input_messaging = "{request["blockedInputMessaging"]}"' in flat


def test_guardrail_imported_from_config() -> None:
    text = squash(read_infra())
    assert 'yamldecode(file("${path.module}/../config/guardrails.yaml"))' in text
    assert "to = aws_bedrock_guardrail.robustness" in text
    assert "to = aws_bedrock_guardrail_version.robustness" in text
    assert "local.guardrail_config.robustness.id" in text
    assert "local.guardrail_config.robustness.version" in text


def test_guardrail_version_survives_destroy() -> None:
    block = squash(resource_block("aws_bedrock_guardrail_version", "robustness"))
    assert "skip_destroy = true" in block
