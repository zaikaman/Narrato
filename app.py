import time

import cloudinary
import cloudinary.uploader

import inspect
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash, Response

from dotenv import load_dotenv
import os
import google.generativeai as genai
from elevenlabs.client import ElevenLabs
import json
import tempfile
import fal_client
import asyncio
from asgiref.sync import sync_to_async
import re
import traceback
import requests
import uuid

# Shov.com configuration
SHOV_API_KEY = os.getenv("SHOV_API_KEY")
PROJECT_NAME = os.getenv("SHOV_PROJECT", "narrato")
SHOV_API_URL = f"https://shov.com/api"

def shov_set(key, value):
    """Store a key-value pair in the shov.com database."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"key": key, "value": value}
    response = requests.post(f"{SHOV_API_URL}/set/{PROJECT_NAME}", headers=headers, json=data)
    return response.json()

def shov_get(key):
    """Retrieve a key-value pair from the shov.com database."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"key": key}
    response = requests.post(f"{SHOV_API_URL}/get/{PROJECT_NAME}", headers=headers, json=data)
    return response.json()

def shov_contents():
    """List all items in the shov.com project."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
    }
    response = requests.post(f"{SHOV_API_URL}/contents/{PROJECT_NAME}", headers=headers)
    return response.json()

def shov_add(collection_name, value):
    """Add a JSON object to a collection."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"name": collection_name, "value": value}
    response = requests.post(f"{SHOV_API_URL}/add/{PROJECT_NAME}", headers=headers, json=data)
    return response.json()

def shov_where(collection_name, filter_dict=None):
    """Filter items in a collection based on JSON properties."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"name": collection_name}
    if filter_dict:
        data['filter'] = filter_dict
    response = requests.post(f"{SHOV_API_URL}/where/{PROJECT_NAME}", headers=headers, json=data)
    return response.json()

def shov_send_otp(email):
    """Send OTP to the user's email."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"identifier": email}
    response = requests.post(f"{SHOV_API_URL}/send-otp/{PROJECT_NAME}", headers=headers, json=data)
    print(f"shov_send_otp response: {response.json()}")
    return response.json()

def shov_verify_otp(email, pin):
    """Verify the OTP provided by the user."""
    headers = {
        "Authorization": f"Bearer {SHOV_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"identifier": email, "pin": pin}
    response = requests.post(f"{SHOV_API_URL}/verify-otp/{PROJECT_NAME}", headers=headers, json=data)
    return response.json()

def shov_remove(collection_name, item_id):
    """Remove an item from a collection by its ID, with robust error handling."""
    try:
        headers = {
            "Authorization": f"Bearer {SHOV_API_KEY}"
        }
        data = {"collection": collection_name}
        print(f"--- Shov Remove --- PRE-REQUEST: Deleting {item_id} from {collection_name}")
        response = requests.post(f"{SHOV_API_URL}/remove/{PROJECT_NAME}/{item_id}", headers=headers, json=data)
        
        print(f"--- Shov Remove --- POST-REQUEST: Status Code: {response.status_code}")
        print(f"--- Shov Remove --- POST-REQUEST: Raw Response Text: {response.text[:500]}")

        if 200 <= response.status_code < 300:
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"success": False, "error": "JSONDecodeError", "details": "API returned success status but response was not valid JSON."}
        else:
            return {"success": False, "error": f"API returned status {response.status_code}", "details": response.text[:500]}

    except requests.exceptions.RequestException as e:
        print(f"--- Shov Remove --- FATAL: RequestException: {e}")
        return {"success": False, "error": "RequestException", "details": str(e)}
    except Exception as e:
        print(f"--- Shov Remove --- FATAL: Unexpected error in shov_remove: {e}")
        return {"success": False, "error": "Unexpected error", "details": str(e)}

