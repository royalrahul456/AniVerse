// Initialize Telegram Web App SDK
const tg = window.Telegram.WebApp;
tg.expand();

// API Server configuration (Change this to your actual Render URL when deploying!)
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8080'
    : 'https://aniverse-bot-cjvr.onrender.com';

// Fallback user ID for previewing in desktop browsers
let userId = 6593485710;
if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
    userId = tg.initDataUnsafe.user.id;
}

// State
let userProfile = null;
let currentActiveGame = null;
let gameInterval = null;
let gameScore = 0;
let gameTimeLeft = 0;
let pendingClaimCoins = 0;

// DOM Elements
const userNameEl = document.getElementById("user-name");
const userTagEl = document.getElementById("user-tag");
const statCoinsEl = document.getElementById("stat-coins");
const gameModal = document.getElementById("game-modal");
const modalTitle = document.getElementById("modal-title");
const liveScore = document.getElementById("live-score");
const liveTimer = document.getElementById("live-timer");
const gameCanvas = document.getElementById("game-canvas");
const htmlGameContainer = document.getElementById("html-game-container");
const mobileControls = document.getElementById("mobile-controls");
const rewardModal = document.getElementById("reward-modal");
const rewardMessage = document.getElementById("reward-message");
const earnedCoinsValue = document.getElementById("earned-coins-value");

// Initialize
async function init() {
    await fetchProfile();
}

// Fetch user profile stats
async function fetchProfile() {
    try {
        const response = await fetch(`${API_BASE}/api/profile/${userId}`);
        if (!response.ok) throw new Error("Profile fetch failed");
        
        userProfile = await response.json();
        
        userNameEl.textContent = userProfile.first_name;
        userTagEl.textContent = userProfile.custom_tag || "Novice Trainer";
        statCoinsEl.textContent = userProfile.coins.toLocaleString();
    } catch (err) {
        console.error("Error loading profile:", err);
        userNameEl.textContent = tg.initDataUnsafe?.user?.first_name || "Trainer";
    }
}

// Launch Game Manager
function openGame(gameType) {
    currentActiveGame = gameType;
    gameScore = 0;
    gameTimeLeft = 0;
    pendingClaimCoins = 0;
    
    // Reset view visibility
    gameCanvas.classList.add("hidden");
    htmlGameContainer.classList.add("hidden");
    mobileControls.classList.add("hidden");
    liveTimer.classList.add("hidden");
    
    gameModal.classList.remove("hidden");
    
    // Clear any active game loops
    if (gameInterval) clearInterval(gameInterval);
    
    // Choose and setup game
    switch (gameType) {
        case 'memory':
            setupMemoryGame();
            break;
        case 'ninja':
            setupNinjaGame();
            break;
        case 'snake':
            setupSnakeGame();
            break;
        case 'catch':
            setupCatchGame();
            break;
        case 'rps':
            setupRPSGame();
            break;
        case 'clicker':
            setupClickerGame();
            break;
        case 'ttt':
            setupTTTGame();
            break;
        case 'dodge':
            setupDodgeGame();
            break;
        case 'guess':
            setupGuessGame();
            break;
        case 'math':
            setupMathGame();
            break;
    }
    
    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred("success");
    }
}

// Close Game Overlay
function closeGame() {
    if (gameInterval) clearInterval(gameInterval);
    gameModal.classList.add("hidden");
    currentActiveGame = null;
}

// Triggers the Victory claim popup
function triggerVictoryScreen(score, coins) {
    pendingClaimCoins = coins;
    rewardMessage.textContent = `You scored ${score} points!`;
    earnedCoinsValue.textContent = coins;
    rewardModal.classList.remove("hidden");
    
    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred("success");
    }
}

// Send earned coins to backend database
async function claimReward() {
    rewardModal.classList.add("hidden");
    closeGame();
    
    if (pendingClaimCoins <= 0) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/games/reward`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                game_id: `game_${currentActiveGame}`,
                coins: pendingClaimCoins
            })
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || "Claim failed");
        }
        
        const data = await response.json();
        // Update live balance counter
        statCoinsEl.textContent = data.coins.toLocaleString();
        
        if (tg.HapticFeedback) {
            tg.HapticFeedback.notificationOccurred("success");
        }
    } catch (err) {
        alert(err.message || "Failed to sync coins to bot account. Cooldown might be active!");
    }
}

// ----------------------------------------------------
// GAME 1: MEMORY MATCH
// ----------------------------------------------------
function setupMemoryGame() {
    modalTitle.textContent = "Memory Match";
    htmlGameContainer.classList.remove("hidden");
    htmlGameContainer.innerHTML = `<div id="memory-grid" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; width: 240px; height: 240px;"></div>`;
    
    const items = ['⛩️', '🦊', '🌸', '🐲', '⚡', '🌌', '🍙', '⚔️'];
    const cards = [...items, ...items].sort(() => Math.random() - 0.5);
    const grid = document.getElementById("memory-grid");
    
    let flipped = [];
    let matches = 0;
    
    cards.forEach((val, idx) => {
        const cell = document.createElement("div");
        cell.style.cssText = "background: #1c1f35; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 24px; cursor: pointer; border: 1px solid rgba(255,255,255,0.1); transition: background 0.2s;";
        cell.textContent = "❓";
        
        cell.addEventListener("click", () => {
            if (flipped.length >= 2 || cell.textContent !== "❓") return;
            
            cell.textContent = val;
            cell.style.background = "var(--accent)";
            flipped.push({ cell, val });
            
            if (flipped.length === 2) {
                setTimeout(() => {
                    if (flipped[0].val === flipped[1].val) {
                        flipped[0].cell.style.background = "var(--success)";
                        flipped[1].cell.style.background = "var(--success)";
                        matches++;
                        gameScore += 10;
                        liveScore.textContent = `Score: ${gameScore}`;
                        
                        if (matches === items.length) {
                            const reward = Math.min(50, gameScore / 2);
                            triggerVictoryScreen(gameScore, Math.floor(reward));
                        }
                    } else {
                        flipped[0].cell.textContent = "❓";
                        flipped[0].cell.style.background = "#1c1f35";
                        flipped[1].cell.textContent = "❓";
                        flipped[1].cell.style.background = "#1c1f35";
                    }
                    flipped = [];
                }, 600);
            }
        });
        grid.appendChild(cell);
    });
}

// ----------------------------------------------------
// GAME 2: NINJA JUMP
// ----------------------------------------------------
function setupNinjaGame() {
    modalTitle.textContent = "Ninja Jump";
    gameCanvas.classList.remove("hidden");
    mobileControls.classList.remove("hidden");
    mobileControls.innerHTML = `<button class="control-btn" id="ninja-jump-btn" style="max-width: 100%;">🥷 JUMP</button>`;
    
    const ctx = gameCanvas.getContext("2d");
    let ninjaY = 270;
    let ninjaVY = 0;
    let isJumping = false;
    let obstacleX = 320;
    let obstacleSpeed = 4;
    
    document.getElementById("ninja-jump-btn").addEventListener("click", () => {
        if (!isJumping) {
            ninjaVY = -12;
            isJumping = true;
        }
    });
    
    gameInterval = setInterval(() => {
        // Physics
        ninjaVY += 0.8; // Gravity
        ninjaY += ninjaVY;
        if (ninjaY >= 270) {
            ninjaY = 270;
            ninjaVY = 0;
            isJumping = false;
        }
        
        obstacleX -= obstacleSpeed;
        if (obstacleX < -15) {
            obstacleX = 320;
            gameScore += 10;
            liveScore.textContent = `Score: ${gameScore}`;
            obstacleSpeed = 4 + Math.floor(gameScore / 50);
        }
        
        // Collisions
        if (obstacleX > 30 && obstacleX < 50 && ninjaY >= 250) {
            clearInterval(gameInterval);
            const reward = Math.min(100, Math.floor(gameScore / 3));
            triggerVictoryScreen(gameScore, reward);
        }
        
        // Draw
        ctx.clearRect(0, 0, 320, 320);
        ctx.fillStyle = "#2ecc71";
        ctx.fillRect(0, 290, 320, 30); // Ground
        
        ctx.fillStyle = "#e74c3c"; // Obstacle (Bamboo spike)
        ctx.fillRect(obstacleX, 260, 15, 30);
        
        ctx.fillStyle = "#f1c40f"; // Player (Ninja icon circle)
        ctx.beginPath();
        ctx.arc(40, ninjaY, 15, 0, Math.PI * 2);
        ctx.fill();
    }, 1000 / 60);
}

// ----------------------------------------------------
// GAME 3: SNAKE GAME
// ----------------------------------------------------
function setupSnakeGame() {
    modalTitle.textContent = "Snake Eater";
    gameCanvas.classList.remove("hidden");
    mobileControls.classList.remove("hidden");
    mobileControls.innerHTML = `
        <button class="control-btn" id="snake-l">◀</button>
        <button class="control-btn" id="snake-u">▲</button>
        <button class="control-btn" id="snake-d">▼</button>
        <button class="control-btn" id="snake-r">▶</button>
    `;
    
    const ctx = gameCanvas.getContext("2d");
    let snake = [{x: 160, y: 160}];
    let dir = {x: 16, y: 0};
    let apple = {x: 80, y: 80};
    
    document.getElementById("snake-l").onclick = () => { if (dir.x === 0) dir = {x: -16, y: 0}; };
    document.getElementById("snake-r").onclick = () => { if (dir.x === 0) dir = {x: 16, y: 0}; };
    document.getElementById("snake-u").onclick = () => { if (dir.y === 0) dir = {x: 0, y: -16}; };
    document.getElementById("snake-d").onclick = () => { if (dir.y === 0) dir = {x: 0, y: 16}; };
    
    gameInterval = setInterval(() => {
        // Move Snake
        const head = {x: snake[0].x + dir.x, y: snake[0].y + dir.y};
        snake.unshift(head);
        
        // Eat Apple
        if (head.x === apple.x && head.y === apple.y) {
            gameScore += 10;
            liveScore.textContent = `Score: ${gameScore}`;
            apple = {
                x: Math.floor(Math.random() * 20) * 16,
                y: Math.floor(Math.random() * 20) * 16
            };
        } else {
            snake.pop();
        }
        
        // Collisions
        if (head.x < 0 || head.x >= 320 || head.y < 0 || head.y >= 320 || 
            snake.slice(1).some(seg => seg.x === head.x && seg.y === head.y)) {
            clearInterval(gameInterval);
            const reward = Math.min(100, Math.floor(gameScore / 2));
            triggerVictoryScreen(gameScore, reward);
        }
        
        // Draw
        ctx.clearRect(0, 0, 320, 320);
        ctx.fillStyle = "#e74c3c"; // Apple
        ctx.fillRect(apple.x, apple.y, 14, 14);
        
        ctx.fillStyle = "#3498db"; // Snake
        snake.forEach(seg => ctx.fillRect(seg.x, seg.y, 14, 14));
    }, 150);
}

// ----------------------------------------------------
// GAME 4: COIN CATCHER
// ----------------------------------------------------
function setupCatchGame() {
    modalTitle.textContent = "Coin Catcher";
    gameCanvas.classList.remove("hidden");
    mobileControls.classList.remove("hidden");
    mobileControls.innerHTML = `
        <button class="control-btn" id="catch-l" style="max-width: 150px;">◀ LEFT</button>
        <button class="control-btn" id="catch-r" style="max-width: 150px;">RIGHT ▶</button>
    `;
    
    const ctx = gameCanvas.getContext("2d");
    let basketX = 130;
    let basketWidth = 60;
    let items = [];
    
    document.getElementById("catch-l").addEventListener("mousedown", () => basketX = Math.max(0, basketX - 25));
    document.getElementById("catch-r").addEventListener("mousedown", () => basketX = Math.min(320 - basketWidth, basketX + 25));
    // Support click tapping too
    document.getElementById("catch-l").onclick = () => basketX = Math.max(0, basketX - 25);
    document.getElementById("catch-r").onclick = () => basketX = Math.min(320 - basketWidth, basketX + 25);
    
    gameInterval = setInterval(() => {
        // Spawn item
        if (Math.random() < 0.03) {
            items.push({
                x: Math.random() * 300,
                y: 0,
                type: Math.random() < 0.75 ? 'coin' : 'bomb',
                speed: 3 + Math.random() * 2
            });
        }
        
        // Update items
        for (let i = items.length - 1; i >= 0; i--) {
            items[i].y += items[i].speed;
            
            // Catch check
            if (items[i].y >= 285 && items[i].y <= 300 && items[i].x + 10 >= basketX && items[i].x <= basketX + basketWidth) {
                if (items[i].type === 'coin') {
                    gameScore += 10;
                    liveScore.textContent = `Score: ${gameScore}`;
                } else {
                    // Bomb hit! Game Over
                    clearInterval(gameInterval);
                    const reward = Math.min(100, Math.floor(gameScore / 3));
                    triggerVictoryScreen(gameScore, reward);
                    return;
                }
                items.splice(i, 1);
            } else if (items[i].y > 320) {
                items.splice(i, 1);
            }
        }
        
        // Draw
        ctx.clearRect(0, 0, 320, 320);
        ctx.fillStyle = "#e67e22"; // Basket
        ctx.fillRect(basketX, 290, basketWidth, 15);
        
        items.forEach(item => {
            ctx.fillStyle = item.type === 'coin' ? '#f1c40f' : '#e74c3c';
            ctx.beginPath();
            ctx.arc(item.x, item.y, 8, 0, Math.PI * 2);
            ctx.fill();
        });
    }, 1000 / 60);
}

