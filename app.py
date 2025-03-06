from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
import os
import google.generativeai as genai
from elevenlabs.client import ElevenLabs
import json
import tempfile
import moviepy.video.io.ImageSequenceClip as ImageSequenceClip
import moviepy.audio.io.AudioFileClip as AudioFileClip
import moviepy.video.compositing.CompositeVideoClip as CompositeVideoClip
import fal_client
import asyncio
from asgiref.sync import sync_to_async
import re
import traceback

app = Flask(__name__)
load_dotenv()

# Cấu hình API keys
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
FAL_KEY = os.getenv('FAL_KEY')

genai.configure(api_key=GOOGLE_API_KEY)
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
os.environ["FAL_KEY"] = FAL_KEY

async def generate_image(prompt):
    """Tạo hình ảnh từ prompt sử dụng FAL.ai"""
    try:
        print(f"\n=== Bắt đầu generate_image ===")
        print(f"Input prompt: {prompt}")
        
        # Đảm bảo prompt là string và không quá dài
        if isinstance(prompt, dict):
            prompt = str(prompt)
        
        # Giới hạn độ dài prompt và làm sạch
        prompt = prompt[:500]
        prompt = re.sub(r'["\'\n]', '', prompt)
        
        # Thêm style vào prompt
        enhanced_prompt = f"{prompt}, digital art style, high quality, detailed, vibrant colors"
        print(f"Enhanced prompt: {enhanced_prompt}")

        # Tạo request
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
            print("=== Kết thúc generate_image ===\n")
            return image_url
            
        print(f"Invalid result format: {result}")
        print("=== Kết thúc generate_image với lỗi ===\n")
        return None
        
    except Exception as e:
        print(f"Lỗi khi tạo hình ảnh: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        print("=== Kết thúc generate_image với exception ===\n")
        return None

@sync_to_async
def generate_voice(text, voice_id="pNInz6obpgDQGcFmaJgB"):
    """Tạo giọng đọc từ văn bản sử dụng ElevenLabs"""
    try:
        # Tạo audio stream từ text
        audio_stream = elevenlabs_client.text_to_speech.convert_as_stream(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2"
        )
        
        # Lưu audio stream vào file tạm thời
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        
        # Ghi từng chunk vào file
        for chunk in audio_stream:
            if isinstance(chunk, bytes):
                temp_file.write(chunk)
        
        temp_file.close()
        return temp_file.name
    except Exception as e:
        print(f"Lỗi khi tạo giọng đọc: {str(e)}")
        return None

@sync_to_async
def generate_story_content(prompt):
    """Tạo nội dung câu chuyện bằng Gemini"""
    try:
        print(f"\n=== Bắt đầu generate_story_content ===")
        print(f"Input prompt: {prompt}")
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        print("Đã khởi tạo model Gemini")
        
        print("Gửi yêu cầu tạo câu chuyện...")
        english_story_response = model.generate_content(f"""
        You are a storyteller writing for a general audience. Create a story based on this theme: {prompt}

        IMPORTANT WRITING GUIDELINES:
        1. Use simple, everyday language that everyone can understand
        2. Avoid complex vocabulary or literary devices
        3. Write short, clear sentences
        4. Use common words instead of sophisticated alternatives
        5. Keep the narrative straightforward and easy to follow
        6. Write as if you're telling the story to a friend
        7. Aim for a reading level suitable for ages 12 and up
        8. Focus on making the story engaging through the plot, not complex language

        Return the story in this EXACT JSON format, with NO additional text or formatting:
        {{
            "title": "Story Title",
            "paragraphs": [
                "First paragraph text",
                "Second paragraph text",
                ... (between 30-50 paragraphs)
            ],
            "moral": "The moral lesson from the story"
        }}

        IMPORTANT FORMAT RULES:
        - Do NOT add trailing commas after the last item in arrays or objects
        - Each paragraph should be 2-3 simple sentences
        - Story should match the theme: {prompt}
        - Return ONLY the JSON object, no other text
        - Number of paragraphs should be between 30 and 50
        - The story should feel complete, don't force it to exactly 50 paragraphs
        """)
        
        print("Đã nhận response từ Gemini")
        
        # Lấy text response và làm sạch
        response_text = english_story_response.text.strip()
        print(f"Raw response: {response_text}")
        
        # Loại bỏ markdown code blocks
        response_text = re.sub(r'```(?:json)?\s*|\s*```', '', response_text, flags=re.MULTILINE)
        
        # Loại bỏ dấu phẩy thừa sau phần tử cuối của mảng và object
        response_text = re.sub(r',(\s*[\]}])', r'\1', response_text)
        response_text = re.sub(r',\s*"moral":', r',"moral":', response_text)
        
        # Loại bỏ khoảng trắng thừa và format lại JSON
        response_text = re.sub(r'\s+', ' ', response_text)
        print(f"Cleaned response: {response_text}")
        
        try:
            # Thử parse JSON
            print("Parsing JSON...")
            story_data = json.loads(response_text)
            print("JSON parsed successfully")
            
            # Kiểm tra cấu trúc JSON
            if not all(key in story_data for key in ['title', 'paragraphs', 'moral']):
                raise ValueError("Missing required fields in story data")
            
            # Đảm bảo số lượng đoạn văn nằm trong khoảng 30-50
            num_paragraphs = len(story_data['paragraphs'])
            if num_paragraphs > 50:
                print(f"Trimming paragraphs from {num_paragraphs} to 50")
                story_data['paragraphs'] = story_data['paragraphs'][:50]
            elif num_paragraphs < 30:
                print(f"Adding paragraphs to reach minimum 30 (current: {num_paragraphs})")
                while len(story_data['paragraphs']) < 30:
                    story_data['paragraphs'].append("And the story continues...")
            
            print(f"Final number of paragraphs: {len(story_data['paragraphs'])}")
            print("=== Kết thúc generate_story_content thành công ===\n")
            return story_data
                
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error processing story: {str(e)}")
            print("=== Kết thúc generate_story_content với lỗi parsing ===\n")
            return {
                "title": "Error Creating Story",
                "paragraphs": ["We encountered an error while creating your story."] * 30,
                "moral": "Sometimes we need to be patient and try again."
            }
    except Exception as e:
        print(f"Generate story error: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        print("=== Kết thúc generate_story_content với exception ===\n")
        raise

@sync_to_async
def generate_image_prompt(paragraph, story_data=None, paragraph_index=0, previous_prompts=None):
    """Tạo prompt cho hình ảnh bằng Gemini, với thông tin về nhân vật để giữ tính nhất quán"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Khởi tạo style guide chung cho toàn bộ câu chuyện
        if paragraph_index == 0 and story_data:
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
                # Làm sạch response text
                style_text = style_guide.text.strip()
                # Loại bỏ markdown code blocks nếu có
                style_text = re.sub(r'```(?:json)?\s*|\s*```', '', style_text)
                print(f"Style guide response: {style_text}")
                
                style_data = json.loads(style_text)
                if not style_data.get('art_style'):
                    raise ValueError("Missing art_style in response")
                    
                story_data['style_guide'] = style_data
                print("Successfully parsed style guide")
            except Exception as e:
                print(f"Could not parse style guide: {str(e)}")
                print(f"Raw response: {style_guide.text}")
                style_data = {
                    "art_style": {
                        "overall_style": "Digital art style with realistic details",
                        "color_palette": "Rich, vibrant colors with deep contrasts",
                        "lighting": "Dramatic lighting with strong highlights and shadows",
                        "composition": "Dynamic, cinematic compositions",
                        "texture": "Detailed textures with fine grain",
                        "perspective": "Varied angles to enhance dramatic effect"
                    }
                }
                story_data['style_guide'] = style_data

            # Phân tích nhân vật chi tiết hơn
            character_analysis = model.generate_content(f"""
            Analyze ALL characters that appear in this story. Read through the entire story carefully:
            Title: {story_data['title']}
            Story: {' '.join(story_data['paragraphs'])}

            Return ONLY a JSON object in this format, no other text:
            {{
                "main_character": {{
                    "name": "Character name",
                    "age": "Specific age",
                    "gender": "Character gender",
                    "physical_traits": {{
                        "height": "Height description",
                        "build": "Body build description",
                        "hair": "Detailed hair description including style and color",
                        "eyes": "Eye color and shape",
                        "skin": "Skin tone and texture",
                        "face_shape": "Detailed face shape description",
                        "distinctive_features": "Any unique identifying marks or features"
                    }},
                    "clothing": {{
                        "style": "Overall clothing style",
                        "main_outfit": "Detailed description of typical outfit",
                        "color_scheme": "Consistent colors in clothing",
                        "accessories": "Regular accessories worn"
                    }},
                    "personality_reflection": "How personality should be reflected in appearance and poses"
                }},
                "supporting_characters": [
                    {{
                        "name": "Character name",
                        "relationship": "Relationship to main character",
                        "physical_traits": {{
                            "height": "Height description",
                            "build": "Body build description",
                            "hair": "Hair details",
                            "face": "Face description",
                            "distinctive_features": "Unique features"
                        }},
                        "clothing": {{
                            "style": "Character's clothing style",
                            "color_scheme": "Consistent colors"
                        }}
                    }}
                ]
            }}
            """)
            
            try:
                # Làm sạch response text
                char_text = character_analysis.text.strip()
                # Loại bỏ markdown code blocks nếu có
                char_text = re.sub(r'```(?:json)?\s*|\s*```', '', char_text)
                print(f"Character analysis response: {char_text}")
                
                char_data = json.loads(char_text)
                if not char_data.get('main_character'):
                    raise ValueError("Missing main_character in response")
                if not char_data.get('supporting_characters'):
                    raise ValueError("Missing supporting_characters in response")
                    
                story_data['character_info'] = char_data
                print("Successfully parsed character analysis")
            except Exception as e:
                print(f"Could not parse character analysis: {str(e)}")
                print(f"Raw response: {character_analysis.text}")
                # Tạo dữ liệu mặc định từ nội dung câu chuyện
                char_data = {
                    "main_character": {
                        "name": "King Alaric",
                        "age": "young",
                        "gender": "male",
                        "physical_traits": {
                            "height": "tall and imposing",
                            "build": "strong and regal",
                            "hair": "well-groomed auburn hair",
                            "eyes": "piercing blue eyes",
                            "skin": "fair and smooth",
                            "face_shape": "noble features with strong jawline",
                            "distinctive_features": "carries himself with royal bearing"
                        },
                        "clothing": {
                            "style": "royal and elegant",
                            "main_outfit": "ornate royal robes with gold trim",
                            "color_scheme": "deep blues and rich golds",
                            "accessories": "golden crown and royal signet ring"
                        },
                        "personality_reflection": "regal bearing with hints of inner turmoil"
                    },
                    "supporting_characters": [
                        {
                            "name": "Sir Kaelen",
                            "relationship": "loyal knight and confidant",
                            "physical_traits": {
                                "height": "tall and athletic",
                                "build": "strong and battle-hardened",
                                "hair": "silver-streaked dark hair",
                                "face": "noble and determined",
                                "distinctive_features": "battle scars and proud bearing"
                            },
                            "clothing": {
                                "style": "polished plate armor with royal insignia",
                                "color_scheme": "silver and blue"
                            }
                        }
                    ]
                }
                story_data['character_info'] = char_data
            story_data['previous_prompts'] = []  # Thêm list để lưu lịch sử prompts
        
        # Lấy lịch sử prompts từ story_data
        previous_prompts = story_data.get('previous_prompts', []) if story_data else []
        
        # Tạo context từ lịch sử prompts
        prompt_history_context = ""
        if previous_prompts:
            prompt_history_context = f"""
            Previous image prompts for consistency (numbered in sequence):
            {chr(10).join(f"{i+1}. {prompt}" for i, prompt in enumerate(previous_prompts))}
            """

        char_data = story_data.get('character_info') if story_data else None
        style_data = story_data.get('style_guide') if story_data else None

        # Tạo prompt chi tiết với thông tin nhân vật và style guide
        character_context = ""
        style_context = ""
        
        if char_data:
            main_char = char_data.get('main_character', {})
            physical_traits = main_char.get('physical_traits', {})
            clothing = main_char.get('clothing', {})
            
            # Phân tích đoạn văn để xác định nhân vật xuất hiện
            character_mention_analysis = model.generate_content(f"""
            Analyze this paragraph and identify which characters appear in it:
            {paragraph}

            Return ONLY a JSON array of character names, no other text:
            ["Character1", "Character2", ...]
            """)
            
            try:
                mentioned_characters = json.loads(character_mention_analysis.text)
            except:
                mentioned_characters = []

            # Tạo mô tả chi tiết cho mỗi nhân vật xuất hiện trong đoạn
            character_descriptions = []
            
            # Kiểm tra nhân vật chính
            main_char_name = main_char.get('name', '')
            if main_char_name in mentioned_characters:
                character_descriptions.append(f"""
                {main_char_name}: {main_char.get('age', '')} year old {main_char.get('gender', '')}, 
                {physical_traits.get('height', '')}, {physical_traits.get('build', '')}, 
                with {physical_traits.get('hair', '')} and {physical_traits.get('eyes', '')} eyes,
                {physical_traits.get('skin', '')} skin tone, {physical_traits.get('face_shape', '')} face,
                {physical_traits.get('distinctive_features', '')}.
                Wearing {clothing.get('main_outfit', '')}, {clothing.get('accessories', '')}.
                Their expression and pose reflect {main_char.get('personality_reflection', '')}.
                """.strip())

            # Kiểm tra các nhân vật phụ
            for char in char_data.get('supporting_characters', []):
                char_name = char.get('name', '')
                if char_name in mentioned_characters:
                    char_traits = char.get('physical_traits', {})
                    char_clothing = char.get('clothing', {})
                    character_descriptions.append(f"""
                    {char_name}: {char.get('relationship', '')},
                    {char_traits.get('height', '')}, {char_traits.get('build', '')},
                    with {char_traits.get('hair', '')} and {char_traits.get('face', '')},
                    {char_traits.get('distinctive_features', '')}.
                    Wearing {char_clothing.get('style', '')} in {char_clothing.get('color_scheme', '')}.
                    """.strip())

            character_context = "Character descriptions (MUST be followed exactly):\n" + "\n\n".join(character_descriptions) if character_descriptions else ""

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
            
        # Tạo prompt với mô tả nhân vật đầy đủ và lịch sử prompts
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
        # Loại bỏ dấu ngoặc kép và ký tự đặc biệt
        prompt = re.sub(r'["\'\n]', '', prompt)
        
        # Lưu prompt vào lịch sử
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
        print(f"Lỗi khi phục vụ file audio: {str(e)}")
        return jsonify({"error": "Không thể phát file âm thanh"}), 404

@app.route('/generate_story', methods=['POST'])
async def generate_story():
    print("\n=== Bắt đầu generate_story endpoint ===")
    prompt = request.form.get('prompt')
    image_mode = request.form.get('imageMode', 'generate')  # Mặc định là tạo ảnh
    print(f"Received prompt: {prompt}")
    print(f"Image mode: {image_mode}")
    
    try:
        # Tạo nội dung câu chuyện
        print("Generating story content...")
        story_data = await generate_story_content(prompt)
        story_data['previous_prompts'] = []  # Khởi tạo list lưu lịch sử prompts
        print("Story content generated successfully")
        
        # Tạo prompts cho hình ảnh theo batch để tránh rate limit
        print("Generating image prompts...")
        image_prompts = []
        batch_size_gemini = 5  # Số lượng prompt tạo trước khi nghỉ
        
        for i in range(0, len(story_data['paragraphs']), batch_size_gemini):
            batch_paragraphs = story_data['paragraphs'][i:i + batch_size_gemini]
            print(f"\nProcessing prompt batch {i//batch_size_gemini + 1}/{len(story_data['paragraphs'])//batch_size_gemini + 1}...")
            
            # Tạo prompt cho batch hiện tại
            batch_prompts = []
            for j, paragraph in enumerate(batch_paragraphs):
                print(f"Generating prompt for paragraph {i + j + 1}...")
                prompt = await generate_image_prompt(paragraph, story_data, i + j)
                print(f"Generated prompt: {prompt}")
                batch_prompts.append(prompt)
            
            image_prompts.extend(batch_prompts)
            
            # Nghỉ 45 giây sau mỗi batch trừ batch cuối
            if i + batch_size_gemini < len(story_data['paragraphs']):
                print("Waiting 45 seconds before next batch of prompts...")
                await asyncio.sleep(45)

        # Nếu chỉ tạo prompt, không gọi API tạo ảnh
        if image_mode == 'prompt':
            print("Prompt-only mode, skipping image generation")
            image_data = [{'prompt': prompt, 'url': None} for prompt in image_prompts]
        else:
            # Tạo hình ảnh song song, chia thành các nhóm nhỏ để tránh quá tải
            print("\nGenerating images...")
            batch_size_fal = 5  # Số lượng ảnh tạo đồng thời
            image_data = []
            
            for i in range(0, len(image_prompts), batch_size_fal):
                batch_prompts = image_prompts[i:i + batch_size_fal]
                print(f"\nProcessing image batch {i//batch_size_fal + 1}/{len(image_prompts)//batch_size_fal + 1}...")
                
                batch_tasks = [generate_image(prompt) for prompt in batch_prompts]
                batch_results = await asyncio.gather(*batch_tasks)
                
                # Lọc bỏ các URL None và lưu cả prompt
                batch_data = []
                for url, prompt in zip(batch_results, batch_prompts):
                    if url is not None:
                        batch_data.append({
                            'url': url,
                            'prompt': prompt
                        })
                image_data.extend(batch_data)
                
                print(f"Batch {i//batch_size_fal + 1} completed: {len(batch_data)} images generated")
                
                # Đợi một chút giữa các batch để tránh quá tải API
                if i + batch_size_fal < len(image_prompts):
                    await asyncio.sleep(2)
            
            print(f"Total images generated: {len(image_data)}")
        
        # Thêm URLs hình ảnh và prompts vào response
        story_data['images'] = image_data
        
        # Không sử dụng ElevenLabs do giới hạn free tier
        story_data['audio_files'] = []
        
        print("=== Kết thúc generate_story endpoint thành công ===\n")
        return jsonify(story_data)
        
    except Exception as e:
        print(f"Error in generate_story endpoint: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        print("=== Kết thúc generate_story endpoint với lỗi ===\n")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 