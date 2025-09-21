from flask import Blueprint, request, jsonify, session
import os
import uuid
import asyncio
import traceback
from shov_api import shov_add, shov_where, shov_update
from generation import generate_story_content, generate_style_guide, analyze_story_characters, generate_all_image_prompts, generate_image, generate_voice

api_bp = Blueprint('api', __name__)

@api_bp.route('/start-story-generation', methods=['POST'])
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


@api_bp.route('/generation-status/<task_uuid>')
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


@api_bp.route('/api/run-worker', methods=['POST'])
def run_worker():
    """
    A state-machine worker with a locking mechanism to prevent race conditions.
    """
    auth_header = request.headers.get('Authorization')
    worker_secret = os.getenv('WORKER_SECRET')
    if not worker_secret or auth_header != f"Bearer {worker_secret}":
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    task_item = None
    processing_tasks_response = shov_where('generation_tasks', {'status': 'processing'})
    if processing_tasks_response.get('items'):
        for item in processing_tasks_response['items']:
            if not item.get('value', {}).get('generation_step', '').endswith('_inprogress'):
                task_item = item
                break
    
    if not task_item:
        pending_tasks_response = shov_where('generation_tasks', {'status': 'pending'})
        if pending_tasks_response.get('items'):
            task_item = pending_tasks_response['items'][0]

    if not task_item:
        return jsonify({"success": True, "message": "No ready tasks to process."} )

    task_id = task_item['id']
    task_data = task_item['value']

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
