import asyncio
import google.generativeai as genai
from google.api_core import exceptions
from .key_manager import api_key_manager, speechify_api_key_manager, huggingface_api_key_manager
import cloudinary
import cloudinary.uploader
from speechify import AsyncSpeechify
import tempfile
from asgiref.sync import sync_to_async
import re
import traceback
import uuid
import base64
import json
import os
from gradio_client import Client

async def generate_with_fallback(prompt, safety_settings=None):
    """Generates content using Gemini (gemini-2.5-flash-family) with model fallback and key rotation."""
    models = ['gemini-2.5-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-flash']
    last_exception = None
    num_keys = len(api_key_manager.keys)

    for model_name in models:
        for i in range(num_keys):
            api_key = ""
            try:
                api_key = await api_key_manager.get_next_key()
                genai.configure(api_key=api_key)
                print(f"Attempting generation with model: {model_name} using key ...{api_key[-4:]}")
                
                model = genai.GenerativeModel(model_name)
                
                if safety_settings:
                    response = model.generate_content(prompt, safety_settings=safety_settings)
                else:
                    response = model.generate_content(prompt)
                
                print(f"Successfully generated content with model: {model_name}")
                return response
            except exceptions.ResourceExhausted as e:
                last_exception = e
                key_identifier = f"...{api_key[-4:]}" if api_key else "N/A"
                print(f"Key {key_identifier} exhausted for model {model_name}. Switching to next key.")
                continue
            except Exception as e:
                key_identifier = f"...{api_key[-4:]}" if api_key else "N/A"
                print(f"An unexpected error occurred with model {model_name} and key {key_identifier}: {e}")
                last_exception = e
                break
        
        print(f"All keys failed for model {model_name}.")

    if last_exception:
        raise last_exception
    raise Exception("Failed to generate content with all available models and keys.")

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
                current_key = await huggingface_api_key_manager.get_next_key()
                print(
                    f"=== Attempting image generation with key ending in ...{current_key[-4:]} "
                    f"(Attempt {i+1}/{num_keys}, Cycle {cycle+1}/{max_cycles}) ==="
                )
                print(f"Input prompt: {prompt}")

                def predict_sync():
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
                    if result and isinstance(result, (list, tuple)) and isinstance(result[0], str):
                        return result[0]
                    print(f"--- UNEXPECTED GRADIO CLIENT RAW RESULT ---: {result}")
                    raise Exception("Invalid or unexpected response format from Gradio client")

                local_image_path = await sync_to_async(predict_sync)()

                if local_image_path:
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
                continue

        if cycle < max_cycles - 1:
            print("--- Waiting for 60 seconds before retrying all keys... ---")
            await asyncio.sleep(60)

    print("--- All retry cycles failed. Could not generate image. ---")
    return None

def find_character(name, char_db):
    """Find character information in the database"""
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
        speechify_key = await speechify_api_key_manager.get_next_key()
        speechify_client = AsyncSpeechify(token=speechify_key)
        ssml_input = f'<speak><speechify:style emotion="assertive">{text}</speechify:style></speak>'
        response = await speechify_client.tts.audio.speech(
            input=ssml_input,
            voice_id="oliver",
            audio_format="mp3"
        )
        audio_bytes = base64.b64decode(response.audio_data)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
            temp_audio_file.write(audio_bytes)
            temp_audio_path = temp_audio_file.name
        upload_result = await sync_to_async(cloudinary.uploader.upload)(
            temp_audio_path,
            resource_type="video",
            folder="storybook_audio",
            public_id=f"{uuid.uuid4()}"
        )
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
    if min_paragraphs == max_paragraphs:
        paragraph_instruction = f"The story MUST have EXACTLY {max_paragraphs} paragraphs."
        paragraph_range_doc = f"exactly {max_paragraphs}"
        final_instruction = f"- {paragraph_instruction}"
    else:
        paragraph_instruction = f"Number of paragraphs should be between {min_paragraphs} and {max_paragraphs}."
        paragraph_range_doc = f"between {min_paragraphs}-{max_paragraphs}"
        final_instruction = f"- {paragraph_instruction}\n        - The story should feel complete, don't force it to exactly {max_paragraphs} paragraphs"

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
                ... ({paragraph_range_doc} paragraphs)
            ],
            "moral": "The moral lesson from the story"
        }}

        IMPORTANT FORMAT RULES:
        - Do NOT add trailing commas after the last item in arrays or objects
        - Each paragraph must be under 30 words with rich details
        - Story should match the theme: {prompt}
        - Return ONLY the JSON object, no other text
        {final_instruction}
        '''
    try:
        print(f"=== Starting generate_story_content ===")
        print(f"Input prompt: {prompt}")
        english_story_response = await generate_with_fallback(prompt_content)
        response_text = english_story_response.text.strip()
        response_text = re.sub(r'```(?:json)?\s*|\s*```', '', response_text)
        response_text = re.sub(r',(\s*\])', r'\1', response_text)
        story_data = json.loads(response_text)
        if not all(key in story_data for key in ['title', 'paragraphs', 'moral']):
            raise ValueError("Missing required fields in story data")
        adjusted_paragraphs = []
        for paragraph in story_data['paragraphs']:
            split_paragraphs = check_paragraph_length(paragraph)
            adjusted_paragraphs.extend(split_paragraphs)
        story_data['paragraphs'] = adjusted_paragraphs
        num_paragraphs = len(story_data['paragraphs'])
        if num_paragraphs > max_paragraphs:
            story_data['paragraphs'] = story_data['paragraphs'][:max_paragraphs]
        elif num_paragraphs < min_paragraphs:
            while len(story_data['paragraphs']) < min_paragraphs:
                story_data['paragraphs'].append("And the story continues...")
        return story_data
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error processing story: {str(e)}")
        return {"title": "Error Creating Story", "paragraphs": ["We encountered an error while creating your story."] * min_paragraphs, "moral": "Sometimes we need to be patient and try again."}
    except Exception as e:
        print(f"Generate story error: {str(e)}")
        raise

async def generate_style_guide(story_data):
    """Generate a consistent art style guide for the story."""
    prompt_template = '''
        Create a consistent art style guide for this story. Read the title and first few paragraphs:
        Title: {title}
        Story start: {story_start}

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
    try:
        story_start = ' '.join(story_data['paragraphs'][:5])
        prompt_content = prompt_template.format(title=story_data['title'], story_start=story_start)
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
        return {"art_style": {"overall_style": "Digital art style with realistic details", "color_palette": "Rich, vibrant colors with deep contrasts", "lighting": "Dramatic lighting with strong highlights and shadows", "composition": "Dynamic, cinematic compositions", "texture": "Detailed textures with fine grain", "perspective": "Varied angles to enhance dramatic effect"}}

