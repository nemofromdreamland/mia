# Placeholders only: the owner writes the real keys in the console/CLI and
# Terraform never reads them back (ignore_changes). Default aws/ssm KMS key (no cost).
resource "aws_ssm_parameter" "secrets" {
  for_each = toset(["GEMINI_API_KEY", "GROQ_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"])

  name  = "/mia/${each.key}"
  type  = "SecureString"
  value = "definir-no-console"

  lifecycle {
    ignore_changes = [value]
  }
}
