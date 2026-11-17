variable "region" {
  description = "AWS region for every MIA resource."
  type        = string
  default     = "us-east-1"
}

variable "budget_email" {
  description = "E-mail that receives the Budget alerts (set it in terraform.tfvars, never in git)."
  type        = string
  sensitive   = true
}

variable "budget_limit_usd" {
  description = "Monthly cost budget in USD (usage before credits)."
  type        = number
  default     = 20
}

variable "bedrock_inference_profiles" {
  description = "Cross-region inference profiles the runtime may call (config/models.yaml)."
  type        = list(string)
  # Nova 2 Lite: runtime answer suggestions for follow-ups (spec 5.6), another family than the judge.
  default = ["us.anthropic.claude-haiku-4-5-20251001-v1:0", "us.amazon.nova-2-lite-v1:0"]
}

variable "bedrock_foundation_models" {
  description = "Foundation models behind those profiles (the profile routes to these regions)."
  type        = list(string)
  default     = ["anthropic.claude-haiku-4-5-20251001-v1:0", "amazon.nova-2-lite-v1:0"]
}

variable "bedrock_profile_regions" {
  description = "Regions a us.* inference profile may route to."
  type        = list(string)
  default     = ["us-east-1", "us-east-2", "us-west-2"]
}

variable "image_tag" {
  description = "Backend image tag in ECR (12-char commit hash from scripts/push_image.py)."
  type        = string
}

variable "visitor_daily_limit" {
  description = "Sessions per visitor per day (MIA_VISITOR_DAILY_LIMIT in the runtime)."
  type        = number
  default     = 20
}
