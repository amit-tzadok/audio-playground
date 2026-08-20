"""Bridges the local-disk pipeline (every processing module reads/writes
plain local paths — soundfile, ffmpeg, torch, etc. all expect that) to S3
for the two boundaries that cross pods in Kubernetes: the file a backend
pod saves on /upload has to reach whichever worker pod picks up the task,
and the file a worker pod produces has to reach whichever backend pod
serves the download later. Everything in between a task's start and end
stays on that pod's local disk untouched.

Inactive (falls back to plain local paths, i.e. today's docker-compose
behavior) unless S3_BUCKET is set, so local dev needs no AWS credentials.
"""
import os
from pathlib import Path
from urllib.parse import urlparse

S3_BUCKET = os.environ.get("S3_BUCKET")

_s3 = None


def _client():
    global _s3
    if _s3 is None:
        import boto3
        _s3 = boto3.client("s3")
    return _s3


def is_enabled() -> bool:
    return bool(S3_BUCKET)


def resolve_input(path: str, dest_dir: Path) -> str:
    """If path is an s3:// reference, download it to dest_dir and return
    the local path; otherwise return it unchanged."""
    if not path or not path.startswith("s3://"):
        return path
    parsed = urlparse(path)
    key = parsed.path.lstrip("/")
    local_path = Path(dest_dir) / Path(key).name
    _client().download_file(parsed.netloc, key, str(local_path))
    return str(local_path)


def finalize_path(path: str, key_prefix: str = "") -> str:
    """Upload a local path to S3 and return its s3:// reference, if S3 is
    enabled; otherwise return the local path unchanged. Already-S3 paths
    (e.g. re-returned without modification) pass through untouched."""
    if not path or not is_enabled() or path.startswith("s3://"):
        return path
    key = f"{key_prefix}{Path(path).name}"
    _client().upload_file(path, S3_BUCKET, key)
    return f"s3://{S3_BUCKET}/{key}"


def presigned_url(s3_uri: str, expires: int = 3600) -> str:
    parsed = urlparse(s3_uri)
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": parsed.netloc, "Key": parsed.path.lstrip("/")},
        ExpiresIn=expires,
    )
