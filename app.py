from urllib.parse import unquote
import cloudinary
import cloudinary.uploader
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash, Response

from dotenv import load_dotenv
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'speechify-api-sdk-python', 'src'))
import google.generativeai as genai
from speechify import AsyncSpeechify, Speechify
import tempfile
import asyncio
from asgiref.sync import sync_to_async
import re
import traceback
import requests
import uuid
import base64
import json
from google.api_core import exceptions
from gradio_client import Client 

from shov_api import shov_set, shov_get, shov_contents, shov_add, shov_where, shov_send_otp, shov_verify_otp, shov_remove, shov_forget, shov_update

async def generate_with_fallback(prompt, safety_settings=None):
    """Generates content using Gemini with model fallback."""
    models = ['gemini-2.5-flash-lite', 'gemini-2.0-flash-lite', 'gemini-2.5-flash', 'gemini-2.0-flash']
    last_exception = None

    # Using a single API key for the duration of a fallback sequence.
    # Key rotation is handled by the APIKeyManager on subsequent calls to this function.
    try:
        api_key = await api_key_manager.get_least_used_key()
        genai.configure(api_key=api_key)
        print(f"Initialized Gemini for fallback generation.")
    except Exception as e:
        print(f"Failed to configure Gemini API key: {e}")
        raise

    for model_name in models:
        try:
            print(f"Attempting generation with model: {model_name}")
            model = genai.GenerativeModel(model_name)
            
            if safety_settings:
                response = model.generate_content(prompt, safety_settings=safety_settings)
            else:
                response = model.generate_content(prompt)
            
            print(f"Successfully generated content with model: {model_name}")
            return response
        except exceptions.ResourceExhausted as e:
            last_exception = e
            print(f"Model {model_name} exhausted. Switching to next model. Error: {e}")
            continue
        except Exception as e:
            print(f"An unexpected error occurred with model {model_name}: {e}")
            last_exception = e
            break

    if last_exception:
        raise last_exception
    raise Exception("Failed to generate content with all available models.")


from key_manager import api_key_manager, speechify_api_key_manager, huggingface_api_key_manager

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

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


# API keys are now managed by the APIKeyManager instances.
# Global configuration is removed to allow for dynamic key rotation per request.

async def generate_image(prompt):
    """Generate image from prompt using Gradio Client with key rotation and retry."""
    if not prompt:
        print("--- Image Generation: Skipped due to empty prompt. ---")
        return None

    max_cycles = 3  # Try the full list of keys 3 times

    for cycle in range(max_cycles):
        num_keys = len(huggingface_api_key_manager.keys)
        if num_keys == 0:
            print("--- FATAL: No Hugging Face API keys found. Cannot generate image. ---")
            return None

        for i in range(num_keys):
            current_key = ""
            try:
                # Get the next key in round-robin fashion
                current_key = await huggingface_api_key_manager.get_next_key()
                print(
                    f"\n=== Attempting image generation with key ending in ...{current_key[-4:]} "
                    f"(Attempt {i+1}/{num_keys}, Cycle {cycle+1}/{max_cycles}) ==="
                )
                print(f"Input prompt: {prompt}")

                def predict_sync():
                    # Pass the specific key for this attempt
                    client = Client("stabilityai/stable-diffusion-3.5-large-turbo", hf_token=current_key)
                    result = client.predict(
                        prompt=prompt,
                        negative_prompt="",
                        seed=0,
                        randomize_seed=True,
                        width=1024,
                        height=1024,
                        guidance_scale=0,
                        num_inference_steps=4,
                        api_name="/infer"
                    )

                    # The result is expected to be a tuple/list where the first element is a file path
                    if result and isinstance(result, (list, tuple)) and isinstance(result[0], str):
                        return result[0]  # The path is the first element

                    print(f"--- UNEXPECTED GRADIO CLIENT RAW RESULT ---: {result}")
                    raise Exception("Invalid or unexpected response format from Gradio client")

                # Run the blocking predict_sync in a thread and await result
                local_image_path = await sync_to_async(predict_sync)()

                if local_image_path:
                    # Success! Upload to Cloudinary and return.
                    upload_result = await sync_to_async(cloudinary.uploader.upload)(local_image_path)
                    cloudinary_url = upload_result.get("secure_url")
                    print(f"Image uploaded to Cloudinary: {cloudinary_url}")

                    try:
                        os.remove(local_image_path)
                    except OSError as e:
                        print(f"Error removing temporary file {local_image_path}: {e}")

                    return cloudinary_url

            except Exception as e:
                key_identifier = f"...{current_key[-4:]}" if current_key else "N/A"
                print(f"--- Key {key_identifier} failed. Error: {e} ---")
                if i == num_keys - 1:
                    print(f"--- All {num_keys} keys failed in cycle {cycle+1}. ---")
                continue  # Move to the next key

        # If we've completed a full cycle of failures, wait before retrying
        if cycle < max_cycles - 1:
            print("--- Waiting for 60 seconds before retrying all keys... ---")
            await asyncio.sleep(60)

    # If all cycles fail
    print("--- All retry cycles failed. Could not generate image. ---")
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

