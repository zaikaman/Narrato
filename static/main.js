        document.addEventListener('touchstart', function(event) {
    if (event.touches.length > 1) {
        event.preventDefault();
    }
}, { passive: false });

document.addEventListener('touchmove', function(event) {
    if (event.touches.length > 1) {
        event.preventDefault();
    }
}, { passive: false });

document.addEventListener('touchend', function(event) {
    if (event.touches.length > 1) {
        event.preventDefault();
    }
}, { passive: false });

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
            const icon = task.querySelector('.task-icon');
            icon.className = `task-icon ${status}`;
        }

        document.getElementById('storyForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            const gamePrompt = document.getElementById('game-prompt');
            
            loading.classList.remove('hidden');
            result.classList.add('hidden');
            gamePrompt.classList.remove('hidden');
            
            // Reset progress
            completedTasks = 0;
            updateProgress('Creating story...', 0);
            updateTaskStatus('task1', 'in-progress');
            updateTaskStatus('task2', 'pending');
            updateTaskStatus('task3', 'pending');
            
            const formData = new FormData(e.target);
            const prompt = formData.get('prompt');
            const imageMode = formData.get('imageMode');
            const public = formData.get('public') === 'on';
            const minParagraphs = formData.get('minParagraphs');
            const maxParagraphs = formData.get('maxParagraphs');

            const eventSource = new EventSource(`/generate_story_stream?prompt=${prompt}&imageMode=${imageMode}&minParagraphs=${minParagraphs}&maxParagraphs=${maxParagraphs}&public=${public}`);

            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);

                if (data.error) {
                    console.error('Error:', data.error);
                    alert('An error occurred while creating the story');
                    updateTaskStatus('task1', 'error');
                    updateTaskStatus('task2', 'error');
                    updateTaskStatus('task3', 'error');
                    eventSource.close();
                    loading.classList.add('hidden');
                    return;
                }

                updateProgress(data.task, data.progress, data.total);

                if (data.task.includes('Creating story content')) {
                    updateTaskStatus('task1', 'in-progress');
                } else if (data.task.includes('Story content generated')) {
                    updateTaskStatus('task1', 'completed');
                    updateTaskStatus('task2', 'in-progress');
                } else if (data.task.includes('Generating image prompts')) {
                    updateTaskStatus('task2', 'completed');
                    updateTaskStatus('task3', 'in-progress');
                } else if (data.task.includes('Generating image')) {
                    updateTaskStatus('task3', 'in-progress');
                }

                if (data.task === 'Finished!') {
                    updateTaskStatus('task1', 'completed');
                    updateTaskStatus('task2', 'completed');
                    updateTaskStatus('task3', 'completed');
                    displayResults(data.data);
                    eventSource.close();
                    loading.classList.add('hidden');
                    stopGame(); // Stop the game
                    document.getElementById('game-container').classList.add('hidden');
                }
            };

            eventSource.onerror = function(err) {
                console.error("EventSource failed:", err);
                alert('An error occurred while creating the story');
                updateTaskStatus('task1', 'error');
                updateTaskStatus('task2', 'error');
                updateTaskStatus('task3', 'error');
                eventSource.close();
                loading.classList.add('hidden');
            };
        });

        document.getElementById('play-game-yes').addEventListener('click', () => {
            document.getElementById('game-prompt').classList.add('hidden');
            document.getElementById('game-container').classList.remove('hidden');
            startGame();
        });

        document.getElementById('play-game-no').addEventListener('click', () => {
            document.getElementById('game-prompt').classList.add('hidden');
        });

        function displayResults(data) {
            console.log(data);
            const storyId = data.story_uuid;
            const modal = document.getElementById('story-ready-modal');
            modal.style.display = 'block';

            document.getElementById('view-story-btn').onclick = () => {
                window.location.href = `/view_story/${storyId}`;
            };
        }

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