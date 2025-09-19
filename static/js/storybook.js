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

document.addEventListener('DOMContentLoaded', () => {
    const titleScreen = document.getElementById('title-screen');
    const storybook = document.getElementById('storybook');
    const pageContainer = document.getElementById('page-container');
    const pageNumberDisplay = document.getElementById('page-number');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const audioPlayer = document.getElementById('audio-player');

    let currentPage = 0;

    function playAudio(audioUrl) {
        if (audioPlayer.src !== audioUrl) {
            audioPlayer.src = audioUrl;
        }
        audioPlayer.play();
    }

    const playStoryBtn = document.getElementById('play-story-btn');

    const titleElement = titleScreen.querySelector('h1');

    playStoryBtn.addEventListener('click', () => {
        // Hide the play button
        playStoryBtn.classList.add('hidden');

        // Play title audio
        playAudio(storyData.audio_files[0]);

        // Wait 5 seconds, then hide the title and show the story
        setTimeout(() => {
            titleElement.classList.add('hidden');
            storybook.classList.remove('hidden');
            showPage(currentPage);
        }, 3000);
    });

    function createPage(pageData) {
        const page = document.createElement('div');
        page.className = 'page';
        let content = '';
        if (pageData.image && pageData.image.url) {
            content += `<img src="${pageData.image.url}" alt="Illustration">`;
        }
        content += `<p>${pageData.paragraph}</p>`;
        page.innerHTML = content;
        return page;
    }

    const pages = storyData.paragraphs.map((paragraph, index) => {
        return createPage({ paragraph: paragraph, image: storyData.images[index] });
    });

    pages.forEach(page => pageContainer.appendChild(page));

    function showPage(pageNumber) {
        pages.forEach((page, index) => {
            if (index === pageNumber) {
                page.classList.add('active');
            } else {
                page.classList.remove('active');
            }
        });

        playAudio(storyData.audio_files[pageNumber + 1]);

        if (pageNumber === 0) {
            prevBtn.classList.add('hidden');
        } else {
            prevBtn.classList.remove('hidden');
        }

        if (pageNumber === pages.length - 1) {
            nextBtn.classList.add('hidden');
        } else {
            nextBtn.classList.remove('hidden');
        }

                document.getElementById('current-page').textContent = pageNumber + 1;
        document.getElementById('total-pages').textContent = pages.length;
    }

    nextBtn.addEventListener('click', () => {
        if (currentPage < pages.length - 1) {
            currentPage++;
            showPage(currentPage);
        }
    });

    prevBtn.addEventListener('click', () => {
        if (currentPage > 0) {
            currentPage--;
            showPage(currentPage);
        }
    });

    const shareBtn = document.getElementById('share-btn');
    shareBtn.addEventListener('click', () => {
        const shareLink = document.getElementById('share-link').value;
        navigator.clipboard.writeText(shareLink).then(() => {
            Toastify({
                text: "Link copied to clipboard!",
                duration: 3000,
                close: true,
                gravity: "top",
                position: "center",
                style: {
                    background: "linear-gradient(to right, #00b09b, #96c93d)",
                    fontFamily: "'Press Start 2P', cursive"
                }
            }).showToast();
        }).catch(err => {
            console.error('Failed to copy: ', err);
            Toastify({
                text: "Failed to copy link!",
                duration: 3000,
                close: true,
                gravity: "top",
                position: "center",
                style: {
                    background: "linear-gradient(to right, #ff5f6d, #ffc371)",
                    fontFamily: "'Press Start 2P', cursive"
                }
            }).showToast();
        });
    });
});