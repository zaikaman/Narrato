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

from generation import generate_with_fallback


from key_manager import api_key_manager, speechify_api_key_manager, huggingface_api_key_manager

app = Flask(__name__)

from auth_routes import auth_bp
app.register_blueprint(auth_bp)
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
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# API keys are now managed by the APIKeyManager instances.
# Global configuration is removed to allow for dynamic key rotation per request.

from generation import generate_story_content, generate_style_guide, analyze_story_characters, generate_all_image_prompts, generate_image, generate_voice

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