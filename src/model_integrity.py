import hashlib
import re
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Calculate SHA256 without loading the entire file into memory."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def verify_model_integrity(
    model_path: str | Path,
    expected_hash_path: str | Path,
) -> str:
    """Verify model SHA256 against a separately stored trusted reference."""
    model = Path(model_path)
    hash_file = Path(expected_hash_path)

    if not model.is_file():
        raise FileNotFoundError(f"Model file is missing: {model}")

    if not hash_file.is_file():
        raise FileNotFoundError(
            f"Model reference hash is missing: {hash_file}"
        )

    reference_content = hash_file.read_text(encoding="utf-8").strip()
    expected_hash = reference_content.split()[0] if reference_content else ""

    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
        raise ValueError("Invalid model SHA256 reference")

    actual_hash = sha256_file(model)

    if actual_hash.lower() != expected_hash.lower():
        raise ValueError("Model SHA256 mismatch")

    return actual_hash
