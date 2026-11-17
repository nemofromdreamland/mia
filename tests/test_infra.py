"""Static checks on the Terraform code in `infra/` (task 4.1). Regex over HCL text, no AWS call."""

import re
from pathlib import Path

import pytest

from mia import repo_dynamo

INFRA = Path(__file__).resolve().parent.parent / "infra"


def read_infra() -> str:
    """All `infra/*.tf` files, concatenated."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(INFRA.glob("*.tf")))


def resource_block(kind: str, name: str) -> str:
    """Text of `resource "<kind>" "<name>" { ... }` (braces balanced)."""
    text = read_infra()
    match = re.search(rf'resource\s+"{kind}"\s+"{name}"\s*\{{', text)
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