async def generate_voice(text):
    """Generate voice from text using Speechify and upload to Cloudinary"""
    try:
        # Get a key for this request using round-robin
        speechify_key = await speechify_api_key_manager.get_next_key()
        speechify_client = AsyncSpeechify(token=speechify_key)

        ssml_input = f'<speak><speechify:style emotion="assertive">{text}</speechify:style></speak>'
        response = await speechify_client.tts.audio.speech(
            input=ssml_input,
            voice_id="oliver",
            audio_format="mp3"
        )
        
        audio_bytes = base64.b64decode(response.audio_data)

        # Save audio to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
            temp_audio_file.write(audio_bytes)
            temp_audio_path = temp_audio_file.name

        # Upload the audio file to Cloudinary
        upload_result = await sync_to_async(cloudinary.uploader.upload)(
            temp_audio_path,
            resource_type="video",
            folder="storybook_audio",
            public_id=f"{uuid.uuid4()}"
        )

        # Clean up the temporary file
        os.remove(temp_audio_path)

        cloudinary_url = upload_result.get('secure_url')
        print(f"Audio uploaded to Cloudinary: {cloudinary_url}")
        return cloudinary_url

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
        
        prompt_content = f'''
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
        '''
        english_story_response = await generate_with_fallback(prompt_content)

        print("Received response from Gemini")
        
        # Get text response and clean it up
        response_text = english_story_response.text.strip()
        print(f"Raw response: {response_text}")
        
        # Remove markdown code blocks
        response_text = re.sub(r'```(?:json)?\s*|\s*```', '', response_text)

        # Remove trailing commas before closing brackets and braces
        response_text = re.sub(r',(\s*[\\]}])', r'\\1', response_text)
        
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

async def generate_style_guide(story_data):
    """Generate a consistent art style guide for the story."""
    try:
        prompt_content = f'''
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
        '''
        style_guide_response = await generate_with_fallback(prompt_content)

        if not style_guide_response:
            raise Exception("Failed to generate style guide after multiple retries.") 
        
        style_text = style_guide_response.text.strip()
        style_text = re.sub(r'```(?:json)?\s*|\s*```', '', style_text)
        style_data = json.loads(style_text)
        if not style_data.get('art_style'):
            raise ValueError("Missing art_style in response")
        return style_data
        
    except Exception as e:
        print(f"Error generating style guide: {e}")
        return {
            "art_style": {
                "overall_style": "Digital art style with realistic details",
                "color_palette": "Rich, vibrant colors with deep contrasts",
                "lighting": "Dramatic lighting with strong highlights and shadows",
                "composition": "Dynamic, cinematic compositions",
                "texture": "Detailed textures with fine grain",
                "perspective": "Varied angles to enhance dramatic effect"
            }
        }

async def analyze_story_characters(story_data):
    """Analyze and create consistent descriptions for all characters in the story"""
    try:
        prompt_content = f'''
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
        '''
        character_analysis = await generate_with_fallback(prompt_content)

        if not character_analysis:
            print("Failed to generate character analysis after multiple retries.")
            return None
            
        try:
            char_text = character_analysis.text.strip()
            char_text = re.sub(r'```(?:json)?\s*|\s*```', '', char_text)
            print(f"Character analysis response: {char_text}")
            
            char_data = json.loads(char_text)
            if not (char_data.get('main_characters') or char_data.get('supporting_characters')):
                raise ValueError("Missing character data in response")
                
            print("Successfully created character database")
            return char_data
            
        except Exception as e:
            print(f"Could not parse character analysis: {str(e)}")
            print(f"Raw response: {character_analysis.text}")
            return None
            
    except Exception as e:
        print(f"Error in analyze_story_characters: {str(e)}")
        return None

