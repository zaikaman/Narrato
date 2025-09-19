
document.addEventListener('DOMContentLoaded', function () {
    if (window.innerWidth <= 768) {
        return;
    }

    // --- Driver Initialization ---
    const driver = new Driver({
        animate: false,
        allowClose: true,
        onHighlightStarted: (element) => {
            document.getElementById('custom-driver-overlay').style.display = 'block';
            if (narrator) narrator.style.display = 'block';

            const storybookContainer = document.getElementById('storybook');
            if (storybookContainer) {
                storybookContainer.style.zIndex = 10001;
            }
        },
        onReset: (element) => {
            document.getElementById('custom-driver-overlay').style.display = 'none';
            if (narrator) narrator.style.display = 'none';

            const storybookContainer = document.getElementById('storybook');
            if (storybookContainer) {
                storybookContainer.style.zIndex = 'auto';
            }
        }
    });

    // --- Helper Elements ---
    const narrator = document.createElement('img');
    narrator.src = '/static/images/narrator.png';
    narrator.className = 'driver-narrator';
    document.body.appendChild(narrator);

    const restartTourButton = document.createElement('button');
    restartTourButton.innerHTML = '<i class="fas fa-question-circle"></i>';
    restartTourButton.className = 'pixel-button tour-button';
    restartTourButton.onclick = () => {
        localStorage.removeItem('tour_step');
        localStorage.removeItem('tour_seen');
        window.location.href = '/';
    };
    document.body.appendChild(restartTourButton);

    // --- Step Definitions ---
    const indexPageSteps = [
        { element: '#prompt', popover: { title: 'Create a Story', description: 'First, enter the theme or a short description of the story you want to create.', side: 'bottom' } },
        { element: 'input[name="minParagraphs"]', popover: { title: 'Number of Pages', description: 'Choose the minimum and maximum number of pages for your story.', side: 'bottom' } },
        { element: 'input[name="imageMode"]', popover: { title: 'Image Generation', description: 'You can choose to generate images for your story or just the text.', side: 'top' } },
        { element: '#public', popover: { title: 'Make it Public', description: 'Check this box if you want to share your story with the community.', side: 'top' } },
        { element: 'button[type="submit"]', popover: { title: 'Generate Story', description: 'Once you are ready, click here to generate your story.', side: 'top' } },
        {
            element: '#browse-button',
            popover: {
                title: 'Explore Stories',
                description: "Now, click the actual 'Browse' button to see what others have created. The tour will continue on the next page.",
                showButtons: ['previous', 'close'],
            },
            onHighlighted: () => {
                localStorage.setItem('tour_step', 'browse');
            }
        }
    ];

    const browsePageSteps = [
        {
            element: '.story-card:first-of-type',
            popover: {
                title: 'View a Story',
                description: 'Click on this story card to read it. The tour will continue when the story loads.',
                showButtons: ['previous', 'close'],
            },
            onHighlighted: () => {
                localStorage.setItem('tour_step', 'story_view');
            }
        }
    ];

    const storyViewPageSteps = [
        { element: '#storybook #next-btn', popover: { title: 'Next Page', description: 'Use this button to go to the next page.', side: 'left' } },
        { element: '#storybook #prev-btn', popover: { title: 'Previous Page', description: 'Use this button to go back to the previous page.', side: 'right' } },
        { element: '#storybook #share-btn', popover: { title: 'Share Your Story', description: 'Click here to get a shareable link.', side: 'top' } },
        { element: 'a[href*="export_pdf"]', popover: { title: 'Export to PDF', description: 'You can download the story as a PDF file with this button.', side: 'top' } },
        {
            element: '.back-button',
            popover: {
                title: 'Go Back Home',
                description: "Click the 'Home' button to go back to the main page for the final tip.",
                showButtons: ['previous', 'close'],
            },
            onHighlighted: () => {
                const backButton = document.querySelector('.back-button');
                if (backButton) {
                    backButton.href = '/?tour_final=true';
                }
            }
        }
    ];

    // --- Tour Logic ---
    const tourStep = localStorage.getItem('tour_step');
    const urlParams = new URLSearchParams(window.location.search);
    const isFinalStep = urlParams.get('tour_final');

    if (document.querySelector('#prompt')) { // On index page
        if (isFinalStep) {
            // Manually trigger the final tip
            document.getElementById('custom-driver-overlay').style.display = 'block';
            if (narrator) narrator.style.display = 'block';
            const finalTipElement = document.getElementById('manual-final-tip');
            if(finalTipElement) finalTipElement.style.display = 'block';

            const closeBtn = document.getElementById('manual-tip-close');
            if(closeBtn) {
                closeBtn.addEventListener('click', () => {
                    if(finalTipElement) finalTipElement.style.display = 'none';
                    document.getElementById('custom-driver-overlay').style.display = 'none';
                    if (narrator) narrator.style.display = 'none';
                    history.replaceState(null, '', window.location.pathname);
                });
            }

        } else if (!localStorage.getItem('tour_seen')) {
            driver.defineSteps(indexPageSteps);
            driver.start();
            localStorage.setItem('tour_seen', 'true');
        }
    } else if (document.querySelector('.story-card') && tourStep === 'browse') { // On browse page
        driver.defineSteps(browsePageSteps);
        driver.start();
    } else if (document.querySelector('#storybook') && tourStep === 'story_view') { // On story view page
        const storybookElement = document.querySelector('#storybook');
        
        if (!storybookElement.classList.contains('hidden')) {
            driver.defineSteps(storyViewPageSteps);
            driver.start();
        } else {
            const observer = new MutationObserver((mutationsList, obs) => {
                for(const mutation of mutationsList) {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                        if (!storybookElement.classList.contains('hidden')) {
                            driver.defineSteps(storyViewPageSteps);
                            driver.start();
                            obs.disconnect();
                        }
                    }
                }
            });
            observer.observe(storybookElement, { attributes: true });
        }
    }
});
