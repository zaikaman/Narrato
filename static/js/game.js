const gameContainer = document.getElementById('game-container');
const bird = document.getElementById('bird');
const scoreElement = document.getElementById('score');
const playAgainButton = document.getElementById('play-again-button');

let GAME_WIDTH;
let GAME_HEIGHT;

window.addEventListener('resize', () => {
    if (gameInterval) {
        stopGame();
    }
});
const BIRD_SIZE = 40;
const GRAVITY = 0.5;
const JUMP_FORCE = -8;
const PIPE_WIDTH = 50;
const PIPE_GAP = 150;
const PIPE_SPEED = 2;

let birdY;
let birdVelocity = 0;
let pipes = [];
let score = 0;
let gameInterval;

function startGame() {
    GAME_WIDTH = gameContainer.offsetWidth;
    GAME_HEIGHT = gameContainer.offsetHeight;

    if (gameInterval) {
        clearInterval(gameInterval);
    }
    birdY = GAME_HEIGHT / 2;
    birdVelocity = 0;
    pipes = [];
    score = 0;
    scoreElement.textContent = `Score: ${score}`;
    playAgainButton.style.display = 'none';
    gameInterval = setInterval(updateGame, 20);
    document.addEventListener('keydown', handleKeyPress);
    gameContainer.addEventListener('click', handleKeyPress); // Allow clicking to jump
    spawnPipe();
}

function stopGame() {
    clearInterval(gameInterval);
    document.removeEventListener('keydown', handleKeyPress);
    gameContainer.removeEventListener('click', handleKeyPress);
    playAgainButton.style.display = 'block';
}

function updateGame() {
    birdVelocity += GRAVITY;
    birdY += birdVelocity;
    bird.style.top = `${birdY}px`;

    if (isGameOver()) {
        stopGame();
        return;
    }

    movePipes();
    renderPipes();
}

function renderPipes() {
    gameContainer.querySelectorAll('.pipe').forEach(pipe => pipe.remove());
    pipes.forEach(pipe => {
        const topPipe = document.createElement('div');
        topPipe.className = 'pipe';
        topPipe.style.left = `${pipe.x}px`;
        topPipe.style.top = '0px';
        topPipe.style.height = `${pipe.topHeight}px`;
        gameContainer.appendChild(topPipe);

        const bottomPipe = document.createElement('div');
        bottomPipe.className = 'pipe';
        bottomPipe.style.left = `${pipe.x}px`;
        bottomPipe.style.bottom = '0px';
        bottomPipe.style.height = `${GAME_HEIGHT - pipe.topHeight - PIPE_GAP}px`;
        gameContainer.appendChild(bottomPipe);
    });
}

function movePipes() {
    pipes.forEach(pipe => {
        pipe.x -= PIPE_SPEED;
    });

    if (pipes.length > 0 && pipes[0].x < -PIPE_WIDTH) {
        pipes.shift();
        score++;
        scoreElement.textContent = `Score: ${score}`;
    }

    if (pipes.length === 0 || pipes[pipes.length - 1].x < GAME_WIDTH - 200) {
        spawnPipe();
    }
}

function spawnPipe() {
    const topHeight = Math.random() * (GAME_HEIGHT - PIPE_GAP - 50) + 25;
    pipes.push({ x: GAME_WIDTH, topHeight: topHeight });
}

function isGameOver() {
    if (birdY > GAME_HEIGHT - BIRD_SIZE || birdY < 0) {
        return true;
    }

    for (const pipe of pipes) {
        if (
            pipe.x < BIRD_SIZE &&
            pipe.x + PIPE_WIDTH > 0 &&
            (birdY < pipe.topHeight || birdY + BIRD_SIZE > pipe.topHeight + PIPE_GAP)
        ) {
            return true;
        }
    }

    return false;
}

function handleKeyPress(event) {
    if (event.code === 'Space' || event.type === 'click') {
        birdVelocity = JUMP_FORCE;
    }
}

playAgainButton.addEventListener('click', startGame);