async def generate_all_image_prompts(story_data):
    """Create all image prompts for the story using Gemini, with retry and fallback."""
    
    for attempt in range(3):
        print(f"--- Image Prompt Generation: Attempt {attempt + 1}/3 ---")
        try:
            char_db = story_data.get('character_database', {})
            style_data = story_data.get('style_guide')
            style_context = ""
            
            if style_data:
                art_style = style_data.get('art_style', {})
                style_context = f'''
                Art style requirements (MUST follow exactly):
                - Style: {art_style.get('overall_style', '')}
                - Colors: {art_style.get('color_palette', '')}
                - Lighting: {art_style.get('lighting', '')}
                - Composition: {art_style.get('composition', '')}
                - Texture: {art_style.get('texture', '')}
                - Perspective: {art_style.get('perspective', '')}
                '''

            paragraphs_json = json.dumps(story_data['paragraphs'], indent=2)

            prompt_for_gemini = f'''
    You are a visual artist creating prompts for an AI image generator. 
    Your task is to create a detailed image generation prompt for EACH paragraph in the story provided, while maintaining STRICT character and style consistency across all images.

    **Story Paragraphs:**
    {paragraphs_json}

    **Instructions:**
    1.  **Analyze Characters and Scenes:** For each paragraph, identify the characters, their emotional state, and the scene.
    2.  **Apply Consistent Descriptions:** Use the provided Character Database to ensure characters look the same in every image. Apply `expression_override` or `appearance_change` based on the context of each paragraph.
    3.  **Construct Prompts:** Create a list of detailed image prompts, one for each paragraph. Each prompt must:
        - Start with the EXACT, combined character descriptions for that scene.
        - Describe the scene/action from the paragraph.
        - Adhere to the Art Style Guide.
        - Be between 75-100 words.
        - Follow the format: [character descriptions], [scene/action description], [art style], [mood], [lighting].
    4.  **Ensure Consistency:** The prompts should tell a cohesive visual story, with consistent characters and environments.

    **Provided Information:**

    **1. Character Database:**
    {json.dumps(char_db, indent=2)}

    **2. Art Style Guide:**
    {style_context}

    **Final Output:**
    Return ONLY a JSON object in this format, with a list of prompts matching the number of paragraphs.
    {{
        "image_prompts": [
            "The final, detailed image prompt for paragraph 1.",
            "The final, detailed image prompt for paragraph 2.",
            ...
        ]
    }}
    '''
            
            safety_settings = {
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            }

            image_prompts_response = await generate_with_fallback(prompt_for_gemini, safety_settings=safety_settings)
            
            if not image_prompts_response:
                print("Failed to get a response from Gemini for image prompts.")
                continue

            response_text = image_prompts_response.text.strip()
            response_text = re.sub(r'```(?:json)?\s*|\s*```', '', response_text)
            response_text = re.sub(r',(\s*\])', r'\1', response_text)
            response_text = re.sub(r',(\s*\})', r'\1', response_text)
            
            prompts_data = json.loads(response_text)
            prompts = prompts_data.get("image_prompts", [])
            
            if not prompts:
                raise ValueError("Generated JSON is missing the 'image_prompts' key or the list is empty.")

            cleaned_prompts = [re.sub(r'["\'\n]', '', p) for p in prompts]
            
            if len(cleaned_prompts) != len(story_data['paragraphs']):
                raise ValueError(f"Mismatch in number of prompts ({len(cleaned_prompts)}) and paragraphs ({len(story_data['paragraphs'])}).")

            print("--- Image Prompt Generation: Success! ---")
            return cleaned_prompts

        except (json.JSONDecodeError, ValueError) as e:
            print(f"--- Image Prompt Generation: Attempt {attempt + 1} failed due to parsing/validation error: {e} ---")
            if attempt < 2:
                print("--- Retrying... ---")
            continue

    print("--- Image Prompt Generation: All 3 attempts failed. Falling back to no images. ---")
    return [None] * len(story_data['paragraphs'])

@app.route('/')
def index():
    return render_template('index.html', show_browse_button=True)

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

from urllib.parse import unquote



@app.route('/browse')
def browse_stories():
    """Browse all public stories"""
    stories_response = shov_where('stories', {'public': True})
    public_stories = stories_response.get('items', [])
    return render_template('browse.html', stories=public_stories, show_browse_button=False)


@app.route('/stories/<title>')
def get_story(title):
    """Get a story from the database"""
    decoded_title = unquote(title)
    story_response = shov_where('stories', {'title': decoded_title})
    if not story_response.get('success', True):
        return render_template('story_view.html', story=None, error="database_down"), 503

    stories = story_response.get('items', [])
    if stories:
        story = stories[0]['value']
        return render_template('story_view.html', story=story)
    
    return render_template('story_view.html', story=None, error="not_found"), 404


@app.route('/view_story/<story_uuid>')
def view_story(story_uuid):
    """Get a story from the database by ID"""
    story_response = shov_where('stories', {'story_uuid': story_uuid})
    
    if not story_response.get('success', True):
        return render_template('story_view.html', story=None, error="database_down"), 503

    stories = story_response.get('items', [])
    if stories:
        story = stories[0]['value']
        return render_template('story_view.html', story=story)
    
    return render_template('story_view.html', story=None, error="not_found"), 404



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
        return jsonify({"success": False, "error": "Invalid request: No story ID provided."} ), 400

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
        return jsonify({"success": False, "error": "You are not authorized to delete this story."} ), 403



# --- Production (Worker) Endpoints ---

@app.route('/start-story-generation', methods=['POST'])
def start_story_generation():
    """Starts the asynchronous story generation process."""
    data = request.get_json()
    if not data or not data.get('prompt'):
        return jsonify({"success": False, "error": "Prompt is required."} ), 400

    prompt = data.get('prompt')
    image_mode = data.get('imageMode', 'generate')
    public = data.get('public', False)
    min_paragraphs = int(data.get('minParagraphs', 15))
    max_paragraphs = int(data.get('maxParagraphs', 20))
    email = session.get('email')

    task_uuid = str(uuid.uuid4())
    task = {
        "task_uuid": task_uuid,
        "status": "pending",
        "prompt": prompt,
        "image_mode": image_mode,
        "public": public,
        "min_paragraphs": min_paragraphs,
        "max_paragraphs": max_paragraphs,
        "email": email,
        "created_at": str(uuid.uuid4()), # Using uuid for timestamp for now
        "progress": 0,
        "task_message": "Task is pending in the queue.",
        "result": None,
        "error": None
    }

    add_response = shov_add('generation_tasks', task)
    if not add_response.get('success'):
        print(f"Failed to create generation task: {add_response}")
        return jsonify({"success": False, "error": "Failed to create generation task."} ), 500

    return jsonify({"success": True, "task_uuid": task_uuid})


@app.route('/generation-status/<task_uuid>')
def generation_status(task_uuid):
    """Polls for the status of a story generation task."""
    task_response = shov_where('generation_tasks', {'task_uuid': task_uuid})
    tasks = task_response.get('items', [])
    if not tasks:
        return jsonify({"success": False, "error": "Task not found"}), 404
    
    task = tasks[0]['value']
    
    return jsonify({
        "success": True, 
        "status": task.get('status'), 
        "progress": task.get('progress'), 
        "task_message": task.get('task_message'), 
        "result": task.get('result'), 
        "error": task.get('error')
    })


