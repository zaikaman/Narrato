from flask import Flask, render_template, request, jsonify, send_file
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
load_dotenv()

# Configure API keys
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
FAL_KEY = os.getenv('FAL_KEY')

genai.configure(api_key=GOOGLE_API_KEY)
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
os.environ["FAL_KEY"] = FAL_KEY

async def generate_image(prompt):
    """Generate image from prompt using FAL.ai"""
    try:
        print(f"\n=== Starting generate_image ===")
        print(f"Input prompt: {prompt}")
        
        # Make sure the prompt is a string and not too long
        if isinstance(prompt, dict):
            prompt = str(prompt)
        
        # Limit prompt length and clean it up
        prompt = prompt[:500]
        prompt = re.sub(r'["\'\n]', '', prompt)
        
        # Add style to prompt
        enhanced_prompt = f"{prompt}, digital art style, high quality, detailed, vibrant colors"
        print(f"Enhanced prompt: {enhanced_prompt}")

        # Create request
        request_data = {
            "prompt": enhanced_prompt,
            "image_size": "landscape_16_9",
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
            "num_images": 1,
            "enable_safety_checker": True
        }
        print(f"Request data: {json.dumps(request_data, indent=2)}")

        print("Submitting request to FAL.ai...")
        handler = await fal_client.submit_async(
            "fal-ai/flux/dev",
            arguments=request_data
        )
        print(f"Request ID: {handler.request_id}")
        
        print("Waiting for result...")
        async for event in handler.iter_events(with_logs=True):
            print(f"Event: {event}")
            
        result = await handler.get()
        print(f"Got result: {result}")
        
        if result and isinstance(result, dict):
            if 'images' in result and len(result['images']) > 0:
                if isinstance(result['images'][0], dict) and 'url' in result['images'][0]:
                    image_url = result['images'][0]['url']
                elif isinstance(result['images'][0], str):
                    image_url = result['images'][0]
                else:
                    print(f"Unexpected image format: {result['images'][0]}")
                    return None
            elif 'image' in result:
                image_url = result['image']
            elif 'url' in result:
                image_url = result['url']
            else:
                print(f"No image URL found in result: {result}")
                return None
                
            print(f"Image generated successfully: {image_url}")
            print("=== Finished generate_image ===\n")
            return image_url
            
        print(f"Invalid result format: {result}")
        print("=== Finished generate_image with error ===\n")
        return None
        
    except Exception as e:
        print(f"Error creating image: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        print("=== Finished generate_image with exception ===\n")
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
        response_text = re.sub(r',(\s*[\\\]}])', r'\1', response_text)
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
            {chr(10).join(f"{i+1}. {prompt}" for i, prompt in enumerate(previous_prompts))}
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
        """)
        
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
        """)
        
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
async def index():
    return await sync_to_async(render_template)('index.html')

@app.route('/audio/<path:filename>')
async def serve_audio(filename):
    try:
        return await sync_to_async(send_file)(filename, mimetype='audio/mpeg')
    except Exception as e:
        print(f"Error serving audio file: {str(e)}")
        return jsonify({"error": "Could not play audio file"}), 404

@app.route('/generate_story', methods=['POST'])
async def generate_story():
    print("\n=== Starting generate_story endpoint ===")
    prompt = request.form.get('prompt')
    image_mode = request.form.get('imageMode', 'generate')  # Default is to generate images
    min_paragraphs = int(request.form.get('minParagraphs', 15))  # Default is 15
    max_paragraphs = int(request.form.get('maxParagraphs', 20))  # Default is 20
    print(f"Received prompt: {prompt}")
    print(f"Image mode: {image_mode}")
    print(f"Paragraph range: {min_paragraphs}-{max_paragraphs}")
    
    try:
        # Generate story content
        print("Generating story content...")
        story_data = await generate_story_content(prompt, min_paragraphs, max_paragraphs)
        story_data['previous_prompts'] = []  # Initialize a list to save the prompt history
        print("Story content generated successfully")

        # Create style guide
        print("Generating style guide...")
        api_key = await api_key_manager.get_next_key()
        genai.configure(api_key=api_key)
        print("Using new API key for style guide")
        
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
            print("Successfully created style guide")
        except Exception as e:
            print(f"Could not parse style guide: {str(e)}")
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

        # Analyze and create character database
        print("Analyzing characters...")
        char_data = await analyze_story_characters(story_data)
        if not char_data:
            print("Failed to create character database, using default")
            story_data['character_database'] = {
                "main_characters": [],
                "supporting_characters": [],
                "groups": []
            }
        
        # Generate image prompts in batches to avoid rate limits
        print("Generating image prompts...")
        image_prompts = []
        batch_size_gemini = 5  # Number of prompts to create before resting
        
        for i in range(0, len(story_data['paragraphs']), batch_size_gemini):
            batch_paragraphs = story_data['paragraphs'][i:i + batch_size_gemini]
            print("\nProcessing prompt batch {}/{}...".format(i // batch_size_gemini + 1, len(story_data['paragraphs']) // batch_size_gemini + 1))
            
            # Create prompts for the current batch
            batch_prompts = []
            for j, paragraph in enumerate(batch_paragraphs):
                print(f"Generating prompt for paragraph {i + j + 1}...")
                prompt = await generate_image_prompt(paragraph, story_data, i + j)
                print(f"Generated prompt: {prompt}")
                batch_prompts.append(prompt)
            
            image_prompts.extend(batch_prompts)
            
            # Rest for 15 seconds after each batch except for the last one
            if i + batch_size_gemini < len(story_data['paragraphs']):
                print("Waiting 15 seconds before next batch of prompts...")
                await asyncio.sleep(15)

        # If only creating prompts, don't call the image creation API
        if image_mode == 'prompt':
            print("Prompt-only mode, skipping image generation")
            image_data = [{'prompt': prompt, 'url': None} for prompt in image_prompts]
        else:
            # Create images in parallel, divided into small groups to avoid overloading
            print("\nGenerating images...")
            batch_size_fal = 5  # Number of images to create at the same time
            image_data = []
            
            for i in range(0, len(image_prompts), batch_size_fal):
                batch_prompts = image_prompts[i:i + batch_size_fal]
                print("\nProcessing image batch {}/{}...".format(i // batch_size_fal + 1, len(image_prompts) // batch_size_fal + 1))
                
                batch_tasks = [generate_image(prompt) for prompt in batch_prompts]
                batch_results = await asyncio.gather(*batch_tasks)
                
                # Filter out None URLs and save the prompt as well
                batch_data = []
                for url, prompt in zip(batch_results, batch_prompts):
                    if url is not None:
                        batch_data.append({
                            'url': url,
                            'prompt': prompt
                        })
                image_data.extend(batch_data)
                
                print(f"Batch {i//batch_size_fal + 1} completed: {len(batch_data)} images generated")
                
                # Wait a moment between batches to avoid API overload
                if i + batch_size_fal < len(image_prompts):
                    await asyncio.sleep(2)
            
            print(f"Total images generated: {len(image_data)}")
        
        # Add image URLs and prompts to the response
        story_data['images'] = image_data
        
        # Do not use ElevenLabs due to free tier limitations
        story_data['audio_files'] = []
        
        print("=== Finished generate_story endpoint successfully ===\n")
        return jsonify(story_data)
        
    except Exception as e:
        print(f"Error in generate_story endpoint: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        print("=== Finished generate_story endpoint with error ===\n")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
 