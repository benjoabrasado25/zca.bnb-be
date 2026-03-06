"""
Services for user-related operations including R2 storage for guest IDs.
Guest IDs are stored in a PRIVATE R2 bucket and accessed via proxy endpoint.
"""

import logging
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


def get_r2_ids_client():
    """
    Get boto3 client for the private R2 bucket (guest IDs).
    Uses separate credentials from the public media bucket.
    """
    return boto3.client(
        's3',
        endpoint_url=settings.R2_IDS_ENDPOINT_URL,
        aws_access_key_id=settings.R2_IDS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_IDS_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto',
    )


def generate_upload_url(user_id: int, filename: str, content_type: str = 'image/jpeg'):
    """
    Generate a presigned URL for uploading a guest ID image.

    Args:
        user_id: The user's ID
        filename: Original filename
        content_type: MIME type of the file

    Returns:
        tuple: (presigned_url, r2_key)
    """
    client = get_r2_ids_client()

    # Generate unique key with user folder structure
    ext = filename.split('.')[-1] if '.' in filename else 'jpg'
    r2_key = f"guest-ids/{user_id}/{uuid4()}.{ext}"

    try:
        url = client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.R2_IDS_BUCKET_NAME,
                'Key': r2_key,
                'ContentType': content_type,
            },
            ExpiresIn=900,  # 15 minutes for upload
        )
        return url, r2_key
    except ClientError as e:
        logger.error(f"Failed to generate upload URL: {e}")
        raise


def get_id_image(r2_key: str):
    """
    Retrieve guest ID image from R2.
    Used by the proxy endpoint to stream image to authorized users.

    Args:
        r2_key: The R2 object key

    Returns:
        tuple: (body stream, content_type, content_length)
    """
    client = get_r2_ids_client()

    try:
        response = client.get_object(
            Bucket=settings.R2_IDS_BUCKET_NAME,
            Key=r2_key,
        )
        return (
            response['Body'],
            response.get('ContentType', 'image/jpeg'),
            response.get('ContentLength', 0),
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.warning(f"ID image not found: {r2_key}")
            return None, None, None
        logger.error(f"Failed to get ID image: {e}")
        raise


def delete_id_from_r2(r2_key: str):
    """
    Delete a guest ID image from R2.

    Args:
        r2_key: The R2 object key to delete
    """
    client = get_r2_ids_client()

    try:
        client.delete_object(
            Bucket=settings.R2_IDS_BUCKET_NAME,
            Key=r2_key,
        )
        logger.info(f"Deleted ID image: {r2_key}")
    except ClientError as e:
        logger.error(f"Failed to delete ID image: {e}")
        raise


def check_id_exists(r2_key: str) -> bool:
    """
    Check if an ID image exists in R2.

    Args:
        r2_key: The R2 object key

    Returns:
        bool: True if exists, False otherwise
    """
    client = get_r2_ids_client()

    try:
        client.head_object(
            Bucket=settings.R2_IDS_BUCKET_NAME,
            Key=r2_key,
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise
