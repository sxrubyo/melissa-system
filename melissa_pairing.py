import os
import json
import time
import secrets
import re
from typing import List, Dict, Optional, Tuple, Any

# Configuration constants
PAIRING_CODE_LENGTH = 8
PAIRING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAIRING_PENDING_TTL = 3600  # 1 hour in seconds
PAIRING_PENDING_MAX = 3

# Base directory for storing pairing data
# Ensures it respects user's home directory and creates the structure if it doesn't exist
MELISSA_PAIRING_BASE_DIR = os.path.join(os.path.expanduser("~"), ".melissa", "pairing")

# Ensure the base directory exists
os.makedirs(MELISSA_PAIRING_BASE_DIR, exist_ok=True)

def _now_iso() -> str:
    """Returns the current time in ISO format."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _load_json(path: str, fallback: Any = None) -> Any:
    """Loads JSON data from a file, returns fallback if file not found or invalid."""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Basic validation for structure if fallback is provided
                if fallback is not None and isinstance(data, dict) and "version" not in data:
                    return fallback
                return data
        else:
            return fallback
    except (json.JSONDecodeError, OSError):
        return fallback

def _save_json(path: str, data: Any) -> None:
    """Saves data to a JSON file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        print(f"Error saving JSON to {path}: {e}") # Basic logging

def _generate_code() -> str:
    """Generates a random pairing code."""
    return ''.join(secrets.choice(PAIRING_CODE_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))

def _get_channel_paths(channel: str) -> Tuple[str, str]:
    """Returns the file paths for pairing requests and allow list for a given channel."""
    channel_safe = re.sub(r'[\\/:*?"<>|]', '_', channel.lower()) # Sanitize channel name for filename
    pairing_path = os.path.join(MELISSA_PAIRING_BASE_DIR, f"{channel_safe}-pairing.json")
    allow_path = os.path.join(MELISSA_PAIRING_BASE_DIR, f"{channel_safe}-allowFrom.json")
    return pairing_path, allow_path

def load_pending(channel: str) -> List[Dict]:
    """Loads pending pairing requests for a channel."""
    path, _ = _get_channel_paths(channel)
    fallback = {"version": 1, "requests": []}
    data = _load_json(path, fallback)
    # Ensure requests are loaded and pruned for expiry
    now = time.time()
    loaded_requests = data.get("requests", [])
    active_requests = [req for req in loaded_requests if now - int(req.get("timestamp", 0)) < PAIRING_PENDING_TTL]
    if len(active_requests) != len(loaded_requests):
        _save_json(path, {"version": 1, "requests": active_requests}) # Save pruned list
    return active_requests

def save_pending(channel: str, requests: List[Dict]) -> None:
    """Saves pending pairing requests for a channel."""
    path, _ = _get_channel_paths(channel)
    _save_json(path, {"version": 1, "requests": requests})

def load_allow(channel: str) -> List[str]:
    """Loads the allow list for a channel."""
    _, path = _get_channel_paths(channel)
    fallback = {"version": 1, "allowed_chat_ids": []}
    data = _load_json(path, fallback)
    return data.get("allowed_chat_ids", [])

def save_allow(channel: str, allowed_chat_ids: List[str]) -> None:
    """Saves the allow list for a channel."""
    _, path = _get_channel_paths(channel)
    _save_json(path, {"version": 1, "allowed_chat_ids": allowed_chat_ids})

def generate_code_for_chat(chat_id: str, channel: str) -> str:
    """
    Generates a pairing code for a chat_id if not already pending or allowed.
    Returns the code and updates the pending requests.
    """
    pending_requests = load_pending(channel)
    allowed_ids = load_allow(channel)

    # Check if already allowed
    if chat_id in allowed_ids:
        return "already_paired" # Special indicator

    # Check if already has a pending request
    for req in pending_requests:
        if req.get("chat_id") == chat_id:
            # Return existing code if not expired
            if time.time() - req.get("timestamp", 0) < PAIRING_PENDING_TTL:
                return req.get("code")
            else:
                break # Expired, will be removed

    # Prune expired requests before adding a new one
    now = time.time()
    active_pending = [req for req in pending_requests if now - req.get("timestamp", 0) < PAIRING_PENDING_TTL]

    # Check if limit is reached
    if len(active_pending) >= PAIRING_PENDING_MAX:
        # Remove oldest to make space, if allowed by logic (or return error/indicator)
        # Simple approach: return error/indicator that limit reached
        return "limit_reached"

    code = _generate_code()
    new_request = {
        "chat_id": chat_id,
        "code": code,
        "timestamp": int(now),
        "channel": channel,
    }
    active_pending.append(new_request)
    save_pending(channel, active_pending)
    return code

def list_pending(channel: str) -> List[Dict]:
    """Returns all active pending pairing requests for a channel."""
    return load_pending(channel)