class APIKeyManager:
    """Manages and rotates API keys"""
    def __init__(self):
        self.google_keys = [
            os.getenv('GOOGLE_API_KEY'),
            os.getenv('GOOGLE_API_KEY_2'),
            os.getenv('GOOGLE_API_KEY_3'),
            os.getenv('GOOGLE_API_KEY_4')
        ]
        self.current_key_index = 0
        self.key_usage = {key: 0 for key in self.google_keys}
        self._lock = asyncio.Lock()
    
    async def get_next_key(self):
        """Gets the next API key in a round-robin fashion"""
        async with self._lock:
            self.current_key_index = (self.current_key_index + 1) % len(self.google_keys)
            key = self.google_keys[self.current_key_index]
            self.key_usage[key] += 1
            return key
    
    def get_current_key(self):
        """Gets the current API key"""
        return self.google_keys[self.current_key_index]
    
    async def get_least_used_key(self):
        """Gets the least-used API key"""
        async with self._lock:
            key = min(self.key_usage.items(), key=lambda x: x[1])[0]
            self.key_usage[key] += 1
            return key

# Initialize API key manager
api_key_manager = APIKeyManager()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")
load_dotenv()

cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key = os.getenv("CLOUDINARY_KEY"),
    api_secret = os.getenv("CLOUDINARY_SECRET")
)

