document.addEventListener('DOMContentLoaded', () => {
    const userDataString = localStorage.getItem('currentUserData');
    const sidebarContainer = document.querySelector('.sidebar-container');

    if (userDataString && sidebarContainer) {
        try {
            const userData = JSON.parse(userDataString);
            renderSidebar(userData, sidebarContainer);

            // Hide the sidebar-container on the login/signup page
            if (window.location.pathname.includes('index.html')) {
                sidebarContainer.style.display = 'none';
            }
        } catch (error) {
            console.error("Failed to parse user data from localStorage:", error);
            // If data is corrupt, clear localStorage and redirect to login
            localStorage.clear();
            window.location.href = 'index.html';
        }
    } else if (sidebarContainer) {
        // Not logged in, but a sidebar container exists on the page
        // You can render a default state or hide it
        sidebarContainer.style.display = 'none';
    }
});

function renderSidebar(userData, container) {
    // Render the user's personal details section
    const personalDetailsHTML = `
        <div class="user-info-section">
            <img src="${userData.profilePhoto || 'https://via.placeholder.com/150'}" alt="User Profile Photo" class="profile-photo">
            <h4>${userData.firstName || 'User'}</h4>
            <div class="sidebar-item">
                <a href="profile.html" style="color: inherit; text-decoration: none;">Personal Details</a>
            </div>
        </div>
    `;

    // Render the ride history section
    let rideHistoryHTML = `
        <div class="ride-history-section">
            <h4>Ride History</h4>
            <ul class="ride-history-list">
    `;
    if (userData.rideHistory && userData.rideHistory.length > 0) {
        rideHistoryHTML += userData.rideHistory.map(ride => `
            <li>
                <strong>From:</strong> ${ride.start}<br>
                <strong>To:</strong> ${ride.end}<br>
                ${ride.date}
            </li>
        `).join('');
    } else {
        rideHistoryHTML += '<li>No ride history found.</li>';
    }
    rideHistoryHTML += `
            </ul>
        </div>
    `;

    // Render the logout link
    const logoutHTML = `
        <div class="sidebar-item" id="logoutBtn">
            <a href="index.html" style="color: inherit; text-decoration: none;">Logout</a>
        </div>
    `;

    // Combine and insert into the sidebar container
    container.innerHTML = personalDetailsHTML + rideHistoryHTML + logoutHTML;

    // Add logout functionality
    document.getElementById('logoutBtn').addEventListener('click', () => {
        localStorage.removeItem('loggedInUsername');
        localStorage.removeItem('currentUserData');
    });
}