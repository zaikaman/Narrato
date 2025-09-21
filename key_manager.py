import os
import asyncio
import re

class APIKeyManager:
    """Manages and rotates API keys"""
    def __init__(self, keys):
        self.keys = [key for key in keys if key] # Filter out empty keys
        if not self.keys:
            raise ValueError("APIKeyManager initialized with no keys.")
        self.current_key_index = 0
        self.key_usage = {key: 0 for key in self.keys}
        self._lock = asyncio.Lock()
    
    async def get_next_key(self):
        """Gets the next API key in a round-robin fashion"""
        async with self._lock:
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            key = self.keys[self.current_key_index]
            self.key_usage[key] += 1
            return key
    
    def get_current_key(self):
        """Gets the current API key"""
        return self.keys[self.current_key_index]
    
    async def get_least_used_key(self):
        """Gets the least-used API key"""
        async with self._lock:
            key = min(self.key_usage.items(), key=lambda x: x[1])[0]
            self.key_usage[key] += 1
            return key

# Initialize Google API key manager
google_keys = sorted([v for k, v in os.environ.items() if k.startswith('GOOGLE_API_KEY')])
api_key_manager = APIKeyManager(google_keys)

# Initialize Speechify API key manager
speechify_keys = sorted([v for k, v in os.environ.items() if k.startswith('SPEECHIFY_KEY')])
speechify_api_key_manager = APIKeyManager(speechify_keys)

# Initialize Hugging Face API key manager
keys_with_indices = []
for k, v in os.environ.items():
    if k.startswith('HUGGING_FACE_TOKEN'):
        if k == 'HUGGING_FACE_TOKEN':
            keys_with_indices.append((1, v))
        else:
            match = re.search(r'_(\d+)$', k)
            if match:
                keys_with_indices.append((int(match.group(1)), v))
keys_with_indices.sort(key=lambda x: x[0])
huggingface_keys = [v for i, v in keys_with_indices]
huggingface_api_key_manager = APIKeyManager(huggingface_keys)