@app.route('/api/run-worker', methods=['POST'])
def run_worker():
    """
    A state-machine worker with a locking mechanism to prevent race conditions.
    """
    # 1. Authenticate the request
    auth_header = request.headers.get('Authorization')
    worker_secret = os.getenv('WORKER_SECRET')
    if not worker_secret or auth_header != f"Bearer {worker_secret}":
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    # 2. Select a single, unlocked task to process
    task_item = None
    # First, find tasks that are already processing but not locked (not in an _inprogress step)
    processing_tasks_response = shov_where('generation_tasks', {'status': 'processing'})
    if processing_tasks_response.get('items'):
        for item in processing_tasks_response['items']:
            if not item.get('value', {}).get('generation_step', '').endswith('_inprogress'):
                task_item = item
                break
    
    # If no processing task is ready, find a new pending task
    if not task_item:
        pending_tasks_response = shov_where('generation_tasks', {'status': 'pending'})
        if pending_tasks_response.get('items'):
            task_item = pending_tasks_response['items'][0]

    if not task_item:
        return jsonify({"success": True, "message": "No ready tasks to process."} )

    task_id = task_item['id']
    task_data = task_item['value']

    # 3. Get the current step, defaulting to 'start' for pending tasks
    current_step = 'start' if task_data.get('status') == 'pending' else task_data.get('generation_step')
    print(f"Found task {task_id} at step '{current_step}'")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        if current_step == 'start':
            task_data['status'] = 'processing'
            task_data['generation_step'] = 'generating_content_inprogress'
            task_data['task_message'] = 'Generating story content...'
            task_data['progress'] = 5
            shov_update('generation_tasks', task_id, task_data)
            
            story_data = loop.run_until_complete(generate_story_content(task_data['prompt'], task_data['min_paragraphs'], task_data['max_paragraphs']))
            
            task_data['intermediate_data'] = story_data
            task_data['generation_step'] = 'generating_elements'
            task_data['progress'] = 15
            task_data['task_message'] = 'Analyzing story elements...'
            shov_update('generation_tasks', task_id, task_data)

        elif current_step == 'generating_elements':
            task_data['generation_step'] = 'generating_elements_inprogress'
            shov_update('generation_tasks', task_id, task_data)

            story_data = task_data['intermediate_data']
            style_task = generate_style_guide(story_data)
            chars_task = analyze_story_characters(story_data)
            style_data, char_data = loop.run_until_complete(asyncio.gather(style_task, chars_task))
            story_data['style_guide'] = style_data
            story_data['character_database'] = char_data if char_data else {"main_characters": [], "supporting_characters": [], "groups": []}
            
            task_data['intermediate_data'] = story_data
            task_data['generation_step'] = 'generating_prompts'
            task_data['progress'] = 25
            task_data['task_message'] = 'Generating image prompts...'
            shov_update('generation_tasks', task_id, task_data)

        elif current_step == 'generating_prompts':
            task_data['generation_step'] = 'generating_prompts_inprogress'
            shov_update('generation_tasks', task_id, task_data)

            story_data = task_data['intermediate_data']
            image_prompts = loop.run_until_complete(generate_all_image_prompts(story_data))
            
            task_data['image_prompts'] = image_prompts
            task_data['generation_step'] = 'generating_images'
            task_data['progress'] = 35
            task_data['task_message'] = 'Generating images...'
            shov_update('generation_tasks', task_id, task_data)

        elif current_step == 'generating_images':
            task_data['generation_step'] = 'generating_images_inprogress'
            shov_update('generation_tasks', task_id, task_data)

            if task_data['image_mode'] == 'generate':
                image_prompts = task_data['image_prompts']
                image_tasks = [generate_image(p) for p in image_prompts]
                image_urls = loop.run_until_complete(asyncio.gather(*image_tasks))
                image_data = [{'url': url, 'prompt': p} for url, p in zip(image_urls, image_prompts)]
                story_data = task_data['intermediate_data']
                story_data['images'] = image_data
                task_data['intermediate_data'] = story_data
                task_data['task_message'] = f'Generated {len(image_urls)} images'
            else:
                task_data['task_message'] = 'Skipping image generation'
            
            task_data['generation_step'] = 'generating_audio'
            task_data['progress'] = 70
            shov_update('generation_tasks', task_id, task_data)

        elif current_step == 'generating_audio':
            task_data['generation_step'] = 'generating_audio_inprogress'
            shov_update('generation_tasks', task_id, task_data)

            story_data = task_data['intermediate_data']
            audio_tasks = [generate_voice(story_data['title'])] + [generate_voice(p) for p in story_data['paragraphs']]
            audio_files = loop.run_until_complete(asyncio.gather(*audio_tasks))
            story_data['audio_files'] = audio_files
            
            task_data['intermediate_data'] = story_data
            task_data['generation_step'] = 'saving'
            task_data['progress'] = 95
            task_data['task_message'] = 'Finalizing and saving story...'
            shov_update('generation_tasks', task_id, task_data)

        elif current_step == 'saving':
            task_data['generation_step'] = 'saving_inprogress'
            shov_update('generation_tasks', task_id, task_data)

            story_data = task_data['intermediate_data']
            story_data['email'] = task_data['email']
            story_data['story_uuid'] = str(uuid.uuid4())
            story_data['public'] = task_data['public']
            add_response = shov_add('stories', story_data)
            if not add_response.get('success'):
                raise Exception(f"Failed to save story to history: {add_response.get('details')}")
            
            task_data['status'] = 'completed'
            task_data['generation_step'] = 'done'
            task_data['progress'] = 100
            task_data['task_message'] = 'Story generation complete.'
            task_data['result'] = story_data
            shov_update('generation_tasks', task_id, task_data)

    except Exception as e:
        print(f"Worker failed on step '{current_step}' for task {task_id}: {e}")
        traceback.print_exc()
        task_data['status'] = 'failed'
        task_data['error'] = str(e)
        task_data['task_message'] = f"An error occurred during step: {current_step}"
        shov_update('generation_tasks', task_id, task_data)
    finally:
        loop.close()

    return jsonify({"success": True, "message": f"Processed step '{current_step}' for task {task_id}."})

        
