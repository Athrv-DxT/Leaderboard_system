// Store previous leaderboard state for animations
let previousLeaderboard = [];
let isAnimating = false;

// Auto-refresh leaderboard every 3 seconds for faster updates
setInterval(() => {
    if (window.location.pathname === '/public_leaderboard' || window.location.pathname === '/') {
        fetchLeaderboardData();
    }
}, 3000);

// Fetch leaderboard data and animate changes
async function fetchLeaderboardData() {
    try {
        showLoading();
        const response = await fetch('/api/leaderboard');
        if (!response.ok) {
            throw new Error('Failed to fetch leaderboard');
        }
        const newLeaderboard = await response.json();
        
        if (previousLeaderboard.length > 0) {
            animateLeaderboardChanges(previousLeaderboard, newLeaderboard);
        }
        
        previousLeaderboard = [...newLeaderboard];
        updateLeaderboardDisplay(newLeaderboard);
        hideLoading();
    } catch (error) {
        console.error('Error fetching leaderboard:', error);
        hideLoading();
        showErrorMessage('Failed to update leaderboard. Retrying...');
    }
}

// Show error message
function showErrorMessage(message) {
    let errorDiv = document.getElementById('error-message');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.id = 'error-message';
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(255, 0, 0, 0.9);
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            z-index: 1000;
            font-family: 'Poppins', sans-serif;
        `;
        document.body.appendChild(errorDiv);
    }
    errorDiv.textContent = message;
    setTimeout(() => {
        if (errorDiv) errorDiv.remove();
    }, 3000);
}

// Animate leaderboard changes
function animateLeaderboardChanges(oldData, newData) {
    if (isAnimating) return;
    isAnimating = true;
    
    // Create maps for easy lookup
    const oldMap = new Map(oldData.map(player => [player.name, player]));
    const newMap = new Map(newData.map(player => [player.name, player]));
    
    // Find players who moved up or down
    const changes = [];
    
    newData.forEach((newPlayer, newIndex) => {
        const oldPlayer = oldMap.get(newPlayer.name);
        if (oldPlayer) {
            const oldIndex = oldData.findIndex(p => p.name === newPlayer.name);
            if (oldIndex !== newIndex) {
                changes.push({
                    name: newPlayer.name,
                    oldRank: oldIndex + 1,
                    newRank: newIndex + 1,
                    direction: newIndex < oldIndex ? 'up' : 'down',
                    isTop3: newIndex < 3
                });
            }
        }
    });
    
    // Animate changes
    changes.forEach(change => {
        animateRankChange(change);
    });
    
    setTimeout(() => {
        isAnimating = false;
    }, 2000);
}

// Animate individual rank changes
function animateRankChange(change) {
    const playerElement = document.querySelector(`[data-player="${change.name}"]`);
    if (!playerElement) return;
    
    // Add movement animation
    playerElement.classList.add('rank-change', change.direction);
    
    // Special effects for top 3
    if (change.isTop3 && change.direction === 'up') {
        createCelebrationEffect(playerElement);
        playRankUpSound();
    }
    
    // Remove animation classes after animation completes
    setTimeout(() => {
        playerElement.classList.remove('rank-change', change.direction);
    }, 1500);
}

// Create celebration effect for top 3
function createCelebrationEffect(element) {
    const rect = element.getBoundingClientRect();
    
    // Create confetti particles
    for (let i = 0; i < 20; i++) {
        createConfetti(rect.left + rect.width / 2, rect.top + rect.height / 2);
    }
    
    // Add glow effect
    element.classList.add('celebration-glow');
    setTimeout(() => {
        element.classList.remove('celebration-glow');
    }, 3000);
}

// Create confetti particle
function createConfetti(x, y) {
    const confetti = document.createElement('div');
    confetti.className = 'confetti';
    confetti.style.left = x + 'px';
    confetti.style.top = y + 'px';
    confetti.style.backgroundColor = getRandomColor();
    
    document.body.appendChild(confetti);
    
    // Animate confetti
    const angle = Math.random() * 360;
    const velocity = 50 + Math.random() * 100;
    const gravity = 0.5;
    let vx = Math.cos(angle * Math.PI / 180) * velocity;
    let vy = Math.sin(angle * Math.PI / 180) * velocity;
    let posX = x;
    let posY = y;
    
    function animateConfetti() {
        posX += vx;
        posY += vy;
        vy += gravity;
        
        confetti.style.left = posX + 'px';
        confetti.style.top = posY + 'px';
        confetti.style.opacity = 1 - (posY - y) / 200;
        
        if (posY < window.innerHeight + 50) {
            requestAnimationFrame(animateConfetti);
        } else {
            confetti.remove();
        }
    }
    
    requestAnimationFrame(animateConfetti);
}

// Get random color for confetti
function getRandomColor() {
    const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57', '#ff9ff3', '#ffd700', '#c0c0c0'];
    return colors[Math.floor(Math.random() * colors.length)];
}

// Play rank up sound (using Web Audio API)
function playRankUpSound() {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.setValueAtTime(440, audioContext.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(880, audioContext.currentTime + 0.3);
        
        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.3);
    } catch (error) {
        console.log('Audio not supported');
    }
}

// Update leaderboard display
function updateLeaderboardDisplay(leaderboard) {
    // Ensure leaderboard is properly sorted by score (highest first)
    leaderboard.sort((a, b) => b.score - a.score);
    
    // Update ranks after sorting
    leaderboard.forEach((player, index) => {
        player.rank = index + 1;
    });
    
    console.log('Updated leaderboard:', leaderboard.slice(0, 5));
    
    // Update top 3 - ensure correct order
    const top3Cards = document.querySelectorAll('.player-card');
    const top3Order = [1, 0, 2]; // second, first, third (visual order)
    
    top3Order.forEach((cardIndex, visualIndex) => {
        const card = top3Cards[visualIndex];
        const player = leaderboard[cardIndex];
        
        if (player) {
            const nameElement = card.querySelector('p');
            const scoreElement = card.querySelector('span');
            
            // Update name with animation
            if (nameElement && nameElement.textContent !== player.name) {
                nameElement.style.animation = 'nameChange 0.5s ease';
                setTimeout(() => {
                    nameElement.textContent = player.name;
                    nameElement.style.animation = '';
                }, 250);
            }
            
            // Update score with animation
            if (scoreElement && scoreElement.textContent !== player.score.toString()) {
                scoreElement.style.animation = 'scoreChange 0.5s ease';
                setTimeout(() => {
                    scoreElement.textContent = player.score;
                    scoreElement.style.animation = '';
                }, 250);
            }
        } else {
            // Clear if no player at this position
            const nameElement = card.querySelector('p');
            const scoreElement = card.querySelector('span');
            if (nameElement) nameElement.textContent = '—';
            if (scoreElement) scoreElement.textContent = '0';
        }
    });
    
    // Update table rows with smooth transitions
    const tbody = document.getElementById('leaderboard-body');
    if (tbody) {
        // Store current rows for animation
        const currentRows = Array.from(tbody.querySelectorAll('tr'));
        
        // Clear and rebuild
        tbody.innerHTML = '';
        leaderboard.slice(3).forEach((player, index) => {
            const row = document.createElement('tr');
            row.setAttribute('data-player', player.name);
            row.style.opacity = '0';
            row.style.transform = 'translateY(20px)';
            row.innerHTML = `
                <td>${index + 4}</td>
                <td>${player.name}</td>
                <td>${player.score}</td>
            `;
            tbody.appendChild(row);
            
            // Animate in
            setTimeout(() => {
                row.style.transition = 'all 0.5s ease';
                row.style.opacity = '1';
                row.style.transform = 'translateY(0)';
            }, index * 50);
        });
    }
}

// Add comprehensive CSS animations
const style = document.createElement('style');
style.textContent = `
/* Rank change animations */
.rank-change.up {
    animation: rankUp 1.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.rank-change.down {
    animation: rankDown 1.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes rankUp {
    0% { transform: translateY(0) scale(1); }
    25% { transform: translateY(-20px) scale(1.05); background: rgba(0,255,150,0.2); }
    50% { transform: translateY(-10px) scale(1.1); background: rgba(0,255,150,0.3); }
    75% { transform: translateY(-5px) scale(1.05); background: rgba(0,255,150,0.2); }
    100% { transform: translateY(0) scale(1); background: transparent; }
}

@keyframes rankDown {
    0% { transform: translateY(0) scale(1); }
    25% { transform: translateY(10px) scale(0.95); background: rgba(255,100,100,0.2); }
    50% { transform: translateY(5px) scale(0.9); background: rgba(255,100,100,0.3); }
    75% { transform: translateY(2px) scale(0.95); background: rgba(255,100,100,0.2); }
    100% { transform: translateY(0) scale(1); background: transparent; }
}

/* Celebration effects */
.celebration-glow {
    animation: celebrationGlow 3s ease-in-out;
    box-shadow: 0 0 30px rgba(255,215,0,0.8), 0 0 60px rgba(255,215,0,0.4);
}

@keyframes celebrationGlow {
    0%, 100% { box-shadow: 0 0 30px rgba(255,215,0,0.8), 0 0 60px rgba(255,215,0,0.4); }
    50% { box-shadow: 0 0 50px rgba(255,215,0,1), 0 0 100px rgba(255,215,0,0.6); }
}

/* Confetti */
.confetti {
    position: fixed;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    pointer-events: none;
    z-index: 1000;
    animation: confettiFall 2s ease-out forwards;
}

@keyframes confettiFall {
    0% { transform: translateY(0) rotate(0deg); opacity: 1; }
    100% { transform: translateY(200px) rotate(720deg); opacity: 0; }
}

/* Name and score change animations */
@keyframes nameChange {
    0% { transform: scale(1); color: #fff; }
    50% { transform: scale(1.1); color: #ffd700; }
    100% { transform: scale(1); color: #fff; }
}

@keyframes scoreChange {
    0% { transform: scale(1); color: #bff1ff; }
    50% { transform: scale(1.2); color: #4CAF50; }
    100% { transform: scale(1); color: #bff1ff; }
}

/* Enhanced table row animations */
#leaderboard-body tr {
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    position: relative;
}

#leaderboard-body tr:hover {
    background: rgba(255,255,255,0.05);
    transform: translateX(10px);
    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
}

#leaderboard-body tr:nth-child(odd) {
    background: rgba(255,255,255,0.02);
}

#leaderboard-body tr:nth-child(even) {
    background: rgba(255,255,255,0.01);
}

/* Flash animation for score changes */
.flash {
    animation: flashAnim 1s ease;
}

@keyframes flashAnim {
    0% { background: rgba(0,255,150,0.14); transform: scale(1.01); }
    100% { background: transparent; transform: scale(1); }
}
`;
document.head.appendChild(style);

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Add data attributes to table rows for easier selection
    const rows = document.querySelectorAll('#leaderboard-body tr');
    rows.forEach(row => {
        const nameCell = row.querySelector('td:nth-child(2)');
        if (nameCell) {
            row.setAttribute('data-player', nameCell.textContent.trim());
        }
    });
    
    // Add loading indicator
    addLoadingIndicator();
    
    // Fetch initial data
    fetchLeaderboardData();
});

// Add loading indicator
function addLoadingIndicator() {
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loading-indicator';
    loadingDiv.style.cssText = `
        position: fixed;
        top: 20px;
        left: 20px;
        background: rgba(0, 150, 255, 0.9);
        color: white;
        padding: 8px 15px;
        border-radius: 20px;
        z-index: 1000;
        font-family: 'Poppins', sans-serif;
        font-size: 14px;
        display: none;
    `;
    loadingDiv.innerHTML = '🔄 Updating...';
    document.body.appendChild(loadingDiv);
}

// Show/hide loading indicator
function showLoading() {
    const loading = document.getElementById('loading-indicator');
    if (loading) loading.style.display = 'block';
}

function hideLoading() {
    const loading = document.getElementById('loading-indicator');
    if (loading) loading.style.display = 'none';
}
