import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BUCKET_DEFAULT = "mlops-lab-wine-quality-bignoht"
PREFIX_DEFAULT = "mlflow"
MLRUNS_DIR = PROJECT_ROOT / "mlruns"


def upload_directory(local_dir: Path, bucket: str, prefix: str, dry_run: bool = False):
    """Upload tất cả files trong local_dir lên s3://bucket/prefix/..."""
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        print("❌ boto3 not installed. Run: pip install boto3")
        sys.exit(1)

    try:
        s3 = boto3.client("s3")
        # Verify credentials & bucket access
        s3.head_bucket(Bucket=bucket)
    except Exception as e:
        print(f"❌ S3 access error: {e}")
        print("   Đảm bảo AWS credentials được cấu hình (aws configure hoặc env vars)")
        sys.exit(1)

    files = list(local_dir.rglob("*"))
    files = [f for f in files if f.is_file()]
    print(f"\n📦 Found {len(files)} files to upload from {local_dir}")
    print(f"   → s3://{bucket}/{prefix}/\n")

    uploaded = 0
    errors = 0

    for local_file in files:
        rel_path = local_file.relative_to(local_dir)
        s3_key = f"{prefix}/{rel_path}".replace("\\", "/")

        if dry_run:
            print(f"   [DRY-RUN] {s3_key}")
            uploaded += 1
            continue

        try:
            s3.upload_file(str(local_file), bucket, s3_key)
            print(f"   ✅ {s3_key}")
            uploaded += 1
        except Exception as e:
            print(f"   ❌ {s3_key}: {e}")
            errors += 1

    print(f"\n{'='*50}")
    if dry_run:
        print(f"🔍 Dry run: {uploaded} files would be uploaded")
    else:
        print(f"✅ Uploaded: {uploaded}  |  ❌ Errors: {errors}")
        if uploaded > 0:
            print(f"\n🔗 S3 URI: s3://{bucket}/{prefix}/")
            print(f"   Browse: https://s3.console.aws.amazon.com/s3/buckets/{bucket}?prefix={prefix}/")


def main(args):
    mlruns_path = Path(args.mlruns_dir)
    if not mlruns_path.exists():
        print(f"❌ mlruns directory not found: {mlruns_path}")
        print("   Chạy 'make mlflow-experiment' trước để tạo experiments.")
        sys.exit(1)

    upload_directory(
        local_dir=mlruns_path,
        bucket=args.bucket,
        prefix=args.prefix,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload MLflow artifacts to S3")
    parser.add_argument("--bucket", default=BUCKET_DEFAULT, help="S3 bucket name")
    parser.add_argument("--prefix", default=PREFIX_DEFAULT, help="S3 key prefix")
    parser.add_argument(
        "--mlruns-dir", default=str(MLRUNS_DIR),
        help="Local mlruns directory to upload"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List files without uploading"
    )
    args = parser.parse_args()
    main(args)
