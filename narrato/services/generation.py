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
    """Generates content using Gemini with model fallback and key rotation."""
    models = ['gemini-2.5-flash']
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
        cloudinary_url = upload_result.get("secure_url")
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

