terraform {
  backend "s3" {
    bucket         = "20231021-terraform-state-lock"
    key            = "terraform/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-lock-table"
  }
}