// ----------------------------------------------------
// GAME 5: ROCK PAPER SCISSORS
// ----------------------------------------------------
function setupRPSGame() {
    modalTitle.textContent = "Anime RPS";
    htmlGameContainer.classList.remove("hidden");
    htmlGameContainer.innerHTML = `
        <div class="guess-box">
            <p id="rps-result" style="font-size: 16px; font-weight: 800; color: var(--gold); margin-bottom: 20px;">Choose Rock, Paper, or Scissors!</p>
            <div class="rps-button-group">
                <button class="rps-btn" onclick="playRPS('rock')">✊</button>
                <button class="rps-btn" onclick="playRPS('paper')">✋</button>
                <button class="rps-btn" onclick="playRPS('scissors')">✌️</button>
            </div>
            <p id="rps-stats" style="font-size: 11px; color: var(--text-secondary); margin-top: 10px;">Round: 0/5</p>
        </div>
    `;
    
    let rounds = 0;
    let wins = 0;
    
    window.playRPS = function(playerChoice) {
        if (rounds >= 5) return;
        
        const choices = ['rock', 'paper', 'scissors'];
        const botChoice = choices[Math.floor(Math.random() * 3)];
        let resultMsg = "";
        
        if (playerChoice === botChoice) {
            resultMsg = `Tie! Both picked ${playerChoice.toUpperCase()}`;
        } else if (
            (playerChoice === 'rock' && botChoice === 'scissors') ||
            (playerChoice === 'paper' && botChoice === 'rock') ||
            (playerChoice === 'scissors' && botChoice === 'paper')
        ) {
            resultMsg = `Win! ${playerChoice.toUpperCase()} beats ${botChoice.toUpperCase()}`;
            wins++;
            gameScore += 20;
        } else {
            resultMsg = `Lose! ${botChoice.toUpperCase()} beats ${playerChoice.toUpperCase()}`;
        }
        
        rounds++;
        document.getElementById("rps-result").textContent = resultMsg;
        document.getElementById("rps-stats").textContent = `Round: ${rounds}/5 (Wins: ${wins})`;
        liveScore.textContent = `Score: ${gameScore}`;
        
        if (rounds === 5) {
            setTimeout(() => {
                const reward = wins * 15;
                triggerVictoryScreen(gameScore, reward);
            }, 1000);
        }
    };
}

// ----------------------------------------------------
// GAME 6: COIN CLICKER
// ----------------------------------------------------
function setupClickerGame() {
    modalTitle.textContent = "Coin Clicker";
    liveTimer.classList.remove("hidden");
    htmlGameContainer.classList.remove("hidden");
    htmlGameContainer.innerHTML = `
        <div class="clicker-box" style="padding: 20px 0;">
            <button class="clicker-coin-btn" id="clicker-coin">🪙</button>
            <p style="margin-top: 20px; font-size: 13px; color: var(--text-secondary);">Tap tap tap!</p>
        </div>
    `;
    
    gameTimeLeft = 10;
    liveTimer.textContent = `Time: 10s`;
    
    document.getElementById("clicker-coin").addEventListener("click", () => {
        if (gameTimeLeft > 0) {
            gameScore++;
            liveScore.textContent = `Score: ${gameScore}`;
            if (tg.HapticFeedback) {
                tg.HapticFeedback.impactOccurred("light");
            }
        }
    });
    
    gameInterval = setInterval(() => {
        gameTimeLeft--;
        liveTimer.textContent = `Time: ${gameTimeLeft}s`;
        
        if (gameTimeLeft <= 0) {
            clearInterval(gameInterval);
            const reward = Math.min(50, Math.floor(gameScore / 2));
            triggerVictoryScreen(gameScore, reward);
        }
    }, 1000);
}

// ----------------------------------------------------
// GAME 7: TIC TAC TOE
// ----------------------------------------------------
function setupTTTGame() {
    modalTitle.textContent = "Tic Tac Toe";
    htmlGameContainer.classList.remove("hidden");
    htmlGameContainer.innerHTML = `
        <div style="display: flex; flex-direction: column; align-items: center;">
            <div id="ttt-grid" class="ttt-grid"></div>
            <p id="ttt-result" style="font-size: 13px; color: var(--gold); margin-top: 16px; font-weight: 600;"></p>
        </div>
    `;
    
    const grid = document.getElementById("ttt-grid");
    const resultText = document.getElementById("ttt-result");
    let board = Array(9).fill("");
    let isGameOver = false;
    
    // Draw board
    for (let i = 0; i < 9; i++) {
        const cell = document.createElement("div");
        cell.className = "ttt-cell";
        cell.addEventListener("click", () => {
            if (board[i] !== "" || isGameOver) return;
            
            // Player move
            board[i] = "X";
            cell.textContent = "X";
            cell.style.color = "var(--accent)";
            
            if (checkTTTWin("X")) {
                gameScore = 50;
                liveScore.textContent = `Score: 50`;
                isGameOver = true;
                resultText.textContent = "You win!";
                setTimeout(() => triggerVictoryScreen(50, 40), 1000);
                return;
            }
            if (board.every(c => c !== "")) {
                isGameOver = true;
                resultText.textContent = "Tie game!";
                setTimeout(() => triggerVictoryScreen(0, 10), 1000);
                return;
            }
            
            // Bot AI move
            setTimeout(() => {
                const bestMove = getTTTBotMove();
                board[bestMove] = "O";
                const botCell = grid.children[bestMove];
                botCell.textContent = "O";
                botCell.style.color = "#e74c3c";
                
                if (checkTTTWin("O")) {
                    isGameOver = true;
                    resultText.textContent = "Bot wins!";
                    setTimeout(() => triggerVictoryScreen(0, 0), 1000);
                    return;
                }
            }, 400);
        });
        grid.appendChild(cell);
    }
    
    function checkTTTWin(p) {
        const winLines = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8], // Rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8], // Cols
            [0, 4, 8], [2, 4, 6]             // Diag
        ];
        return winLines.some(line => line.every(idx => board[idx] === p));
    }
    
    function getTTTBotMove() {
        // AI: Play random empty spot
        const empties = [];
        board.forEach((c, idx) => { if (c === "") empties.push(idx); });
        return empties[Math.floor(Math.random() * empties.length)];
    }
}

// ----------------------------------------------------
// GAME 8: DODGE THE FIREBALLS
// ----------------------------------------------------
function setupDodgeGame() {
    modalTitle.textContent = "Dodge Fire";
    gameCanvas.classList.remove("hidden");
    mobileControls.classList.remove("hidden");
    mobileControls.innerHTML = `
        <button class="control-btn" id="dodge-l">◀ LEFT</button>
        <button class="control-btn" id="dodge-r">RIGHT ▶</button>
    `;
    
    const ctx = gameCanvas.getContext("2d");
    let playerX = 150;
    let balls = [];
    
    document.getElementById("dodge-l").addEventListener("mousedown", () => playerX = Math.max(0, playerX - 20));
    document.getElementById("dodge-r").addEventListener("mousedown", () => playerX = Math.min(300, playerX + 20));
    document.getElementById("dodge-l").onclick = () => playerX = Math.max(0, playerX - 20);
    document.getElementById("dodge-r").onclick = () => playerX = Math.min(300, playerX + 20);
    
    gameInterval = setInterval(() => {
        // Spawn fireball
        if (Math.random() < 0.05) {
            balls.push({
                x: Math.random() * 320,
                y: 0,
                radius: 8 + Math.random() * 10,
                speed: 3 + Math.random() * 3
            });
        }
        
        // Physics updates
        for (let i = balls.length - 1; i >= 0; i--) {
            balls[i].y += balls[i].speed;
            
            // Check collision with player box at Y = 280
            if (balls[i].y >= 270 && balls[i].y <= 290 && balls[i].x >= playerX && balls[i].x <= playerX + 20) {
                clearInterval(gameInterval);
                const reward = Math.min(100, Math.floor(gameScore / 3));
                triggerVictoryScreen(gameScore, reward);
                return;
            }
            
            if (balls[i].y > 320) {
                balls.splice(i, 1);
                gameScore += 5;
                liveScore.textContent = `Score: ${gameScore}`;
            }
        }
        
        // Draw
        ctx.clearRect(0, 0, 320, 320);
        ctx.fillStyle = "#3498db"; // Player
        ctx.fillRect(playerX, 280, 20, 20);
        
        ctx.fillStyle = "#e74c3c"; // Fireballs
        balls.forEach(ball => {
            ctx.beginPath();
            ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI * 2);
            ctx.fill();
        });
    }, 1000 / 60);
}

