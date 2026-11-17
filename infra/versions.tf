terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # State local (task 4.1): terraform.tfstate stays on the owner's machine, git-ignored.
  backend "local" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project = "mia"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}
