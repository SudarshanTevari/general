resource "aws_s3_bucket" "application_log" {
  bucket = "20231103-application-data"
}

resource "aws_s3_bucket_versioning" "application_log" {
  bucket = aws_s3_bucket.application_log.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "application_log" {
  bucket = aws_s3_bucket.application_log.id

  rule {
    id      = "DeleteCveJsonDbLogsAfter2Days"
    status = "Enabled"

    filter {
      prefix = "app_log/cve_json_db_script_log/"
    }

    expiration {
      days = 2
    }
  }

  rule {
    id      = "DeleteDownloadCveJsonLogsAfter2Days"
    status = "Enabled"

    filter {
      prefix = "app_log/download_cve_json_script_log/"
    }

    expiration {
      days = 2
    }
  }
}