async def analyze_story_characters(story_data):
    """Analyze and create consistent descriptions for all characters in the story"""
    prompt_template = '''
        You are a character designer creating consistent descriptions for all characters in this story. 
        Analyze the entire story carefully and create detailed, consistent descriptions that will be used for ALL images.
        
        Title: {title}
        Story: {story}

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
            "supporting_characters": [],
            "groups": [
                {{
                    "name": "Group identifier",
                    "members_description": "Consistent description for group members",
                    "variations": []
                }}
            ]
        }}    
    '''
    try:
        story_text = ' '.join(story_data['paragraphs'])
        prompt_content = prompt_template.format(title=story_data['title'], story=story_text)
        character_analysis = await generate_with_fallback(prompt_content)
        if not character_analysis:
            print("Failed to generate character analysis after multiple retries.")
            return None
        char_text = character_analysis.text.strip()
        char_text = re.sub(r'```(?:json)?\s*|\s*```', '', char_text)
        char_data = json.loads(char_text)
        if not (char_data.get('main_characters') or char_data.get('supporting_characters')):
            raise ValueError("Missing character data in response")
        return char_data
    except Exception as e:
        print(f"Could not parse character analysis: {str(e)}")
        return None

async def generate_all_image_prompts(story_data):
    """Create all image prompts for the story using Gemini, with retry and fallback."""
    num_paragraphs = len(story_data['paragraphs'])
    prompt_template = '''
    You are a visual artist creating prompts for an AI image generator. 
    Your task is to create a detailed image generation prompt for EACH paragraph in the story provided, while maintaining STRICT character and style consistency across all images. Make sure the art style is the same in every image.

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
    5.  **Match Paragraph Count:** The number of prompts in the final `image_prompts` list MUST be exactly equal to the number of paragraphs provided. If you are given {num_paragraphs} paragraphs, you must generate {num_paragraphs} prompts.

    **Provided Information:**

    **1. Character Database:**
    {char_db_json}

    **2. Art Style Guide:**
    {style_context}

    **Final Output:**
    Return ONLY a JSON object in this format. The `image_prompts` array must contain a prompt for every single paragraph provided. For example, if there are {num_paragraphs} paragraphs, there must be {num_paragraphs} strings in the `image_prompts` list.
    {{
        "image_prompts": [
            "The final, detailed image prompt for paragraph 1.",
            "The final, detailed image prompt for paragraph 2.",
            ...
        ]
    }}
    '''
    for attempt in range(10):
        try:
            char_db = story_data.get('character_database', {})
            style_data = story_data.get('style_guide')
            style_context = ""
            if style_data:
                art_style = style_data.get('art_style', {})
                style_context = f"""Art style requirements (MUST follow exactly):
                - Style: {art_style.get('overall_style', '')}
                - Colors: {art_style.get('color_palette', '')}
                - Lighting: {art_style.get('lighting', '')}
                - Composition: {art_style.get('composition', '')}
                - Texture: {art_style.get('texture', '')}
                - Perspective: {art_style.get('perspective', '')}"""

            paragraphs_json = json.dumps(story_data['paragraphs'], indent=2)
            char_db_json = json.dumps(char_db, indent=2)

            prompt_for_gemini = prompt_template.format(
                paragraphs_json=paragraphs_json, 
                char_db_json=char_db_json, 
                style_context=style_context,
                num_paragraphs=num_paragraphs
            )
            
            safety_settings = {
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            }

            image_prompts_response = await generate_with_fallback(prompt_for_gemini, safety_settings=safety_settings)
            if not image_prompts_response:
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

            return cleaned_prompts
        except (json.JSONDecodeError, ValueError) as e:
            print(f"--- Image Prompt Generation: Attempt {attempt + 1} failed: {e} ---")
            if attempt < 2:
                print("--- Retrying... ---")
            continue

    return [None] * len(story_data['paragraphs'])
