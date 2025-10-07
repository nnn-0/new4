// Global location tracking for attendance system
let userLocation = null;
let locationStatus = 'checking';
let locationCheckInterval = null;

// VEMU Institute of Technology boundary coordinates (ordered clockwise for proper polygon)
const COLLEGE_BOUNDARY = [
    [13.4174095, 79.1136006],  // Point A (southwest corner)
    [13.417660, 79.116551],    // Point B (southeast corner)
    [13.419027, 79.116626],    // Point C (northeast corner) 
    [13.418703, 79.116604],    // Point D (northwest corner)
];

// Calculate circle center from boundary points
const COLLEGE_CENTER = calculateCenterPoint();
const COLLEGE_RADIUS = calculateRadius();

function calculateCenterPoint() {
    let totalLat = 0, totalLon = 0;
    for (let point of COLLEGE_BOUNDARY) {
        totalLat += point[0];
        totalLon += point[1];
    }
    return [totalLat / COLLEGE_BOUNDARY.length, totalLon / COLLEGE_BOUNDARY.length];
}

function calculateRadius() {
    let maxDistance = 0;
    for (let point of COLLEGE_BOUNDARY) {
        let distance = calculateDistance(COLLEGE_CENTER[0], COLLEGE_CENTER[1], point[0], point[1]);
        maxDistance = Math.max(maxDistance, distance);
    }
    return maxDistance + 50; // Add 50m buffer
}

function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371000; // Earth's radius in meters
    const lat1Rad = lat1 * Math.PI / 180;
    const lat2Rad = lat2 * Math.PI / 180;
    const deltaLat = (lat2 - lat1) * Math.PI / 180;
    const deltaLon = (lon2 - lon1) * Math.PI / 180;
    
    const a = Math.sin(deltaLat/2) * Math.sin(deltaLat/2) +
              Math.cos(lat1Rad) * Math.cos(lat2Rad) *
              Math.sin(deltaLon/2) * Math.sin(deltaLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    
    return R * c;
}

document.addEventListener('DOMContentLoaded', function() {
    initializeLocationTracking();
    
    // Check location every 30 seconds
    locationCheckInterval = setInterval(checkLocation, 30000);
});

function initializeLocationTracking() {
    showLocationStatus('Checking your location...', 'info');
    
    if (!navigator.geolocation) {
        showLocationStatus('Location services not supported', 'error');
        disableAttendanceFeatures();
        return;
    }
    
    // Get high accuracy location
    navigator.geolocation.getCurrentPosition(
        handleLocationSuccess,
        handleLocationError,
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 60000
        }
    );
}

function handleLocationSuccess(position) {
    userLocation = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        timestamp: new Date()
    };
    
    console.log('Location obtained:', userLocation);
    verifyLocationWithServer();
}

function handleLocationError(error) {
    console.error('Location error:', error);
    
    let message = 'Location access required';
    switch(error.code) {
        case error.PERMISSION_DENIED:
            message = 'Location access denied. Please enable GPS and refresh.';
            break;
        case error.POSITION_UNAVAILABLE:
            message = 'Location information unavailable. Please check GPS.';
            break;
        case error.TIMEOUT:
            message = 'Location request timed out. Please try again.';
            break;
    }
    
    showLocationStatus(message, 'error');
    disableAttendanceFeatures();
}

function verifyLocationWithServer() {
    fetch('/api/verify_location', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            latitude: userLocation.latitude,
            longitude: userLocation.longitude
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.allowed) {
            locationStatus = 'allowed';
            showLocationStatus(`✓ Location verified at ${data.college_name}`, 'success');
            enableAttendanceFeatures();
        } else {
            locationStatus = 'denied';
            showLocationStatus(`✗ ${data.message}`, 'error');
            disableAttendanceFeatures();
        }
    })
    .catch(error => {
        console.error('Location verification error:', error);
        locationStatus = 'error';
        showLocationStatus('Location verification failed', 'error');
        disableAttendanceFeatures();
    });
}

function checkLocation() {
    if (navigator.geolocation && locationStatus === 'allowed') {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                userLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    timestamp: new Date()
                };
                verifyLocationWithServer();
            },
            function(error) {
                console.log('Background location check failed:', error);
            },
            {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 30000
            }
        );
    }
}

function showLocationStatus(message, type) {
    // Update any existing location status elements
    const statusElements = document.querySelectorAll('.location-status');
    
    let className = 'alert-info';
    let icon = '📍';
    
    switch(type) {
        case 'success':
            className = 'alert-success';
            icon = '✅';
            break;
        case 'error':
            className = 'alert-danger';
            icon = '❌';
            break;
        case 'warning':
            className = 'alert-warning';
            icon = '⚠️';
            break;
    }
    
    statusElements.forEach(element => {
        element.className = `alert ${className} location-status`;
        element.innerHTML = `${icon} ${message}`;
    });
    
    // Also update any specific location display elements
    const locationDisplay = document.getElementById('location-display');
    if (locationDisplay) {
        locationDisplay.className = `alert ${className}`;
        locationDisplay.innerHTML = `${icon} ${message}`;
    }
    
    console.log(`Location Status: ${message}`);
}

function enableAttendanceFeatures() {
    // Enable attendance buttons and forms
    const attendanceButtons = document.querySelectorAll('.attendance-feature');
    attendanceButtons.forEach(button => {
        button.disabled = false;
        button.classList.remove('disabled');
    });
    
    // Enable QR scanning
    const scanButton = document.getElementById('start-camera');
    if (scanButton) {
        scanButton.disabled = false;
    }
    
    // Enable face attendance
    const faceButton = document.querySelector('.face-attendance-btn');
    if (faceButton) {
        faceButton.disabled = false;
    }
}

function disableAttendanceFeatures() {
    // Disable attendance buttons and forms
    const attendanceButtons = document.querySelectorAll('.attendance-feature');
    attendanceButtons.forEach(button => {
        button.disabled = true;
        button.classList.add('disabled');
    });
    
    // Disable QR scanning
    const scanButton = document.getElementById('start-camera');
    if (scanButton) {
        scanButton.disabled = true;
    }
    
    // Disable face attendance
    const faceButton = document.querySelector('.face-attendance-btn');
    if (faceButton) {
        faceButton.disabled = true;
    }
}

// Function to get current user location for other scripts
function getCurrentLocation() {
    return userLocation;
}

// Function to check if user is in allowed location
function isLocationAllowed() {
    return locationStatus === 'allowed';
}

// Export functions for other scripts
window.locationTracker = {
    getCurrentLocation: getCurrentLocation,
    isLocationAllowed: isLocationAllowed,
    checkLocation: checkLocation,
    userLocation: function() { return userLocation; }
};

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (!document.hidden && locationStatus !== 'allowed') {
        // Re-check location when page becomes visible
        setTimeout(initializeLocationTracking, 1000);
    }
});

// Clean up interval on page unload
window.addEventListener('beforeunload', function() {
    if (locationCheckInterval) {
        clearInterval(locationCheckInterval);
    }
});