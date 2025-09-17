document.addEventListener('DOMContentLoaded', () => {
    const titleScreen = document.getElementById('title-screen');
    const storybook = document.getElementById('storybook');
    const pageContainer = document.getElementById('page-container');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');

    let currentPage = 0;

    setTimeout(() => {
        titleScreen.classList.add('hidden');
        storybook.classList.remove('hidden');
        showPage(currentPage);
    }, 5000);

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
