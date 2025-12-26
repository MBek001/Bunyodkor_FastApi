import boto3
import io
from uuid import uuid4
from fastapi import UploadFile
from PIL import Image
import fitz  # PyMuPDF
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
    Upload image to S3 with automatic format conversion.

    Supports: JPG, JPEG, PNG, PDF
    - Images (JPG, PNG, JPEG) are uploaded as-is
    - PDFs are converted to JPG (first page only)

    Returns:
        S3 URL of uploaded file
    """
    if not file:
        return None

    try:
        # Read file content
        content = await file.read()

        # Get file extension
        extension = file.filename.split('.')[-1].lower()
        content_type = file.content_type or ""

        # Check if it's a PDF
        is_pdf = extension == "pdf" or "pdf" in content_type.lower()

        if is_pdf:
            # Convert PDF to JPG
            pdf_document = fitz.open(stream=content, filetype="pdf")

            # Get first page
            page = pdf_document[0]

            # Render page to pixmap (image)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x resolution for better quality

            # Convert pixmap to PIL Image
            img_data = pix.tobytes("jpeg")
            img = Image.open(io.BytesIO(img_data))

            # Save as JPEG to buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=95)
            buffer.seek(0)

            pdf_document.close()

            # Set extension to jpg
            extension = "jpg"
            final_content_type = "image/jpeg"

        else:
            # For regular images (JPG, PNG, JPEG), upload as-is
            buffer = io.BytesIO(content)

            # Validate it's actually an image
            try:
                img = Image.open(buffer)
                img.verify()  # Verify it's a valid image
                buffer.seek(0)  # Reset buffer position

                # Normalize extension
                if extension in ["jpg", "jpeg"]:
                    extension = "jpg"
                    final_content_type = "image/jpeg"
                elif extension == "png":
                    final_content_type = "image/png"
                else:
                    # Unsupported format
                    raise ValueError(f"Unsupported image format: {extension}. Please use JPG, PNG, or PDF.")

            except Exception as e:
                raise ValueError(f"Invalid image file: {str(e)}")

        # Create S3 key
        key = f"{folder}/{uuid4()}.{extension}"

        # Upload to S3
        s3.upload_fileobj(
            Fileobj=buffer,
            Bucket=AWS_BUCKET_NAME,
            Key=key,
            ExtraArgs={
                "ContentType": final_content_type,
            }
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

        # Upload to S3 (public-read for easy access)
        s3.upload_fileobj(
            Fileobj=buffer,
            Bucket=AWS_BUCKET_NAME,
            Key=key,
            ExtraArgs={
                "ContentType": "application/pdf",

            }
        )

        return f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"

    except Exception as e:
        raise Exception(f"PDF S3 upload error: {e}")
