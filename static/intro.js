window.onload = function () {
    console.log('intro.js loaded');
    const introOverlay = document.getElementById('intro-overlay');
    const startTourBtn = document.getElementById('start-tour-btn');
    const tourSeen = localStorage.getItem('tour_seen');
    const narrator = document.querySelector('#intro-narrator');

    if (!tourSeen) {
        introOverlay.style.display = 'flex';
    }

    startTourBtn.addEventListener('click', function (e) {
        e.preventDefault();
        console.log('Start Tour button clicked');
        console.log('window.driver in intro.js:', window.driver);
        localStorage.setItem('tour_seen', 'true');
        introOverlay.style.display = 'none';
        
        if (document.querySelector('#prompt')) {
            const driver = window.driver;
            if (driver) {
                console.log('Starting tour in 100ms...');
                setTimeout(() => {
                    driver.start();
                }, 100);
            } else {
                console.error('Driver is not initialized');
            }
        }
    });
};