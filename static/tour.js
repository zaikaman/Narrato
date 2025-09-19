document.addEventListener('DOMContentLoaded', function () {
    if (window.innerWidth <= 768) {
        return;
    }

    if (document.querySelector('#prompt')) {
        const narrator = document.createElement('img');
        narrator.src = '/static/images/narrator.png';
        narrator.className = 'driver-narrator';
        document.body.appendChild(narrator);

        const driver = new Driver({
            animate: false,
            allowClose: false,
            onHighlightStarted: (element) => {
                narrator.style.display = 'block';
            },
            onReset: (element) => {
                narrator.style.display = 'none';
            }
        });

        const baseSteps = [
            {
                element: '#prompt',
                popover: {
                    title: 'Welcome to the Story Generator!',
                    description: 'First, enter the theme or a short description of the story you want to create.',
                    side: 'bottom'
                }
            },
            {
                element: 'div.grid.grid-cols-1.gap-4 > div:nth-child(1)',
                popover: {
                    title: 'Number of Pages',
                    description: 'Choose the minimum and maximum number of pages for your story. Each page will have an illustration.',
                    side: 'bottom'
                }
            },
            {
                element: 'div.space-y-2:nth-child(2)',
                popover: {
                    title: 'Image Generation',
                    description: 'You can choose to generate images for your story or just the text.',
                    side: 'top'
                }
            },
            {
                element: 'div.space-y-2:nth-child(3)',
                popover: {
                    title: 'Public Story',
                    description: 'Check this box if you want to share your story with the community.',
                    side: 'top'
                }
            },
            {
                element: 'button[type="submit"]',
                popover: {
                    title: 'Create Your Story',
                    description: 'Once you are ready, click here to generate your story. It might take a few moments.',
                    side: 'top'
                }
            }
        ];

        const loggedInSteps = [
            {
                element: '#history-button',
                popover: {
                    title: 'View Your Stories',
                    description: 'You can view your previously created stories here.',
                    side: 'bottom'
                }
            }
        ];

        let steps = baseSteps;
        if (document.querySelector('#history-button')) {
            steps = [...baseSteps, ...loggedInSteps];
        }

        driver.defineSteps(steps);

        if (!localStorage.getItem('tour_seen')) {
            driver.start();
            localStorage.setItem('tour_seen', 'true');
        }

        const restartTourButton = document.createElement('button');
        restartTourButton.innerHTML = '<i class="fas fa-question-circle"></i>';
        restartTourButton.className = 'pixel-button tour-button';
        restartTourButton.onclick = () => {
            driver.start();
        };
        document.body.appendChild(restartTourButton);
    }
});