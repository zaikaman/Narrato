from dotenv import load_dotenv
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'speechify-api-sdk-python', 'src'))
import requests
import uuid
import base64
import json
import time

load_dotenv()

# Shov.com configuration
SHOV_API_KEY = os.getenv("SHOV_API_KEY")
PROJECT_NAME = os.getenv("SHOV_PROJECT", "narrato")
SHOV_API_URL = f"https://shov.com/api"

def _shov_request_with_retry(url, headers, json_data=None, max_retries=3, delay=1):
    """Wrapper for requests.post with retry logic for connection errors."""
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=json_data)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, ConnectionResetError) as e:
            print(f"--- Shov Request --- WARN: Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt + 1 == max_retries:
                raise  # Re-raise the last exception
            time.sleep(delay)

def shov_set(key, value):
    """Store a key-value pair in the shov.com database."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"key": key, "value": value}
    try:
        response = _shov_request_with_retry(f"{SHOV_API_URL}/set/{PROJECT_NAME}", headers=headers, json_data=data)
        return response.json()
    except (requests.exceptions.RequestException, ConnectionResetError) as e:
        print(f"--- Shov Set --- FATAL: RequestException: {e}")
        return {"success": False, "error": "RequestException", "details": str(e)}
    except json.JSONDecodeError:
        return {"success": False, "error": "JSONDecodeError", "details": "API returned success status but response was not valid JSON."}

def shov_get(key):
    """Retrieve a key-value pair from the shov.com database."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"key": key}
    try:
        response = _shov_request_with_retry(f"{SHOV_API_URL}/get/{PROJECT_NAME}", headers=headers, json_data=data)
        return response.json()
    except (requests.exceptions.RequestException, ConnectionResetError) as e:
        print(f"--- Shov Get --- FATAL: RequestException: {e}")
        return {"success": False, "error": "RequestException", "details": str(e)}
    except json.JSONDecodeError:
        return {"success": False, "error": "JSONDecodeError", "details": "API returned success status but response was not valid JSON."}

def shov_contents():
    """List all items in the shov.com project."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
    }
    try:
        response = _shov_request_with_retry(f"{SHOV_API_URL}/contents/{PROJECT_NAME}", headers=headers)
        return response.json()
    except (requests.exceptions.RequestException, ConnectionResetError) as e:
        print(f"--- Shov Contents --- FATAL: RequestException: {e}")
        return {"success": False, "error": "RequestException", "details": str(e)}

def shov_add(collection_name, value):
    """Add a JSON object to a collection."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"name": collection_name, "value": value}
    print(f"--- Shov Add --- PRE-REQUEST: Adding to collection '{collection_name}'")
    try:
        response = _shov_request_with_retry(f"{SHOV_API_URL}/add/{PROJECT_NAME}", headers=headers, json_data=data)
        print(f"--- Shov Add --- POST-REQUEST: Status Code: {response.status_code}, Raw Response: {response.text}")
        response_json = response.json()
        print(f"--- Shov Add --- POST-REQUEST: JSON Response: {response_json}")
        return response_json
    except (requests.exceptions.RequestException, ConnectionResetError) as e:
        print(f"--- Shov Add --- FATAL: RequestException: {e}")
        return {"success": False, "error": "RequestException", "details": str(e)}
    except json.JSONDecodeError:
        return {"success": False, "error": "JSONDecodeError", "details": "API returned success status but response was not valid JSON."}

def shov_where(collection_name, filter_dict=None):
    """Filter items in a collection based on JSON properties."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"name": collection_name}
    if filter_dict:
        data['filter'] = filter_dict
    
    try:
        response = _shov_request_with_retry(f"{SHOV_API_URL}/where/{PROJECT_NAME}", headers=headers, json_data=data)
        result = response.json()
        print(f"--- Shov Where --- INFO: Result: {result}")
        return result
    except (requests.exceptions.RequestException, ConnectionResetError) as e:
        print(f"--- Shov Where --- FATAL: RequestException: {e}")
        return {"success": False, "error": "RequestException", "details": str(e), "items": []}
    except json.JSONDecodeError:
        print(f"--- Shov Where --- FATAL: JSONDecodeError")
        return {"success": False, "error": "JSONDecodeError", "details": "API returned success status but response was not valid JSON.", "items": []}

def shov_send_otp(email):
    """Send OTP to the user's email."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"identifier": email}
    try:
        response = _shov_request_with_retry(f"{SHOV_API_URL}/send-otp/{PROJECT_NAME}", headers=headers, json_data=data)
        print(f"shov_send_otp response: {response.json()}")
        return response.json()
    except (requests.exceptions.RequestException, ConnectionResetError) as e:
        print(f"--- Shov Send OTP --- FATAL: {e}")
        return {"success": False, "error": str(e)}

def shov_verify_otp(email, pin):
    """Verify the OTP provided by the user."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"identifier": email, "pin": pin}
    try:
        response = _shov_request_with_retry(f"{SHOV_API_URL}/verify-otp/{PROJECT_NAME}", headers=headers, json_data=data)
        return response.json()
    except (requests.exceptions.RequestException, ConnectionResetError) as e:
        print(f"--- Shov Verify OTP --- FATAL: {e}")
        return {"success": False, "error": str(e)}

def shov_remove(collection_name, item_id):
    """Remove an item from a collection by its ID, with robust error handling."""
    try:
        headers = {
            "Authorization": f"Bearer {SHOV_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {"collection": collection_name}
        print(f"--- Shov Remove --- PRE-REQUEST: Deleting {item_id} from {collection_name}")
        response = _shov_request_with_retry(f"{SHOV_API_URL}/remove/{PROJECT_NAME}/{item_id}", headers=headers, json_data=data)
        
        print(f"--- Shov Remove --- POST-REQUEST: Status Code: {response.status_code}")
        print(f"--- Shov Remove --- POST-REQUEST: Raw Response Text: {response.text[:500]}")

        if 200 <= response.status_code < 300:
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"success": False, "error": "JSONDecodeError", "details": "API returned success status but response was not valid JSON."}
        else:
            return {"success": False, "error": f"API returned status {response.status_code}", "details": response.text[:500]}

    except (requests.exceptions.RequestException, ConnectionResetError) as e:
        print(f"--- Shov Remove --- FATAL: RequestException: {e}")
        return {"success": False, "error": "RequestException", "details": str(e)}
    except Exception as e:
        print(f"--- Shov Remove --- FATAL: Unexpected error in shov_remove: {e}")
        return {"success": False, "error": "Unexpected error", "details": str(e)}

def shov_forget(key):
    """Permanently delete a key-value pair."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"key": key}
    try:
        response = _shov_request_with_retry(f"{SHOV_API_URL}/forget/{PROJECT_NAME}", headers=headers, json_data=data)
        return response.json()
    except (requests.exceptions.RequestException, ConnectionResetError) as e:
        print(f"--- Shov Forget --- FATAL: {e}")
        return {"success": False, "error": str(e)}

def shov_update(collection_name, item_id, value):
    """Update an item in a collection by its ID."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"collection": collection_name, "value": value}
    try:
        response = requests.post(f"{SHOV_API_URL}/update/{PROJECT_NAME}/{item_id}", headers=headers, json=data)
        response_json = response.json()
        return response_json
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": "RequestException", "details": str(e)}
    except json.JSONDecodeError:
        return {"success": False, "error": "JSONDecodeError", "details": "API returned success status but response was not valid JSON."}