def approve_code(code: str, channel: str, chat_id: Optional[str] = None) -> bool:
    """
    Approves a pairing code. Adds chat_id to allow list and removes the request.
    Returns True if successful, False otherwise.
    """
    pending_requests = load_pending(channel)
    allowed_ids = load_allow(channel)
    
    original_request = None
    new_pending_requests = []
    for req in pending_requests:
        if req.get("code") == code:
            original_request = req
            # Don't add this request to the new list (effectively removing it)
        else:
            new_pending_requests.append(req)

    if original_request:
        # Add the chat_id to the allow list if provided and not already there
        request_chat_id = original_request.get("chat_id")
        target_chat_id = chat_id or request_chat_id # Use provided chat_id if available, else from request

        if target_chat_id and target_chat_id not in allowed_ids:
            allowed_ids.append(target_chat_id)
            save_allow(channel, allowed_ids)
        
        save_pending(channel, new_pending_requests)
        return True
    return False

def is_paired(chat_id: str, channel: str) -> bool:
    """Checks if a chat_id is in the allow list for a channel."""
    allowed_ids = load_allow(channel)
    return chat_id in allowed_ids

def ensure_pairing_for_chat(chat_id: str, channel: str) -> str:
    """
    Ensures a chat_id is either paired or has an active pending request.
    Returns the pairing code if a new one was generated, 'already_paired' if already allowed,
    or 'limit_reached' if max pending requests are active.
    """
    if is_paired(chat_id, channel):
        return "already_paired"
    else:
        return generate_code_for_chat(chat_id, channel)

# Example usage (for testing, not part of the main module export)
if __name__ == "__main__":
    # Example for Telegram channel
    TEST_CHANNEL = "telegram"
    TEST_CHAT_ID_1 = "123456789"
    TEST_CHAT_ID_2 = "987654321"
    TEST_CHAT_ID_3 = "111111111"
    TEST_CHAT_ID_4 = "222222222"

    print(f"--- Testing Pairing Module for Channel: {TEST_CHANNEL} ---")

    # Generate code for chat 1
    code1 = ensure_pairing_for_chat(TEST_CHAT_ID_1, TEST_CHANNEL)
    print(f"Ensure pairing for {TEST_CHAT_ID_1}: {code1}")

    # Generate code for chat 2
    code2 = ensure_pairing_for_chat(TEST_CHAT_ID_2, TEST_CHANNEL)
    print(f"Ensure pairing for {TEST_CHAT_ID_2}: {code2}")

    # Generate code for chat 3
    code3 = ensure_pairing_for_chat(TEST_CHAT_ID_3, TEST_CHANNEL)
    print(f"Ensure pairing for {TEST_CHAT_ID_3}: {code3}")

    # Try to generate code for chat 4 (should hit limit if MAX is 3)
    code4_limit = ensure_pairing_for_chat(TEST_CHAT_ID_4, TEST_CHANNEL)
    print(f"Ensure pairing for {TEST_CHAT_ID_4} (expect limit): {code4_limit}")

    # List pending
    pending = list_pending(TEST_CHANNEL)
    print(f"Pending requests: {pending}")

    # Approve code for chat 1
    print(f"\nApproving code {code1} for {TEST_CHAT_ID_1}...")
    success_approve1 = approve_code(code1, TEST_CHANNEL, TEST_CHAT_ID_1)
    print(f"Approval successful: {success_approve1}")

    # Check if chat 1 is now paired
    print(f"Is {TEST_CHAT_ID_1} paired? {is_paired(TEST_CHAT_ID_1, TEST_CHANNEL)}")
    print(f"Is {TEST_CHAT_ID_2} paired? {is_paired(TEST_CHAT_ID_2, TEST_CHANNEL)}")

    # List pending again (should be less)
    pending_after_approve = list_pending(TEST_CHANNEL)
    print(f"Pending requests after approve: {pending_after_approve}")

    # Try to approve a non-existent or already approved code
    print("\nApproving non-existent code 'ABCDEFGH'...")
    fail_approve = approve_code("ABCDEFGH", TEST_CHANNEL)
    print(f"Approval successful: {fail_approve}")
    
    print(f"\nApproving {code2} again for {TEST_CHAT_ID_2}...")
    success_approve2 = approve_code(code2, TEST_CHANNEL, TEST_CHAT_ID_2)
    print(f"Approval successful: {success_approve2}")

    # Test ensure_pairing for already paired chat
    print(f"\nEnsure pairing for {TEST_CHAT_ID_1} (already paired):")
    code_already = ensure_pairing_for_chat(TEST_CHAT_ID_1, TEST_CHANNEL)
    print(f"Result: {code_already}")

    print("\n--- Test Cleanup ---")
    # Clean up created files
    try:
        os.remove(os.path.join(MELISSA_PAIRING_BASE_DIR, f"{TEST_CHANNEL}-pairing.json"))
        os.remove(os.path.join(MELISSA_PAIRING_BASE_DIR, f"{TEST_CHANNEL}-allowFrom.json"))
        print("Cleanup successful.")
    except OSError as e:
        print(f"Cleanup failed: {e}")
    finally:
        # Remove base dir if empty
        try:
            if not os.listdir(MELISSA_PAIRING_BASE_DIR):
                os.rmdir(MELISSA_PAIRING_BASE_DIR)
        except OSError:
            pass
