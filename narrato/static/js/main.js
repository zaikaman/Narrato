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
    const cancelBtn = document.getElementById('cancel-generation-btn');

    const activeStreamTaskKey = 'activeStreamTask';
    let currentEventSource = null; // To hold the active EventSource

    // --- Core Functions ---

    function resetUI() {
        sessionStorage.removeItem('isSubmitting'); // Reset submission guard
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
        // Add logic here for stopping polling if/when implemented

        toggleForm(false);
        loading.classList.add('hidden');
        cancelBtn.classList.add('hidden');
        localStorage.removeItem(activeStreamTaskKey);
        localStorage.removeItem('activeTaskUUID'); // Also clear production task
        updateProgress('Cancelled', 0, 100);
        console.log("Story generation cancelled.");
    }


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

    function updateAllTaskStatuses(progress) {
        // Set status based on progress percentage
        updateTaskStatus('task1', progress > 0 ? 'in-progress' : 'pending');
        updateTaskStatus('task2', 'pending');
        updateTaskStatus('task3', 'pending');
        updateTaskStatus('task4', 'pending');
    
        if (progress >= 10) {
            updateTaskStatus('task1', 'completed');
            updateTaskStatus('task2', 'in-progress');
        }
        if (progress >= 35) {
            updateTaskStatus('task2', 'completed');
            updateTaskStatus('task3', 'in-progress');
        }
        if (progress >= 70) {
            updateTaskStatus('task3', 'completed');
            updateTaskStatus('task4', 'in-progress');
        }
        if (progress >= 100) {
            updateTaskStatus('task1', 'completed');
            updateTaskStatus('task2', 'completed');
            updateTaskStatus('task3', 'completed');
            updateTaskStatus('task4', 'completed');
        }
    }
    
    function createEpicTransition() {
        const modal = document.getElementById('story-ready-modal');
        const modalContent = modal.querySelector('.modal-content');

        modal.style.display = 'block';

        const particleContainer = document.createElement('div');
        particleContainer.id = 'particle-container';
        modalContent.appendChild(particleContainer);

        for (let i = 0; i < 50; i++) {
            const particle = document.createElement('div');
            particle.classList.add('particle');
            const size = Math.random() * 5 + 2;
            particle.style.width = `${size}px`;
            particle.style.height = `${size}px`;
            particle.style.top = `50%`;
            particle.style.left = `50%`;
            particle.style.setProperty('--x', `${(Math.random() - 0.5) * 400}px`);
            particle.style.setProperty('--y', `${(Math.random() - 0.5) * 400}px`);
            particleContainer.appendChild(particle);
        }

        setTimeout(() => {
            modal.style.opacity = 1;
            modalContent.style.transform = 'translate(-50%, -50%) scale(1)';
        }, 10);

        setTimeout(() => {
            particleContainer.remove();
        }, 1000);
    }

    function displayResults(data) {
        if (!data || !data.story_uuid) {
            console.error("Invalid data passed to displayResults", data);
            alert("An error occurred while trying to display the story results.");
            return;
        }
        const storyId = data.story_uuid;
        createEpicTransition();
        viewStoryBtn.onclick = () => {
            window.location.href = `/view_story/${storyId}`;
        };
    }
    
    // --- Local/Heroku (Streaming) Functions ---
    function startStreaming(taskDetails) {
        const params = new URLSearchParams(taskDetails);
        currentEventSource = new EventSource(`/generate_story_stream?${params.toString()}`);

        currentEventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);

            if (data.error) {
                alert('An error occurred while creating the story: ' + data.error);
                currentEventSource.close();
                toggleForm(false);
                localStorage.removeItem(activeStreamTaskKey);
                window.location.reload();
                return;
            }

                            updateProgress(data.task, data.progress, data.total);
                            updateAllTaskStatuses(data.progress);
            
                            if (data.task === 'Finished!') {
                                sessionStorage.removeItem('isSubmitting'); // Reset submission guard
                                displayResults(data.data);
                                currentEventSource.close();
                localStorage.removeItem(activeStreamTaskKey);
                toggleForm(false);
                loading.classList.add('hidden');
                if (window.stopGame) stopGame();
                gameContainer.classList.add('hidden');
            }
        };

        currentEventSource.onerror = function(err) {
            console.error("EventSource connection failed. This is the final error handler.", err);
            sessionStorage.removeItem('isSubmitting'); // Reset submission guard
            currentEventSource.close();
        };
    }

    // --- Event Listeners ---

    storyForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (sessionStorage.getItem('isSubmitting') === 'true') {
            console.warn("Submission blocked: a story is already being generated.");
            return;
        }
        sessionStorage.setItem('isSubmitting', 'true');

        Swal.fire({
            title: 'Heads up!',
            text: 'We do not recommend closing or refreshing this page during story generation.',
            icon: 'info',
            confirmButtonText: 'Got it!',
            background: '#2a2a2a',
            color: '#ffffff',
            customClass: {
                popup: 'pixel-font-popup',
                title: 'pixel-font-popup',
                htmlContainer: 'pixel-font-popup',
                confirmButton: 'pixel-font-popup',
            }
        });

        const formData = new FormData(e.target);
        const prompt = formData.get('prompt');
        if (!prompt || prompt.trim() === '') {
            alert('Please enter a story prompt.');
            return;
        }

        toggleForm(true);
        loading.classList.remove('hidden');
        cancelBtn.classList.remove('hidden');
        result.classList.add('hidden');
        gamePrompt.classList.remove('hidden');
        updateProgress('Initializing story generation...', 0, 100);
        updateTaskStatus('task1', 'in-progress');
        updateTaskStatus('task2', 'pending');
        updateTaskStatus('task3', 'pending');

        const imageMode = formData.get('imageMode');
        const isPublic = formData.get('public') === 'on';
        const minParagraphs = document.getElementById('minParagraphs').value;
        const maxParagraphs = document.getElementById('maxParagraphs').value;

        const taskDetails = {
            story_uuid: crypto.randomUUID(),
            prompt,
            imageMode,
            public: isPublic,
            minParagraphs,
            maxParagraphs
        };
        localStorage.setItem(activeStreamTaskKey, JSON.stringify(taskDetails));
        startStreaming(taskDetails);
    });

    // --- Initial Page Load Logic ---
    const taskJSON = localStorage.getItem(activeStreamTaskKey);
    if (taskJSON) {
        const taskDetails = JSON.parse(taskJSON);
        console.log('Resuming stream task:', taskDetails.story_uuid);
        
        toggleForm(true);
        loading.classList.remove('hidden');
        result.classList.add('hidden');
        gamePrompt.classList.remove('hidden');

        startStreaming(taskDetails);
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

    cancelBtn.addEventListener('click', () => {
        resetUI();
        // Optionally, show a confirmation message
        Swal.fire({
            title: 'Cancelled',
            text: 'Story generation has been stopped.',
            icon: 'error',
            background: '#2a2a2a',
            color: '#ffffff',
            customClass: {
                popup: 'pixel-font-popup',
                title: 'pixel-font-popup',
                htmlContainer: 'pixel-font-popup',
                confirmButton: 'pixel-font-popup',
            }
        });
    });

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