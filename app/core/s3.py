import boto3
from uuid import uuid4
from fastapi import UploadFile
from typing import List
from .config import settings

AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
AWS_BUCKET_NAME = settings.AWS_BUCKET_NAME
AWS_REGION = settings.AWS_REGION

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def upload_image_to_s3(file: UploadFile, folder: str = "contracts") -> str:
    """Upload image to S3 and return public URL"""
    extension = file.filename.split('.')[-1]
    key = f"{folder}/{uuid4()}.{extension}"

    s3.upload_fileobj(
        Fileobj=file.file,
        Bucket=AWS_BUCKET_NAME,
        Key=key,
        ExtraArgs={"ACL": "public-read", "ContentType": file.content_type}
    )

    return f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"
