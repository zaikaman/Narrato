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

// Add validation for the number input fields
const minParagraphsInput = document.getElementById('minParagraphs');
const maxParagraphsInput = document.getElementById('maxParagraphs');

function validateInputs() {
    let minVal = parseInt(minParagraphsInput.value);
    let maxVal = parseInt(maxParagraphsInput.value);
    
    if (minVal > maxVal) {
        maxParagraphsInput.value = minVal;
    }
    
    minParagraphsInput.value = Math.max(5, Math.min(100, minVal));
    maxParagraphsInput.value = Math.max(5, Math.min(100, maxVal));
}

minParagraphsInput.addEventListener('change', validateInputs);
maxParagraphsInput.addEventListener('change', validateInputs);

function updateProgress(task, progress, total) {
    document.getElementById('currentTask').textContent = task;
    const percentage = Math.round((progress / total) * 100);
    document.getElementById('progressBar').style.width = `${percentage}%`;
    document.getElementById('progressText').textContent = `${percentage}%`;
}

function updateTaskStatus(taskId, status) {
    const task = document.getElementById(taskId);
    if (task) {
        const icon = task.querySelector('.task-icon');
        icon.className = `task-icon ${status}`;
    }
}

function startPolling(taskUUID) {
    // Show the loading UI
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('result').classList.add('hidden');
    document.getElementById('game-prompt').classList.remove('hidden');
    document.getElementById('storyForm').classList.add('hidden');

    const pollInterval = setInterval(async () => {
        try {
            const statusResponse = await fetch(`/generation-status/${taskUUID}`);
            const statusData = await statusResponse.json();

            if (!statusData.success) {
                if (statusData.error === 'Task not found') {
                    alert('The story task you were tracking could not be found. It may have been completed or expired.');
                    localStorage.removeItem('activeTaskUUID');
                    clearInterval(pollInterval);
                    window.location.reload();
                    return;
                }
                throw new Error(statusData.error || 'Failed to get task status.');
            }

            updateProgress(statusData.task_message, statusData.progress, 100);

            if (statusData.progress < 10) {
                updateTaskStatus('task1', 'in-progress');
            } else if (statusData.progress >= 10 && statusData.progress < 20) {
                updateTaskStatus('task1', 'completed');
                updateTaskStatus('task2', 'in-progress');
            } else if (statusData.progress >= 20 && statusData.progress < 95) {
                updateTaskStatus('task2', 'completed');
                updateTaskStatus('task3', 'in-progress');
            } else if (statusData.progress >= 95) {
                updateTaskStatus('task3', 'completed');
            }

            if (statusData.status === 'completed' || statusData.status === 'failed') {
                clearInterval(pollInterval);
                localStorage.removeItem('activeTaskUUID');

                if (statusData.status === 'completed') {
                    updateTaskStatus('task1', 'completed');
                    updateTaskStatus('task2', 'completed');
                    updateTaskStatus('task3', 'completed');
                    displayResults(statusData.result);
                    document.getElementById('loading').classList.add('hidden');
                    if (window.stopGame) stopGame();
                    document.getElementById('game-container').classList.add('hidden');
                } else {
                    throw new Error(statusData.error || 'Story generation failed.');
                }
            }
        } catch (pollError) {
            clearInterval(pollInterval);
            localStorage.removeItem('activeTaskUUID');
            console.error("Polling failed:", pollError);
            alert(pollError.message);
            updateTaskStatus('task1', 'error');
            updateTaskStatus('task2', 'error');
            updateTaskStatus('task3', 'error');
            document.getElementById('loading').classList.add('hidden');
        }
    }, 3000);
}

document.getElementById('storyForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const prompt = formData.get('prompt');
    const imageMode = formData.get('imageMode');
    const isPublic = formData.get('public') === 'on';
    const minParagraphs = formData.get('minParagraphs');
    const maxParagraphs = formData.get('maxParagraphs');

    try {
        const startResponse = await fetch('/start-story-generation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt, imageMode, public: isPublic, minParagraphs, maxParagraphs
            }),
        });

        const startData = await startResponse.json();

        if (!startData.success) {
            throw new Error(startData.error || 'Failed to start story generation.');
        }

        const taskUUID = startData.task_uuid;
        localStorage.setItem('activeTaskUUID', taskUUID);
        startPolling(taskUUID);

    } catch (startError) {
        console.error("Starting generation failed:", startError);
        alert(startError.message);
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const activeTaskUUID = localStorage.getItem('activeTaskUUID');
    if (activeTaskUUID) {
        console.log('Resuming task:', activeTaskUUID);
        startPolling(activeTaskUUID);
    }
});

document.getElementById('play-game-yes').addEventListener('click', () => {
    document.getElementById('game-prompt').classList.add('hidden');
    document.getElementById('game-container').classList.remove('hidden');
    if (window.startGame) startGame();
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

function showPrompt(prompt) {
    const modal = document.getElementById('promptModal');
    const promptText = document.getElementById('promptText');
    promptText.textContent = prompt;
    modal.style.display = 'block';
}

document.querySelector('.close').onclick = function() {
    document.getElementById('promptModal').style.display = 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('promptModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}

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