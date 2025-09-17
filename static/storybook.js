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

    playStoryBtn.addEventListener('click', () => {
        // Play title audio
        playAudio(storyData.audio_files[0]);

        // Hide the play button
        playStoryBtn.classList.add('hidden');

        setTimeout(() => {
            titleScreen.classList.add('hidden');
            storybook.classList.remove('hidden');
            setTimeout(() => {
                showPage(currentPage);
            }, 2000);
        }, 5000);
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
});