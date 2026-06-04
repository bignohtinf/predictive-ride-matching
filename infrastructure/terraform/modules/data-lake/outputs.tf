output "data_bucket_name" { 
    value = aws_s3_bucket.data.bucket 
}

output "model_bucket_name" { 
    value = aws_s3_bucket.models.bucket 
}

output "glue_database_name" { 
    value = aws_glue_catalog_database.this.name 
}

output "glue_crawler_name" { 
    value = aws_glue_crawler.raw.name 
}
