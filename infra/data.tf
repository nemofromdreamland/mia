# ---------- DynamoDB (Backend Schema: "DynamoDB") ----------

resource "aws_dynamodb_table" "sessions" {
  name         = "mia-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "visitor_id"
  range_key    = "session_id"

  attribute {
    name = "visitor_id"
    type = "S"
  }

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "case_id"
    type = "S"
  }

  attribute {
    name = "ended_at"
    type = "S"
  }

  # ALL: list_completed turns GSI items straight into Session (spec 4.1, Decisões).
  global_secondary_index {
    name            = "by_case"
    projection_type = "ALL"

    key_schema {
      attribute_name = "case_id"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "ended_at"
      key_type       = "RANGE"
    }
  }
}

resource "aws_dynamodb_table" "turns" {
  name         = "mia-turns"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "turn_no"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "turn_no"
    type = "N"
  }
}

resource "aws_dynamodb_table" "meta" {
  name         = "mia-meta"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}

# ---------- S3 data bucket (Backend Schema: "S3") ----------

resource "aws_s3_bucket" "data" {
  bucket = "mia-data-${local.account_id}"
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "expire-sessions"
    status = "Enabled"

    filter {
      prefix = "sessions/"
    }

    expiration {
      days = 30
    }
  }
}

data "aws_iam_policy_document" "data_bucket" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.data.arn,
      "${aws_s3_bucket.data.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "data" {
  bucket     = aws_s3_bucket.data.id
  policy     = data.aws_iam_policy_document.data_bucket.json
  depends_on = [aws_s3_bucket_public_access_block.data]
}
