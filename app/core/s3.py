import boto3
import io
from uuid import uuid4
from fastapi import UploadFile
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

async def upload_image_to_s3(file: UploadFile, folder: str = "contracts") -> str:
    """
    Asinxron S3 yuklash — 'seek of closed file' xatosiz ishlaydi.
    Faylni .read() orqali xotiraga o'qiydi va yopiq fayllarda ham ishlaydi.
    """
    if not file:
        return None

    try:
        # Fayl kontentini o'qib olamiz
        content = await file.read()
        buffer = io.BytesIO(content)

        # Fayl nomi
        extension = file.filename.split('.')[-1]
        key = f"{folder}/{uuid4()}.{extension}"

        # Yuklash
        s3.upload_fileobj(
            Fileobj=buffer,
            Bucket=AWS_BUCKET_NAME,
            Key=key,
            ExtraArgs={"ContentType": file.content_type}
        )

        return f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"

    except Exception as e:
        raise Exception(f"S3 upload error: {e}")


def upload_pdf_to_s3(pdf_file_path: str, contract_number: str, folder: str = "contract-pdfs") -> str:
    """
    Upload PDF file to S3 from local file path.

    Args:
        pdf_file_path: Local file system path to PDF
        contract_number: Contract number for filename (e.g., N12017)
        folder: S3 folder name

    Returns:
        S3 URL of uploaded PDF
    """
    try:
        # Read PDF file
        with open(pdf_file_path, 'rb') as f:
            pdf_content = f.read()

        buffer = io.BytesIO(pdf_content)

        # Create unique key
        key = f"{folder}/{contract_number}_{uuid4()}.pdf"

        # Upload to S3
        s3.upload_fileobj(
            Fileobj=buffer,
            Bucket=AWS_BUCKET_NAME,
            Key=key,
            ExtraArgs={"ContentType": "application/pdf"}
        )

        return f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"

    except Exception as e:
        raise Exception(f"PDF S3 upload error: {e}")