print(f"SHOV_API_KEY: {os.getenv('SHOV_API_KEY')}")
print(f"SHOV_PROJECT: {os.getenv('SHOV_PROJECT')}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'email' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# Configure API keys
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
FAL_KEY = os.getenv('FAL_KEY')

genai.configure(api_key=GOOGLE_API_KEY)
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
os.environ["FAL_KEY"] = FAL_KEY

async def generate_image(prompt):
    """Generate image from prompt using Runware API and upload to Cloudinary"""
    try:
        print(f"\n=== Starting generate_image with Runware ===")
        print(f"Input prompt: {prompt}")

        url = "https://api.runware.ai/v1/imageInference"
        headers = {
            "Authorization": f"Bearer {os.getenv('RUNWARE_TOKEN')}",
            "Content-Type": "application/json"
        }
        payload = [{
            "taskType": "imageInference",
            "taskUUID": str(uuid.uuid4()),
            "outputType": "URL",
            "outputFormat": "jpg",
            "positivePrompt": prompt,
            "model": "civitai:497255@552771",
            "height": 1024,
            "width": 1024,
            "steps": 30,
            "CFGScale": 7.5
        }]

        response = await sync_to_async(requests.post)(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        if data.get("data") and data["data"][0].get("imageURL"):
            image_url = data["data"][0]["imageURL"]
            
            # Download the image from the URL
            image_response = await sync_to_async(requests.get)(image_url)
            image_response.raise_for_status()

            # Upload the image to Cloudinary
            upload_result = await sync_to_async(cloudinary.uploader.upload)(image_response.content)
            cloudinary_url = upload_result.get('secure_url')

            print(f"Image uploaded to Cloudinary: {cloudinary_url}")
            print("=== Finished generate_image with Runware ===\n")
            return cloudinary_url
        else:
            print("No image data found in Runware response")
            return None

    except Exception as e:
        print(f"Error creating image with Runware: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        print("=== Finished generate_image with Runware with exception ===\n")
        return None

def find_character(name, char_db):
    """Find character information in the database
    
    Args:
        name (str): Character name to search for
        char_db (dict): Database containing character information
        
    Returns:
        tuple: (character_data, character_type) or (None, None) if not found
    """
    for char in char_db.get('main_characters', []):
        if char['name'].lower() == name.lower():
            return char, 'main'
    for char in char_db.get('supporting_characters', []):
        if char['name'].lower() == name.lower():
            return char, 'supporting'
    for group in char_db.get('groups', []):
        if group['name'].lower() == name.lower():
            return group, 'group'
    return None, None

@sync_to_async
def generate_voice(text, voice_id="pNInz6obpgDQGcFmaJgB"):
    """Generate voice from text using ElevenLabs"""
    try:
        # Create audio stream from text
        audio_stream = elevenlabs_client.text_to_speech.convert_as_stream(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2"
        )
        
        # Save audio stream to a temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        
        # Write each chunk to the file
        for chunk in audio_stream:
            if isinstance(chunk, bytes):
                temp_file.write(chunk)
        
        temp_file.close()
        return temp_file.name
    except Exception as e:
        print(f"Error creating voice: {str(e)}")
        return None

def check_paragraph_length(paragraph):
    """Check and adjust paragraph length to not exceed 30 words"""
    words = paragraph.split()
    if len(words) > 30:
        # Cut the paragraph into smaller parts of less than 30 words
        new_paragraphs = []
        current_paragraph = []
        word_count = 0
        
        for word in words:
            if word_count + 1 > 30:
                new_paragraphs.append(' '.join(current_paragraph))
                current_paragraph = [word]
                word_count = 1
            else:
                current_paragraph.append(word)
                word_count += 1
                
        if current_paragraph:
            new_paragraphs.append(' '.join(current_paragraph))
            
        return new_paragraphs
    return [paragraph]

async def generate_story_content(prompt, min_paragraphs, max_paragraphs):
    """Generate story content using Gemini"""
    try:
        print(f"\n=== Starting generate_story_content ===")
        print(f"Input prompt: {prompt}")
        
        # Get the least used API key
        api_key = await api_key_manager.get_least_used_key()
        genai.configure(api_key=api_key)
        print("Initialized Gemini model with new API key")
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        print("Sending story creation request...")
        english_story_response = model.generate_content(f"""
        You are a master storyteller writing an engaging and detailed story for a general audience. 
        Create a rich, vivid story based on this theme: {prompt}

        IMPORTANT WRITING GUIDELINES:
        1. Write detailed, descriptive paragraphs that paint a clear picture
        2. Each paragraph MUST BE 30 WORDS OR LESS
        3. Each paragraph should focus on one scene or moment
        4. Use sensory details to bring scenes to life (sights, sounds, smells, textures, etc.)
        5. Balance dialogue, action, and description
        6. Include character emotions and internal thoughts
        7. Use simple but expressive language that everyone can understand
        8. Create smooth transitions between paragraphs
        9. Maintain a steady pace - don't rush through important moments
        10. Show character development through actions and reactions
        11. Build tension and emotional investment throughout the story

        PARAGRAPH STRUCTURE:
        - Start with scene-setting details
        - Add character actions and reactions
        - Include relevant dialogue or internal thoughts
        - End with a hook to the next paragraph
        - Each paragraph should be a mini-scene that moves the story forward
        - STRICTLY KEEP EACH PARAGRAPH UNDER 30 WORDS

        Return the story in this EXACT JSON format, with NO additional text or formatting:
        {{
            "title": "Story Title",
            "paragraphs": [
                "First detailed paragraph text (under 30 words)",
                "Second detailed paragraph text (under 30 words)",
                ... (between {min_paragraphs}-{max_paragraphs} paragraphs)
            ],
            "moral": "The moral lesson from the story"
        }}

        IMPORTANT FORMAT RULES:
        - Do NOT add trailing commas after the last item in arrays or objects
        - Each paragraph must be under 30 words with rich details
        - Story should match the theme: {prompt}
        - Return ONLY the JSON object, no other text
        - Number of paragraphs should be between {min_paragraphs} and {max_paragraphs}
        - The story should feel complete, don't force it to exactly {max_paragraphs} paragraphs
        - Focus on quality and detail in each paragraph while keeping them concise
        """)
        
        print("Received response from Gemini")
        
        # Get text response and clean it up
        response_text = english_story_response.text.strip()
        print(f"Raw response: {response_text}")
        
        # Remove markdown code blocks
        response_text = re.sub(r'```(?:json)?\s*|\s*```', '', response_text)
        
        # Remove trailing comma after the last element of the array and object
        response_text = re.sub(r',(\s*[\}\]])', r'\1', response_text)
        response_text = re.sub(r',\s*"moral":', r',"moral":', response_text)
        
        # Remove extra whitespace and reformat JSON
        response_text = re.sub(r'\s+', ' ', response_text)
        print(f"Cleaned response: {response_text}")
        
        try:
            # Try parsing JSON
            print("Parsing JSON...")
            story_data = json.loads(response_text)
            print("JSON parsed successfully")
            
            # Check JSON structure
            if not all(key in story_data for key in ['title', 'paragraphs', 'moral']):
                raise ValueError("Missing required fields in story data")
            
            # Check and adjust the length of each paragraph
            adjusted_paragraphs = []
            for paragraph in story_data['paragraphs']:
                split_paragraphs = check_paragraph_length(paragraph)
                adjusted_paragraphs.extend(split_paragraphs)
            
            story_data['paragraphs'] = adjusted_paragraphs
            
            # Make sure the number of paragraphs is within the min-max range
            num_paragraphs = len(story_data['paragraphs'])
            if num_paragraphs > max_paragraphs:
                print(f"Trimming paragraphs from {num_paragraphs} to {max_paragraphs}")
                story_data['paragraphs'] = story_data['paragraphs'][:max_paragraphs]
            elif num_paragraphs < min_paragraphs:
                print(f"Adding paragraphs to reach minimum {min_paragraphs} (current: {num_paragraphs})")
                while len(story_data['paragraphs']) < min_paragraphs:
                    story_data['paragraphs'].append("And the story continues...")
            
            print(f"Final number of paragraphs: {len(story_data['paragraphs'])}")
            print("=== Finished generate_story_content successfully ===\n")
            return story_data
                
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error processing story: {str(e)}")
            print("=== Finished generate_story_content with parsing error ===\n")
            return {
                "title": "Error Creating Story",
                "paragraphs": ["We encountered an error while creating your story."] * min_paragraphs,
                "moral": "Sometimes we need to be patient and try again."
            }
    except Exception as e:
        print(f"Generate story error: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        print("=== Finished generate_story_content with exception ===\n")
        raise

async def analyze_story_characters(story_data):
    """Analyze and create consistent descriptions for all characters in the story"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        character_analysis = model.generate_content(f"""
        You are a character designer creating consistent descriptions for all characters in this story. 
        Analyze the entire story carefully and create detailed, consistent descriptions that will be used for ALL images.
        
        Title: {story_data['title']}
        Story: {' '.join(story_data['paragraphs'])}

        Requirements:
        1. Identify ALL named and unnamed but important characters
        2. Create VERY detailed descriptions that will remain consistent
        3. Include specific details about appearance, clothing, and expressions
        4. Use exact measurements and specific colors where possible
        5. Consider character development/changes throughout the story
        
        Return ONLY a JSON object in this format:
        {{
            "main_characters": [
                {{
                    "name": "Character's name or identifier",
                    "role": "Role in story",
                    "base_description": "Complete physical description to use in EVERY image",
                    "variations": [
                        {{
                            "trigger_keywords": ["sad", "crying", "upset"],
                            "expression_override": "Detailed description of sad expression and posture"
                        }},
                        {{
                            "trigger_keywords": ["happy", "joyful", "laughing"],
                            "expression_override": "Detailed description of happy expression and posture"
                        }}
                    ],
                    "relationships": ["Relationship with other characters"],
                    "development_points": [
                        {{
                            "story_point": "Key story event",
                            "appearance_change": "How appearance changes after this point"
                        }}
                    ]
                }}
            ],
            "supporting_characters": [
                // Same structure as main characters
            ],
            "groups": [
                {{
                    "name": "Group identifier",
                    "members_description": "Consistent description for group members",
                    "variations": []
                }}
            ]
        }}
        """)
        
        try:
            char_text = character_analysis.text.strip()
            char_text = re.sub(r'```(?:json)?\s*|\s*```', '', char_text)
            print(f"Character analysis response: {char_text}")
            
            char_data = json.loads(char_text)
            if not (char_data.get('main_characters') or char_data.get('supporting_characters')):
                raise ValueError("Missing character data in response")
                
            # Add to story_data
            story_data['character_database'] = char_data
            print("Successfully created character database")
            return char_data
            
        except Exception as e:
            print(f"Could not parse character analysis: {str(e)}")
            print(f"Raw response: {character_analysis.text}")
            return None
            
    except Exception as e:
        print(f"Error in analyze_story_characters: {str(e)}")
        return None

async def generate_image_prompt(paragraph, story_data=None, paragraph_index=0, previous_prompts=None):
    """Create a prompt for the image using Gemini, with character information to keep it consistent"""
    try:
        # Get the next API key in a round-robin fashion
        api_key = await api_key_manager.get_next_key()
        genai.configure(api_key=api_key)
        print(f"Using new API key for generate_image_prompt")
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Get prompt history from story_data
        previous_prompts = story_data.get('previous_prompts', []) if story_data else []
        
        # Create context from prompt history
        prompt_history_context = ""
        if previous_prompts:
            prompt_history_context = f"""
            Previous image prompts for consistency (numbered in sequence):
            {chr(10).join(f'{i+1}. {prompt}' for i, prompt in enumerate(previous_prompts))}
            """

        # Analyze the paragraph to identify which characters appear
        character_mention_analysis = model.generate_content(f"""
        Analyze this paragraph and identify which characters appear in it.
        Also identify their emotional state or any significant changes in appearance.
        
        Paragraph: "{paragraph}"

        Return ONLY a JSON object in this format:
        {{
            "characters": [
                {{
                    "name": "Character name or identifier",
                    "emotional_state": ["happy", "excited"],
                    "appearance_change": "Any story-driven changes to note"
                }}
            ]
        }}
        """ )
        
        try:
            char_mentions = json.loads(character_mention_analysis.text)
            mentioned_chars = char_mentions.get('characters', [])
        except:
            mentioned_chars = []

        # Get character information from the character_database
        character_descriptions = []
        char_db = story_data.get('character_database', {})
        
        # Build a character description based on emotional state and changes
        for mention in mentioned_chars:
            char_name = mention.get('name')
            char_data, char_type = find_character(char_name, char_db)
            
            if char_data:
                description = char_data.get('base_description', '')
                
                # Add an expression based on the emotional state
                emotions = mention.get('emotional_state', [])
                for variation in char_data.get('variations', []):
                    if any(emotion in variation['trigger_keywords'] for emotion in emotions):
                        description = f"{description}, {variation['expression_override']}"
                
                # Add appearance changes if any
                appearance_change = mention.get('appearance_change')
                if appearance_change:
                    for dev_point in char_data.get('development_points', []):
                        if appearance_change.lower() in dev_point['story_point'].lower():
                            description = f"{description}, {dev_point['appearance_change']}"
                
                character_descriptions.append(description)

        character_context = "Character descriptions (MUST be followed exactly):\n" + "\n\n".join(character_descriptions) if character_descriptions else ""

        style_data = story_data.get('style_guide') if story_data else None
        style_context = ""
        
        if style_data:
            art_style = style_data.get('art_style', {})
            style_context = f"""
            Art style requirements (MUST follow exactly):
            - Style: {art_style.get('overall_style', '')}
            - Colors: {art_style.get('color_palette', '')}
            - Lighting: {art_style.get('lighting', '')}
            - Composition: {art_style.get('composition', '')}
            - Texture: {art_style.get('texture', '')}
            - Perspective: {art_style.get('perspective', '')}
            """
            
        # Create a prompt with the full character description and prompt history
        image_prompt_response = model.generate_content(f"""
        You are a visual artist creating prompts for an AI image generator.
        Create a detailed image generation prompt for this story paragraph while maintaining STRICT character and style consistency.

        Story paragraph: "{paragraph}"

        {character_context}

        {style_context}

        {prompt_history_context}

        Requirements:
        1. Start with the EXACT character descriptions provided above for any character in the scene
        2. Then describe the scene/action while maintaining those character details
        3. Follow the art style guide exactly for colors, lighting, and composition
        4. Format: [character descriptions], [scene/action description], [art style], [mood], [lighting]
        5. Keep prompt length between 75-100 words
        6. Use exact same descriptors for recurring character features
        7. NEVER change or contradict the provided character descriptions
        8. Maintain consistency with previous prompts - use same descriptors and style
        9. If a character appeared in previous prompts, use the SAME physical description
        
        Return ONLY the prompt, no additional text or explanations.
        """ )
        
        prompt = image_prompt_response.text.strip()
        # Remove quotes and special characters
        prompt = re.sub(r'["\'\n]', '', prompt)
        
        # Save prompt to history
        if story_data and 'previous_prompts' in story_data:
            story_data['previous_prompts'].append(prompt)
        
        return prompt
    except Exception as e:
        print(f"Generate image prompt error: {str(e)}")
        return "A beautiful illustration in digital art style, vibrant colors, detailed"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    try:
        return send_file(filename, mimetype='audio/mpeg')
    except Exception as e:
        print(f"Error serving audio file: {str(e)}")
        return jsonify({"error": "Could not play audio file"}), 404

@app.route('/stories')
def list_stories():
    """List all stories in the database"""
    return jsonify(shov_contents())

@app.route('/stories/<title>')
def get_story(title):
    """Get a story from the database"""
    story_response = shov_where('stories', {'title': title})
    stories = story_response.get('items', [])
    if stories:
        story = stories[0]['value']
        return render_template('story_view.html', story=story)
    return "Story not found", 404

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        shov_send_otp(email)
        return redirect(url_for('verify', email=email))
    return render_template('login.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    email = request.args.get('email')
    if request.method == 'POST':
        pin = request.form['pin']
        response = shov_verify_otp(email, pin)
        if response.get('success'):
            session['email'] = email
            return redirect(url_for('index'))
        else:
            flash("Invalid OTP. Please try again.")
            return redirect(url_for('verify', email=email))
    return render_template('verify.html', email=email)

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('index'))


@app.route('/history')
@login_required
def story_history():
    """Display user's story history"""
    stories_response = shov_where('stories', {'email': session['email']})
    user_stories = stories_response.get('items', [])
    return render_template('history.html', stories=user_stories)

@app.route('/delete_story', methods=['POST'])
@login_required
def delete_story():
    """Delete a story."""
    data = request.get_json()
    story_id = data.get('story_id')

    if not story_id:
        return jsonify({"success": False, "error": "Invalid request: No story ID provided."}), 400

    # Verify ownership
    stories_response = shov_where('stories', {'email': session['email']})
    user_stories = stories_response.get('items', [])
    owned_story_ids = [story['id'] for story in user_stories]
    print(f"User owns stories with IDs: {owned_story_ids}")

    if story_id in owned_story_ids:
        print(f"User is authorized to delete story {story_id}. Proceeding with deletion.")
        delete_response = shov_remove('stories', story_id)
        print(f"shov_remove response: {delete_response}")

        if delete_response.get('success'):
            return jsonify({"success": True})
        else:
            error_msg = delete_response.get('error', 'Unknown error during deletion.')
            return jsonify({"success": False, "error": error_msg}), 500
    else:
        print(f"User is NOT authorized to delete story {story_id}.")
        return jsonify({"success": False, "error": "You are not authorized to delete this story."}), 403

@app.route('/generate_story_stream', methods=['GET'])
def generate_story_stream():
    prompt = request.args.get('prompt')
    image_mode = request.args.get('imageMode', 'generate')
    min_paragraphs = int(request.args.get('minParagraphs', 15))
    max_paragraphs = int(request.args.get('maxParagraphs', 20))
    email = session.get('email')

    def generate():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            gen = generate_story(prompt, image_mode, min_paragraphs, max_paragraphs, email)
            while True:
                try:
                    progress = loop.run_until_complete(gen.__anext__())
                    yield f"data: {json.dumps(progress)}\n\n"
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    return Response(generate(), mimetype='text/event-stream')

async def generate_story(prompt, image_mode, min_paragraphs, max_paragraphs, email):
    """Generate story and stream progress"""
    print("\n=== Starting generate_story endpoint ===")
    print(f"Received prompt: {prompt}")
    print(f"Image mode: {image_mode}")
    print(f"Paragraph range: {min_paragraphs}-{max_paragraphs}")
    
    total_steps = min_paragraphs + 4 # story, style, characters, prompts, images
    current_step = 0

    def progress_update(task, step, total, data=None):
        return {"task": task, "progress": step, "total": total, "data": data}

    try:
        # Generate story content
        current_step += 1
        yield progress_update('Creating story content...', current_step, total_steps)
        story_data = await generate_story_content(prompt, min_paragraphs, max_paragraphs)
        story_data['previous_prompts'] = []  # Initialize a list to save the prompt history
        yield progress_update('Story content generated', current_step, total_steps, story_data)

        # Create style guide
        current_step += 1
        yield progress_update('Generating style guide...', current_step, total_steps)
        api_key = await api_key_manager.get_next_key()
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        style_guide = model.generate_content(f"""
        Create a consistent art style guide for this story. Read the title and first few paragraphs:
        Title: {story_data['title']}
        Story start: {' '.join(story_data['paragraphs'][:5])}

        Return ONLY a JSON object in this format, no other text:
        {{
            "art_style": {{
                "overall_style": "Main art style description",
                "color_palette": "Specific color scheme to use throughout",
                "lighting": "Consistent lighting approach",
                "composition": "Standard composition guidelines",
                "texture": "Texture treatment across all images",
                "perspective": "How scenes should be framed"
            }}
        }}
        """)
        
        try:
            style_text = style_guide.text.strip()
            style_text = re.sub(r'```(?:json)?\s*|\s*```', '', style_text)
            style_data = json.loads(style_text)
            if not style_data.get('art_style'):
                raise ValueError("Missing art_style in response")
            story_data['style_guide'] = style_data
        except Exception as e:
            story_data['style_guide'] = {
                "art_style": {
                    "overall_style": "Digital art style with realistic details",
                    "color_palette": "Rich, vibrant colors with deep contrasts",
                    "lighting": "Dramatic lighting with strong highlights and shadows",
                    "composition": "Dynamic, cinematic compositions",
                    "texture": "Detailed textures with fine grain",
                    "perspective": "Varied angles to enhance dramatic effect"
                }
            }
        yield progress_update('Style guide created', current_step, total_steps, story_data)

        # Analyze and create character database
        current_step += 1
        yield progress_update('Analyzing characters...', current_step, total_steps)
        char_data = await analyze_story_characters(story_data)
        if not char_data:
            story_data['character_database'] = {
                "main_characters": [],
                "supporting_characters": [],
                "groups": []
            }
        yield progress_update('Characters analyzed', current_step, total_steps, story_data)
        
        # Generate image prompts
        current_step += 1
        yield progress_update('Generating image prompts...', current_step, total_steps)
        image_prompts = []
        for i, paragraph in enumerate(story_data['paragraphs']):
            prompt = await generate_image_prompt(paragraph, story_data, i)
            image_prompts.append(prompt)
            yield progress_update(f'Generated prompt {i+1}/{len(story_data["paragraphs"] )}', current_step, total_steps)

        # Generate images
        if image_mode == 'generate':
            total_steps = current_step + len(image_prompts)
            image_data = []
            for i, prompt in enumerate(image_prompts):
                current_step += 1
                yield progress_update(f'Generating image {i+1}/{len(image_prompts)}...', current_step, total_steps)
                image_url = await generate_image(prompt)
                image_data.append({'url': image_url, 'prompt': prompt})
            story_data['images'] = image_data
        else:
            story_data['images'] = [{'prompt': prompt, 'url': None} for prompt in image_prompts]

        # Finalize
        story_data['audio_files'] = []
        story_data['email'] = email
        shov_add('stories', story_data)
        
        yield progress_update('Finished!', total_steps, total_steps, story_data)
        
    except Exception as e:
        print(f"Error in generate_story endpoint: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        yield progress_update('Error', total_steps, total_steps, {"error": str(e)})


@app.route('/test_image')
async def test_image():
    try:
        prompt = "A pixel art style image of a human sitting on a pile of books."
        image_url = await generate_image(prompt)
        return await sync_to_async(render_template)('test_image.html', image_url=image_url, error=None)
    except Exception as e:
        error_message = f"Error creating image: {str(e)}"
        print(error_message)
        print(f"Stack trace: {traceback.format_exc()}")
        return await sync_to_async(render_template)('test_image.html', image_url=None, error=error_message)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
