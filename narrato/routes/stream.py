from flask import Blueprint, request, Response, session
import asyncio
import json
import traceback
from ..services.shov_api import shov_where, shov_update, shov_add, shov_remove
from ..services.generation import generate_story_content, generate_style_guide, analyze_story_characters, generate_all_image_prompts, generate_image, generate_voice

stream_bp = Blueprint('stream', __name__)

# Define a semaphore to limit concurrent thread-based tasks
CONCURRENCY_LIMIT = 4 # A safe number for a small Heroku dyno
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

async def generate_story_for_stream(prompt, image_mode, min_paragraphs, max_paragraphs, email, public, story_uuid=None):
    """Generate story and stream progress, with state saving."""
    
    def progress_update(task, step, total, data=None):
        return {"task": task, "progress": step, "total": total, "data": data}

    try:
        step = 0
        state_data = {}
        shov_id = None

        if story_uuid:
            response = None
            for _ in range(3):
                response = shov_where('stream_progress', {'story_uuid': story_uuid})
                if response and response.get('items'):
                    break
                await asyncio.sleep(0.5)

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
                yield progress_update('Analyzing story elements...', 15, 100)
                style_task = generate_style_guide(story_data)
                chars_task = analyze_story_characters(story_data)
                
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
                if image_mode == 'generate':
                    yield progress_update('Generating images...', 40, 100)
                    image_data = story_data.get('images', [])
                    num_prompts = len(image_prompts)
                    start_index = len(image_data)
                    for i, p in enumerate(image_prompts[start_index:], start=start_index):
                        progress = 40 + int(30 * (i + 1) / num_prompts)
                        yield progress_update(f'Waiting for image slot {i + 1} of {num_prompts}...', progress, 100)
                        async with semaphore:
                            yield progress_update(f'Generating image {i + 1} of {num_prompts}...', progress, 100)
                            image_task = asyncio.create_task(generate_image(p))
                            while not image_task.done():
                                try:
                                    await asyncio.wait_for(asyncio.shield(image_task), timeout=15)
                                except asyncio.TimeoutError:
                                    yield progress_update(f'Generating image {i + 1} of {num_prompts}... (ping)', progress, 100)
                            image_url = await image_task
                        
                        image_data.append({'url': image_url, 'prompt': p})
                        story_data['images'] = image_data
                        save_progress(3, {'story_data': story_data, 'image_prompts': image_prompts})
                        yield progress_update(f'Generated image {i + 1} of {num_prompts}', progress, 100, story_data)
                else:
                    story_data['images'] = [{'prompt': p, 'url': None} for p in image_prompts]
                    yield progress_update('Skipping image generation', 70, 100)
                
                save_progress(4, {'story_data': story_data, 'image_prompts': image_prompts})
                step = 4
            elif step == 4:
                yield progress_update('Generating audio files...', 75, 100)
                audio_files = story_data.get('audio_files', [])
                texts_to_voice = [story_data['title']] + story_data['paragraphs']
                num_texts = len(texts_to_voice)
                start_index = len(audio_files)
                for i, text in enumerate(texts_to_voice[start_index:], start=start_index):
                    progress = 75 + int(20 * (i + 1) / num_texts)
                    yield progress_update(f'Waiting for audio slot {i + 1} of {num_texts}...', progress, 100)
                    async with semaphore:
                        yield progress_update(f'Generating audio {i + 1} of {num_texts}...', progress, 100)
                        audio_task = asyncio.create_task(generate_voice(text))
                        while not audio_task.done():
                            try:
                                await asyncio.wait_for(asyncio.shield(audio_task), timeout=15)
                            except asyncio.TimeoutError:
                                yield progress_update(f'Generated audio {i + 1} of {num_texts}... (ping)', progress, 100)
                        audio_url = await audio_task

                    audio_files.append(audio_url)
                    story_data['audio_files'] = audio_files
                    await asyncio.sleep(1)
                    save_progress(4, {'story_data': story_data, 'image_prompts': image_prompts})
                    yield progress_update(f'Generated audio {i + 1} of {num_texts}', progress, 100, {'audio_file': audio_url, 'index': i})

                save_progress(5, {'story_data': story_data, 'image_prompts': image_prompts})
                step = 5
            elif step == 5:
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

@stream_bp.route('/generate_story_stream', methods=['GET'])
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
