// Auto-refresh leaderboard every 5 seconds
setInterval(() => {
    if (window.location.pathname === '/public_leaderboard' || window.location.pathname === '/') {
        location.reload();
    }
}, 5000);

// Add flash animation for score changes
function addFlashAnimation(element) {
    element.classList.add('flash');
    setTimeout(() => {
        element.classList.remove('flash');
    }, 1000);
}

// Flash animation CSS
const style = document.createElement('style');
style.textContent = `
.flash {
    animation: flashAnim 1s ease;
}
@keyframes flashAnim {
    0% { background: rgba(0,255,150,0.14); transform: scale(1.01); }
    100% { background: transparent; transform: scale(1); }
}
`;
document.head.appendChild(style);
