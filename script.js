// script.js

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const messageDisplay = document.getElementById('message');

    if (loginForm) {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault(); // Prevent the default form submission

            // Clear previous messages
            messageDisplay.textContent = '';
            messageDisplay.className = 'message'; // Reset classes

            const username = usernameInput.value.trim();
            const password = passwordInput.value.trim();

            if (!username || !password) {
                showMessage('Please enter both username and password.', 'error');
                return;
            }

            // Simulate an API call to a backend
            // In a real project, you would replace this with a fetch() call to your Node.js backend
            console.log('Attempting login with:', { username, password });

            showMessage('Logging in...', 'info'); // Show a temporary loading message

            try {
                // Simulate network request delay
                await new Promise(resolve => setTimeout(resolve, 1500));

                // --- Simulated Backend Response ---
                // Replace this with actual API call to http://localhost:3000/api/login
               // Inside script.js, within the loginForm.addEventListener('submit', ...)
if (username === 'safestreets' && password === 'password123') {
    showMessage('Login successful! Redirecting...', 'success');
    // In a real application, you would handle session/token storage here
    // For now, we'll redirect to the dashboard page after a short delay
    setTimeout(() => {
        window.location.href = 'Route.html'; // Redirect to the new page
    }, 1500); // Give user time to see success message
} else {
    showMessage('Invalid username or password. Please try again.', 'error');
}
            } catch (error) {
                console.error('Login error:', error);
                showMessage('An unexpected error occurred. Please try again later.', 'error');
            }
        });
    }

    function showMessage(msg, type) {
        messageDisplay.textContent = msg;
        messageDisplay.classList.add('show', type);
        // Remove the message after a few seconds (optional)
        setTimeout(() => {
            messageDisplay.classList.remove('show');
        }, 5000);
    }
    // Review carousel
let currentReview = 0;
const reviews = document.querySelectorAll(".review");

setInterval(() => {
  reviews[currentReview].classList.remove("active");
  currentReview = (currentReview + 1) % reviews.length;
  reviews[currentReview].classList.add("active");
}, 4000);

});