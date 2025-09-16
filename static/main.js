        let currentAudio = null;
        let isPlaying = false;
        let totalTasks = 32;
        let completedTasks = 0;

        // Add validation for the number input fields
        const minParagraphsInput = document.getElementById('minParagraphs');
        const maxParagraphsInput = document.getElementById('maxParagraphs');

        function validateInputs() {
            // Make sure min is not greater than max
            let minVal = parseInt(minParagraphsInput.value);
            let maxVal = parseInt(maxParagraphsInput.value);
            
            if (minVal > maxVal) {
                maxParagraphsInput.value = minVal;
            }
            
            // Make sure the values are within the allowed range
            minParagraphsInput.value = Math.max(5, Math.min(100, minVal));
            maxParagraphsInput.value = Math.max(5, Math.min(100, maxVal));
        }

        // Add event listeners for the input fields
        minParagraphsInput.addEventListener('change', validateInputs);
        maxParagraphsInput.addEventListener('change', validateInputs);

        function updateProgress(task, progress, total) {
            document.getElementById('currentTask').textContent = task;
            // If total is provided, use it, otherwise use totalTasks
            const totalToUse = total || totalTasks;
            const percentage = Math.round((progress / totalToUse) * 100);
            document.getElementById('progressBar').style.width = `${percentage}%`;
            document.getElementById('progressText').textContent = `${percentage}%`;
        }

        function updateTaskStatus(taskId, status) {
            const task = document.getElementById(taskId);
            const icon = task.querySelector('i');
            icon.className = 'fas mr-2 ' + 
                (status === 'pending' ? 'fa-circle text-xs' :
                 status === 'in-progress' ? 'fa-spinner fa-spin' :
                 status === 'completed' ? 'fa-check text-green-500' :
                 'fa-times text-red-500');
        }

        document.getElementById('storyForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            
            loading.classList.remove('hidden');
            result.classList.add('hidden');
            
            // Reset progress
            completedTasks = 0;
            updateProgress('Creating story...', 0);
            updateTaskStatus('task1', 'in-progress');
            updateTaskStatus('task2', 'pending');
            updateTaskStatus('task3', 'pending');
            
            const formData = new FormData(e.target);
            
            try {
                const response = await fetch('/generate_story', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                // Update totalTasks based on the actual number of paragraphs
                const actualTotalTasks = data.paragraphs.length + 2; // paragraphs + story + final processing
                
                // Update progress for the story
                updateProgress('Finished creating the story', 1, actualTotalTasks);
                updateTaskStatus('task1', 'completed');
                updateTaskStatus('task2', 'in-progress');
                
                // Display the results
                document.getElementById('storyTitle').textContent = data.title;
                
                const storyContent = document.getElementById('storyContent');
                storyContent.innerHTML = '';
                
                // Update progress for each image
                data.paragraphs.forEach((paragraph, index) => {
                    const section = document.createElement('div');
                    section.className = 'flex flex-col md:flex-row gap-6 items-center p-4 border rounded-lg mb-8';
                    
                    // Add image and view prompt button
                    if (data.images && data.images[index]) {
                        const imgContainer = document.createElement('div');
                        imgContainer.className = 'w-full md:w-1/2 relative';
                        
                        if (data.images[index].url) {
                            const img = document.createElement('img');
                            img.src = data.images[index].url;
                            img.className = 'w-full h-auto rounded-lg shadow-lg';
                            img.alt = `Illustration ${index + 1}`;
                            imgContainer.appendChild(img);
                        }

                        // Display the prompt
                        const promptContainer = document.createElement('div');
                        promptContainer.className = 'mt-2';
                        
                        if (!data.images[index].url) {
                            // If there is no URL (prompt-only mode), display the prompt directly
                            const promptText = document.createElement('div');
                            promptText.className = 'bg-gray-50 p-4 rounded-lg text-sm text-gray-700 whitespace-pre-wrap';
                            promptText.textContent = data.images[index].prompt;
                            promptContainer.appendChild(promptText);

                            // Add a copy button
                            const copyBtn = document.createElement('button');
                            copyBtn.className = 'mt-2 bg-gray-200 text-gray-700 px-3 py-1 rounded-full hover:bg-gray-300 transition-all text-sm';
                            copyBtn.innerHTML = '<i class="fas fa-copy mr-1"></i>Copy prompt';
                            copyBtn.onclick = () => {
                                navigator.clipboard.writeText(data.images[index].prompt);
                                copyBtn.innerHTML = '<i class="fas fa-check mr-1"></i>Copied';
                                setTimeout(() => {
                                    copyBtn.innerHTML = '<i class="fas fa-copy mr-1"></i>Copy prompt';
                                }, 2000);
                            };
                            promptContainer.appendChild(copyBtn);
                        } else {
                            // If there is a URL (image generation mode), display the view prompt button
                            const promptBtn = document.createElement('button');
                            promptBtn.className = 'absolute top-2 right-2 bg-white bg-opacity-75 hover:bg-opacity-100 text-gray-700 px-3 py-1 rounded-full shadow-md transition-all';
                            promptBtn.innerHTML = '<i class="fas fa-info-circle mr-1"></i>View prompt';
                            promptBtn.onclick = () => showPrompt(data.images[index].prompt);
                            imgContainer.appendChild(promptBtn);
                        }
                        
                        imgContainer.appendChild(promptContainer);
                        section.appendChild(imgContainer);
                        updateProgress(`Creating image ${index + 1}/${data.paragraphs.length}...`, 2 + index, actualTotalTasks);
                    }
                    
                    // Add the paragraph
                    const textContainer = document.createElement('div');
                    textContainer.className = 'w-full md:w-1/2 space-y-4';
                    
                    const p = document.createElement('p');
                    p.className = 'text-lg leading-relaxed';
                    p.textContent = paragraph;
                    textContainer.appendChild(p);
                    
                    if (data.audio_files && data.audio_files[index]) {
                        const audioBtn = document.createElement('button');
                        audioBtn.className = 'bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500';
                        audioBtn.innerHTML = '<i class="fas fa-play mr-2"></i>Play this part';
                        audioBtn.onclick = () => playAudio(data.audio_files[index]);
                        textContainer.appendChild(audioBtn);
                    }
                    
                    section.appendChild(textContainer);
                    storyContent.appendChild(section);
                });
                
                document.getElementById('moralText').textContent = data.moral;
                
                // Finished
                updateProgress('Finished!', actualTotalTasks, actualTotalTasks);
                updateTaskStatus('task2', 'completed');
                updateTaskStatus('task3', 'completed');
                
                result.classList.remove('hidden');
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred while creating the story');
                updateTaskStatus('task1', 'error');
                updateTaskStatus('task2', 'error');
                updateTaskStatus('task3', 'error');
            } finally {
                loading.classList.add('hidden');
            }
        });

        // Audio handling
        function playAudio(audioUrl) {
            if (currentAudio) {
                currentAudio.pause();
            }
            currentAudio = new Audio(audioUrl);
            currentAudio.play();
            isPlaying = true;
            updatePlayPauseButtons();
        }

        function pauseAudio() {
            if (currentAudio) {
                currentAudio.pause();
                isPlaying = false;
                updatePlayPauseButtons();
            }
        }

        function updatePlayPauseButtons() {
            const playAllBtn = document.getElementById('playAll');
            const pauseAllBtn = document.getElementById('pauseAll');
            
            if (isPlaying) {
                playAllBtn.classList.add('hidden');
                pauseAllBtn.classList.remove('hidden');
            } else {
                playAllBtn.classList.remove('hidden');
                pauseAllBtn.classList.add('hidden');
            }
        }

        document.getElementById('playAll').onclick = () => {
            // Handle playing all audio
            const audioFiles = document.querySelectorAll('audio');
            if (audioFiles.length > 0) {
                let currentIndex = 0;
                
                function playNext() {
                    if (currentIndex < audioFiles.length) {
                        const audio = audioFiles[currentIndex];
                        currentAudio = audio;
                        isPlaying = true;
                        updatePlayPauseButtons();
                        
                        audio.onended = () => {
                            currentIndex++;
                            playNext();
                        };
                        
                        audio.play();
                    } else {
                        isPlaying = false;
                        updatePlayPauseButtons();
                    }
                }
                
                playNext();
            }
        };
        
        document.getElementById('pauseAll').onclick = pauseAudio;

        // Add modal handling functions
        function showPrompt(prompt) {
            const modal = document.getElementById('promptModal');
            const promptText = document.getElementById('promptText');
            promptText.textContent = prompt;
            modal.style.display = 'block';
        }

        // Close the modal when the close button is clicked
        document.querySelector('.close').onclick = function() {
            document.getElementById('promptModal').style.display = 'none';
        }

        // Close the modal when clicking outside of it
        window.onclick = function(event) {
            const modal = document.getElementById('promptModal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }