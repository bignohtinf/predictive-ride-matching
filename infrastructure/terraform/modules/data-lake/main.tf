data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "data" {
  bucket = "${var.project}-data-${var.env}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Enabled"
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

resource "aws_s3_bucket" "models" {
  bucket = "${var.project}-models-${var.env}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_glue_catalog_database" "this" {
  name = "${var.project}_${var.env}_crp_db"
}

resource "aws_iam_role" "glue_crawler" {
  name = "${var.project}-${var.env}-glue-crawler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "glue.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "glue_crawler_s3" {
  name = "${var.project}-${var.env}-glue-crawler-s3-policy"
  role = aws_iam_role.glue_crawler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["glue:*"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_glue_crawler" "raw" {
  name          = "${var.project}-${var.env}-raw-crawler"
  role          = aws_iam_role.glue_crawler.arn
  database_name = aws_glue_catalog_database.this.name

  s3_target {
    path = "s3://${aws_s3_bucket.data.bucket}/raw/"
  }

  schedule = "cron(0 */6 * * ? *)"
}
