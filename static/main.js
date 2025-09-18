document.addEventListener('DOMContentLoaded', () => {
    const isProduction = window.location.hostname.includes('vercel.app');

    // --- DOM Element Selectors ---
    const storyForm = document.getElementById('storyForm');
    const loading = document.getElementById('loading');
    const result = document.getElementById('result');
    const gamePrompt = document.getElementById('game-prompt');
    const minParagraphsInput = document.getElementById('minParagraphs');
    const maxParagraphsInput = document.getElementById('maxParagraphs');
    const currentTask = document.getElementById('currentTask');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const gameContainer = document.getElementById('game-container');
    const playYesBtn = document.getElementById('play-game-yes');
    const playNoBtn = document.getElementById('play-game-no');
    const storyReadyModal = document.getElementById('story-ready-modal');
    const viewStoryBtn = document.getElementById('view-story-btn');
    const promptModal = document.getElementById('promptModal');
    const closeModalBtn = document.querySelector('.close');

    // --- Core Functions ---

    function toggleForm(disabled) {
        const elements = [
            storyForm.querySelector('textarea[name="prompt"]'),
            storyForm.querySelector('select[name="imageMode"]'),
            storyForm.querySelector('input[name="public"]'),
            minParagraphsInput,
            maxParagraphsInput,
            storyForm.querySelector('button[type="submit"]'),
            storyForm.querySelector('input[type="submit"]')
        ];

        elements.forEach(el => {
            if (el) {
                el.disabled = disabled;
            }
        });
    }

    function updateProgress(task, progress, total) {
        currentTask.textContent = task;
        const percentage = Math.round((progress / total) * 100);
        progressBar.style.width = `${percentage}%`;
        progressText.textContent = `${percentage}%`;
    }

    function updateTaskStatus(taskId, status) {
        const task = document.getElementById(taskId);
        if (task) {
            const icon = task.querySelector('.task-icon');
            icon.className = `task-icon ${status}`;
        }
    }

    function displayResults(data) {
        if (!data || !data.story_uuid) {
            console.error("Invalid data passed to displayResults", data);
            alert("An error occurred while trying to display the story results.");
            return;
        }
        const storyId = data.story_uuid;
        storyReadyModal.style.display = 'block';
        viewStoryBtn.onclick = () => {
            window.location.href = `/view_story/${storyId}`;
        };
    }

    // --- Production Mode (Polling) Functions ---

    function startPolling(taskUUID) {
        toggleForm(true);
        loading.classList.remove('hidden');
        result.classList.add('hidden');
        gamePrompt.classList.remove('hidden');

        const pollInterval = setInterval(async () => {
            try {
                const statusResponse = await fetch(`/generation-status/${taskUUID}`);
                if (!statusResponse.ok) throw new Error(`Server error: ${statusResponse.status}`);
                const statusData = await statusResponse.json();

                if (!statusData.success) {
                    if (statusData.error === 'Task not found') {
                        alert('The story task could not be found.');
                        localStorage.removeItem('activeTaskUUID');
                        clearInterval(pollInterval);
                        toggleForm(false);
                        window.location.reload();
                        return;
                    }
                    throw new Error(statusData.error || 'Failed to get task status.');
                }

                updateProgress(statusData.task_message, statusData.progress, 100);

                if (statusData.progress < 10) updateTaskStatus('task1', 'in-progress');
                else if (statusData.progress >= 10 && statusData.progress < 20) { updateTaskStatus('task1', 'completed'); updateTaskStatus('task2', 'in-progress'); }
                else if (statusData.progress >= 20 && statusData.progress < 95) { updateTaskStatus('task2', 'completed'); updateTaskStatus('task3', 'in-progress'); }
                else if (statusData.progress >= 95) updateTaskStatus('task3', 'completed');

                if (statusData.status === 'completed' || statusData.status === 'failed') {
                    clearInterval(pollInterval);
                    localStorage.removeItem('activeTaskUUID');
                    toggleForm(false);

                    if (statusData.status === 'completed') {
                        updateTaskStatus('task1', 'completed');
                        updateTaskStatus('task2', 'completed');
                        updateTaskStatus('task3', 'completed');
                        displayResults(statusData.result);
                        loading.classList.add('hidden');
                        if (window.stopGame) stopGame();
                        gameContainer.classList.add('hidden');
                    } else {
                        alert(`Story generation failed: ${statusData.error || 'Unknown error'}`);
                        window.location.reload();
                    }
                }
            } catch (pollError) {
                console.error("Polling network error (will retry):", pollError.message);
                currentTask.textContent = 'Connection issue. Retrying...';
            }
        }, 3000);
    }

    // --- Event Listeners ---

    storyForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(e.target);
        const prompt = formData.get('prompt');
        if (!prompt || prompt.trim() === '') {
            alert('Please enter a story prompt.');
            return;
        }

        toggleForm(true);
        loading.classList.remove('hidden');
        result.classList.add('hidden');
        gamePrompt.classList.remove('hidden');
        updateProgress('Initializing story generation...', 0, 100);
        updateTaskStatus('task1', 'in-progress');
        updateTaskStatus('task2', 'pending');
        updateTaskStatus('task3', 'pending');

        const imageMode = formData.get('imageMode');
        const isPublic = formData.get('public') === 'on';
        const minParagraphs = formData.get('minParagraphs');
        const maxParagraphs = formData.get('maxParagraphs');

        if (isProduction) {
            // --- PRODUCTION LOGIC ---
            try {
                const startResponse = await fetch('/start-story-generation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt, imageMode, public: isPublic, minParagraphs, maxParagraphs }),
                });
                const startData = await startResponse.json();
                if (!startData.success) throw new Error(startData.error || 'Failed to start story generation.');
                localStorage.setItem('activeTaskUUID', startData.task_uuid);
                startPolling(startData.task_uuid);
            } catch (startError) {
                console.error("Starting generation failed:", startError);
                alert(startError.message);
                toggleForm(false);
                window.location.reload();
            }
        } else {
            // --- LOCAL DEVELOPMENT LOGIC ---
            const params = new URLSearchParams({ prompt, imageMode, public: isPublic, minParagraphs, maxParagraphs });
            const eventSource = new EventSource(`/generate_story_stream?${params.toString()}`);

            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);

                if (data.error) {
                    alert('An error occurred while creating the story: ' + data.error);
                    eventSource.close();
                    toggleForm(false);
                    window.location.reload();
                    return;
                }

                updateProgress(data.task, data.progress, data.total);

                if (data.task.includes('Creating story content')) updateTaskStatus('task1', 'in-progress');
                else if (data.task.includes('Story content generated')) { updateTaskStatus('task1', 'completed'); updateTaskStatus('task2', 'in-progress'); }
                else if (data.task.includes('Generating image prompts')) { updateTaskStatus('task2', 'completed'); updateTaskStatus('task3', 'in-progress'); }
                else if (data.task.includes('Generating image')) updateTaskStatus('task3', 'in-progress');

                if (data.task === 'Finished!') {
                    updateTaskStatus('task1', 'completed');
                    updateTaskStatus('task2', 'completed');
                    updateTaskStatus('task3', 'completed');
                    displayResults(data.data);
                    eventSource.close();
                    toggleForm(false);
                    loading.classList.add('hidden');
                    if (window.stopGame) stopGame();
                    gameContainer.classList.add('hidden');
                }
            };

            eventSource.onerror = function(err) {
                console.error("EventSource failed:", err);
                alert('An error occurred with the story generation stream.');
                eventSource.close();
                toggleForm(false);
                window.location.reload();
            };
        }
    });

    // --- Initial Page Load Logic ---
    if (isProduction) {
        const activeTaskUUID = localStorage.getItem('activeTaskUUID');
        if (activeTaskUUID) {
            console.log('Resuming task:', activeTaskUUID);
            startPolling(activeTaskUUID);
        }
    }

    // --- UI & Utility Listeners ---
    function validateInputs() {
        let minVal = parseInt(minParagraphsInput.value);
        let maxVal = parseInt(maxParagraphsInput.value);
        if (minVal > maxVal) maxParagraphsInput.value = minVal;
        minParagraphsInput.value = Math.max(5, Math.min(100, minVal));
        maxParagraphsInput.value = Math.max(5, Math.min(100, maxVal));
    }

    minParagraphsInput.addEventListener('change', validateInputs);
    maxParagraphsInput.addEventListener('change', validateInputs);

    playYesBtn.addEventListener('click', () => {
        gamePrompt.classList.add('hidden');
        gameContainer.classList.remove('hidden');
        if (window.startGame) startGame();
    });

    playNoBtn.addEventListener('click', () => {
        gamePrompt.classList.add('hidden');
    });

    closeModalBtn.onclick = function() {
        promptModal.style.display = 'none';
    }

    window.onclick = function(event) {
        if (event.target == promptModal) {
            promptModal.style.display = 'none';
        }
    }
});

// --- Global Functions (can be called from HTML) ---
function showPrompt(prompt) {
    const modal = document.getElementById('promptModal');
    const promptText = document.getElementById('promptText');
    if (modal && promptText) {
        promptText.textContent = prompt;
        modal.style.display = 'block';
    }
}

// --- Touch event listeners to prevent multi-touch zoom ---
document.addEventListener('touchstart', (event) => {
    if (event.touches.length > 1) event.preventDefault();
}, { passive: false });

document.addEventListener('touchmove', (event) => {
    if (event.touches.length > 1) event.preventDefault();
}, { passive: false });

document.addEventListener('touchend', (event) => {
    if (event.touches.length > 1) event.preventDefault();
}, { passive: false });