# --- Local Development (Streaming) Endpoints ---

async def generate_story_for_stream(prompt, image_mode, min_paragraphs, max_paragraphs, email, public, story_uuid=None):
    """Generate story and stream progress, with state saving."""
    
    def progress_update(task, step, total, data=None):
        return {"task": task, "progress": step, "total": total, "data": data}

    try:
        # Load or initialize state
        step = 0
        state_data = {}
        shov_id = None

        if story_uuid:
            response = None
            for _ in range(3): # Retry up to 3 times
                response = shov_where('stream_progress', {'story_uuid': story_uuid})
                if response and response.get('items'):
                    break
                await asyncio.sleep(0.5) # Wait 500ms

            if response and response.get('items'):
                item = response['items'][0]
                shov_id = item['id']
                state_data = item['value']
                step = state_data.get('step', 0)
                print(f"Resuming story {story_uuid} (shov_id: {shov_id}) from step {step}")

        story_data = state_data.get('story_data', {})
        image_prompts = state_data.get('image_prompts', [])

        def save_progress(current_step, data_to_save):
            nonlocal shov_id
            state = {'step': current_step, 'story_uuid': story_uuid, **data_to_save}

            if shov_id:
                result = shov_update('stream_progress', shov_id, state)
            else:
                result = shov_add('stream_progress', state)
                if result.get('success') and result.get('id'):
                    shov_id = result['id']

            if not result.get('success'):
                print(f"CRITICAL: Failed to save progress for story {story_uuid}. Error: {result.get('details')}")
                raise IOError(f"Failed to save progress: {result.get('details')}")
            print(f"Saved progress for story {story_uuid} at step {current_step}")

        if step > 0:
            initial_progress = 10
            if step == 2: initial_progress = 25
            elif step == 3: initial_progress = 35
            elif step == 4: initial_progress = 70
            elif step == 5: initial_progress = 95
            yield progress_update(f"Resuming generation...", initial_progress, 100, story_data)

        while step < 6:
            if step == 0:
                # 1. Generate story content
                yield progress_update('Creating story content...', 0, 100)
                ping_task = asyncio.create_task(generate_story_content(prompt, min_paragraphs, max_paragraphs))
                while not ping_task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(ping_task), timeout=15)
                    except asyncio.TimeoutError:
                        yield progress_update('Creating story content... (ping)', 0, 100)
                story_data = await ping_task
                save_progress(1, {'story_data': story_data})
                yield progress_update('Story content generated', 10, 100, story_data)
                step = 1
            elif step == 1:
                # 2 & 3. Generate style guide and analyze characters
                yield progress_update('Analyzing story elements...', 15, 100)
                style_task = generate_style_guide(story_data)
                chars_task = analyze_story_characters(story_data)
                
                # Wrap gather in a coroutine so create_task can accept it
                async def gather_elements():
                    return await asyncio.gather(style_task, chars_task)

                gather_task = asyncio.create_task(gather_elements())
                while not gather_task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(gather_task), timeout=15)
                    except asyncio.TimeoutError:
                        yield progress_update('Analyzing story elements... (ping)', 15, 100)
                style_data, char_data = await gather_task
                story_data['style_guide'] = style_data
                story_data['character_database'] = char_data if char_data else {"main_characters": [], "supporting_characters": [], "groups": []}
                save_progress(2, {'story_data': story_data})
                yield progress_update('Story elements analyzed', 25, 100, story_data)
                step = 2
            elif step == 2:
                # 4. Generate image prompts
                yield progress_update('Generating image prompts...', 30, 100)
                prompts_task = asyncio.create_task(generate_all_image_prompts(story_data))
                while not prompts_task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(prompts_task), timeout=15)
                    except asyncio.TimeoutError:
                        yield progress_update('Generating image prompts... (ping)', 30, 100)
                image_prompts = await prompts_task
                save_progress(3, {'story_data': story_data, 'image_prompts': image_prompts})
                yield progress_update(f'Generated {len(image_prompts)} prompts', 35, 100)
                step = 3
            elif step == 3:
                # 5. Generate images
                if image_mode == 'generate':
                    yield progress_update('Generating images...', 40, 100)
                    image_data = story_data.get('images', [])
                    num_prompts = len(image_prompts)
                    start_index = len(image_data)
                    for i, p in enumerate(image_prompts[start_index:], start=start_index):
                        progress = 40 + int(30 * (i + 1) / num_prompts)
                        image_task = asyncio.create_task(generate_image(p))
                        while not image_task.done():
                            try:
                                await asyncio.wait_for(asyncio.shield(image_task), timeout=15)
                            except asyncio.TimeoutError:
                                yield progress_update(f'Generating image {i + 1} of {num_prompts}... (ping)', progress, 100)
                        image_url = await image_task
                        
                        image_data.append({'url': image_url, 'prompt': p})
                        story_data['images'] = image_data
                        # Save progress within the loop for resumability
                        save_progress(3, {'story_data': story_data, 'image_prompts': image_prompts})
                        yield progress_update(f'Generated image {i + 1} of {num_prompts}', progress, 100, story_data)
                else:
                    story_data['images'] = [{'prompt': p, 'url': None} for p in image_prompts]
                    yield progress_update('Skipping image generation', 70, 100)
                
                save_progress(4, {'story_data': story_data, 'image_prompts': image_prompts})
                step = 4
            elif step == 4:
                # 6. Generate audio files
                yield progress_update('Generating audio files...', 75, 100)
                audio_files = story_data.get('audio_files', [])
                texts_to_voice = [story_data['title']] + story_data['paragraphs']
                num_texts = len(texts_to_voice)
                start_index = len(audio_files)
                for i, text in enumerate(texts_to_voice[start_index:], start=start_index):
                    progress = 75 + int(20 * (i + 1) / num_texts)
                    audio_task = asyncio.create_task(generate_voice(text))
                    while not audio_task.done():
                        try:
                            await asyncio.wait_for(asyncio.shield(audio_task), timeout=15)
                        except asyncio.TimeoutError:
                            yield progress_update(f'Generated audio {i + 1} of {num_texts}... (ping)', progress, 100)
                    audio_url = await audio_task

                    audio_files.append(audio_url)
                    story_data['audio_files'] = audio_files
                    await asyncio.sleep(1) # Keep the rate-limiting sleep
                    # Save progress within the loop for resumability
                    save_progress(4, {'story_data': story_data, 'image_prompts': image_prompts})
                    yield progress_update(f'Generated audio {i + 1} of {num_texts}', progress, 100, {'audio_file': audio_url, 'index': i})

                save_progress(5, {'story_data': story_data, 'image_prompts': image_prompts})
                step = 5
            elif step == 5:
                # Finalize
                story_data['email'] = email
                story_data['story_uuid'] = story_uuid
                story_data['public'] = public
                add_response = shov_add('stories', story_data)
                if not add_response.get('success'):
                    error_details = add_response.get('details', 'No details provided.')
                    print(f"CRITICAL: Failed to save story to history. Error: {add_response.get('error')}. Details: {error_details}")
                
                if shov_id:
                    shov_remove('stream_progress', shov_id)
                yield progress_update('Finished!', 100, 100, story_data)
                step = 6
        
    except Exception as e:
        print(f"Error in generate_story_for_stream: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        yield progress_update('Error', 100, 100, {"error": str(e)})

@app.route('/generate_story_stream', methods=['GET'])
def generate_story_stream():
    try:
        prompt = request.args.get('prompt')
        if not prompt:
            raise ValueError("A story prompt is required.")

        image_mode = request.args.get('imageMode', 'generate')
        public = request.args.get('public') == 'true'
        
        min_param = request.args.get('minParagraphs')
        max_param = request.args.get('maxParagraphs')
        min_paragraphs = int(min_param) if min_param and min_param.isdigit() else 15
        max_paragraphs = int(max_param) if max_param and max_param.isdigit() else 20

        email = session.get('email')
        story_uuid = request.args.get('story_uuid')

        def generate():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                gen = generate_story_for_stream(prompt, image_mode, min_paragraphs, max_paragraphs, email, public, story_uuid)
                while True:
                    try:
                        progress = loop.run_until_complete(gen.__anext__())
                        yield f"data: {json.dumps(progress)}\n\n"
                    except StopAsyncIteration:
                        break
            finally:
                loop.close()

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        print(f"Error in generate_story_stream setup: {e}")
        traceback.print_exc()
        
        def error_generate(exc):
            error_payload = {
                "task": "Error", 
                "progress": 100, 
                "total": 100, 
                "data": {"error": f"A server setup error occurred: {str(exc)}"}
            }
            yield f"data: {json.dumps(error_payload)}\n\n"

        return Response(error_generate(e), mimetype='text/event-stream')


from xhtml2pdf import pisa
from io import BytesIO
import requests
import base64
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def link_callback(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those
    resources
    """
    # The URI from url_for('static', ...) will start with /static/
    if uri.startswith('/static/'):
        project_root = os.path.dirname(__file__)
        # The uri is /static/css/file.css, we need to map it to <project_root>/static/css/file.css
        path = os.path.join(project_root, uri.lstrip('/'))
        path = os.path.normpath(path)

        if os.path.exists(path):
            return Path(path).as_uri()

    if uri.startswith("data:"):
        return uri

    return uri

@app.route('/export_pdf/<story_uuid>')
def export_pdf(story_uuid):
    """Export a story as a PDF"""
    story_response = shov_where('stories', {'story_uuid': story_uuid})
    stories = story_response.get('items', [])
    if stories:
        story = stories[0]['value']

        # Register fonts
        static_path = os.path.join(os.path.dirname(__file__), 'static')
        medieval_font_path = os.path.join(static_path, 'MedievalSharp', 'MedievalSharp-Regular.ttf')
        literata_font_path = os.path.join(static_path, 'Literata', 'Literata-VariableFont_opsz,wght.ttf')
        
        if os.path.exists(medieval_font_path):
            pdfmetrics.registerFont(TTFont('MedievalSharp', medieval_font_path))
        if os.path.exists(literata_font_path):
            pdfmetrics.registerFont(TTFont('Literata', literata_font_path))

        # Download images and convert to data URIs
        if 'images' in story:
            for image_data in story['images']:
                if image_data.get('url') and image_data['url'].startswith('http'):
                    try:
                        response = requests.get(image_data['url'], timeout=10)
                        response.raise_for_status()
                        
                        content_type = response.headers.get('Content-Type', 'image/jpeg')
                        encoded_string = base64.b64encode(response.content).decode('utf-8')
                        
                        image_data['url'] = f"data:{content_type};base64,{encoded_string}"
                    except requests.exceptions.RequestException as e:
                        print(f"Could not fetch image {image_data['url']}: {e}")
                        image_data['url'] = '' 

        html = render_template('pdf_template.html', story=story)
        
        pdf_file = BytesIO()
        pisa_status = pisa.CreatePDF(
            BytesIO(html.encode('UTF-8')),
            dest=pdf_file,
            encoding='UTF-8',
            link_callback=link_callback
        )

        if pisa_status.err:
            print(f"PDF creation error: {pisa_status.err}")
            return "Error creating PDF", 500

        pdf_file.seek(0)
        
        response = Response(pdf_file.read(), mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'attachment; filename="{story["title"]}.pdf"'
        return response

    return "Story not found", 404

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)