// ----------------------------------------------------
// GAME 9: GUESS THE NUMBER
// ----------------------------------------------------
function setupGuessGame() {
    modalTitle.textContent = "Guess Number";
    htmlGameContainer.classList.remove("hidden");
    
    const secretNum = Math.floor(Math.random() * 100) + 1;
    let attemptsLeft = 6;
    
    htmlGameContainer.innerHTML = `
        <div class="guess-box">
            <p class="guess-feedback" id="guess-hint">Guess a number between 1 and 100</p>
            <input type="number" id="guess-val" class="guess-input" placeholder="50">
            <div>
                <button class="play-btn" id="guess-submit-btn" style="max-width: 150px; padding: 12px;">Submit Guess</button>
            </div>
            <p class="guess-attempts" id="guess-att-text" style="margin-top: 14px;">Attempts remaining: 6</p>
        </div>
    `;
    
    document.getElementById("guess-submit-btn").onclick = () => {
        const inputEl = document.getElementById("guess-val");
        const guess = parseInt(inputEl.value);
        if (isNaN(guess) || guess < 1 || guess > 100) return;
        
        attemptsLeft--;
        inputEl.value = "";
        
        if (guess === secretNum) {
            gameScore = 100;
            liveScore.textContent = `Score: 100`;
            triggerVictoryScreen(100, 50);
        } else if (attemptsLeft <= 0) {
            document.getElementById("guess-hint").textContent = `Game Over! The number was ${secretNum}`;
            setTimeout(() => triggerVictoryScreen(0, 0), 1500);
        } else {
            const hint = guess < secretNum ? "Too low! 📈" : "Too high! 📉";
            document.getElementById("guess-hint").textContent = hint;
            document.getElementById("guess-att-text").textContent = `Attempts remaining: ${attemptsLeft}`;
        }
    };
}

// ----------------------------------------------------
// GAME 10: MATH RUSH
// ----------------------------------------------------
function setupMathGame() {
    modalTitle.textContent = "Math Rush";
    htmlGameContainer.classList.remove("hidden");
    liveTimer.classList.remove("hidden");
    
    let a, b, answer, options, questionTimer;
    
    function generateQuestion() {
        a = Math.floor(Math.random() * 30) + 10;
        b = Math.floor(Math.random() * 30) + 1;
        const op = Math.random() < 0.5 ? '+' : '-';
        answer = op === '+' ? a + b : a - b;
        
        // Generate multiple choice options
        const incorrects = new Set();
        while (incorrects.size < 3) {
            const diff = (Math.floor(Math.random() * 10) + 1) * (Math.random() < 0.5 ? 1 : -1);
            if (diff !== 0) incorrects.add(answer + diff);
        }
        options = [answer, ...incorrects].sort(() => Math.random() - 0.5);
        
        htmlGameContainer.innerHTML = `
            <div class="math-box">
                <div class="math-equation">${a} ${op} ${b} = ?</div>
                <div class="math-options">
                    <button class="math-btn" onclick="submitMath(${options[0]})">${options[0]}</button>
                    <button class="math-btn" onclick="submitMath(${options[1]})">${options[1]}</button>
                    <button class="math-btn" onclick="submitMath(${options[2]})">${options[2]}</button>
                    <button class="math-btn" onclick="submitMath(${options[3]})">${options[3]}</button>
                </div>
            </div>
        `;
        
        gameTimeLeft = 4; // 4 seconds per question
        liveTimer.textContent = `Time: 4s`;
        
        if (questionTimer) clearInterval(questionTimer);
        questionTimer = setInterval(() => {
            gameTimeLeft--;
            liveTimer.textContent = `Time: ${gameTimeLeft}s`;
            if (gameTimeLeft <= 0) {
                clearInterval(questionTimer);
                // Time up -> Game over
                const reward = Math.min(100, Math.floor(gameScore / 2));
                triggerVictoryScreen(gameScore, reward);
            }
        }, 1000);
    }
    
    window.submitMath = function(userAnswer) {
        if (userAnswer === answer) {
            gameScore += 10;
            liveScore.textContent = `Score: ${gameScore}`;
            generateQuestion();
        } else {
            // Wrong answer -> Game over
            if (questionTimer) clearInterval(questionTimer);
            const reward = Math.min(100, Math.floor(gameScore / 2));
            triggerVictoryScreen(gameScore, reward);
        }
    };
    
    generateQuestion();
}

// Start
init();
