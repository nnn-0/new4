// GPS Location Service for Smart Attendance System
// Ensures faculty can only mark attendance from within college premises

class LocationService {
    constructor() {
        // Vemu Institute of Technology GPS coordinates
        // Located at P. Kothakota, Tirupati-Chittoor Highway, Chittoor District
        this.collegeCoordinates = {
            latitude: 13.4182,   // Center of VEMU boundary coordinates
            longitude: 79.1158,  // Center of VEMU boundary coordinates  
            name: "Vemu Institute of Technology, Chittoor"
        };
        
        // Allowed radius in meters (500m = 0.5km coverage area)
        this.allowedRadius = 500;
        
        this.userLocation = null;
        this.locationAllowed = false;
        this.watchId = null;
    }

    // Calculate distance between two GPS coordinates using Haversine formula
    calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371e3; // Earth's radius in meters
        const φ1 = lat1 * Math.PI/180;
        const φ2 = lat2 * Math.PI/180;
        const Δφ = (lat2-lat1) * Math.PI/180;
        const Δλ = (lon2-lon1) * Math.PI/180;

        const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                Math.cos(φ1) * Math.cos(φ2) *
                Math.sin(Δλ/2) * Math.sin(Δλ/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

        return R * c; // Distance in meters
    }

    // Show loading screen with GPS tracking message
    showLocationLoading() {
        const loadingHTML = `
            <div id="gps-loading" class="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center" 
                 style="background: rgba(0,0,0,0.9); z-index: 9999;">
                <div class="text-center text-white">
                    <div class="spinner-border text-primary mb-3" role="status" style="width: 3rem; height: 3rem;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <h4><i class="fas fa-map-marker-alt me-2"></i>GPS Tracking</h4>
                    <p class="mb-2">Verifying your location...</p>
                    <p class="text-muted small">Please ensure location services are enabled</p>
                    <div class="mt-3">
                        <div id="location-status" class="badge bg-warning">
                            <i class="fas fa-satellite-dish me-1"></i>Acquiring GPS signal...
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', loadingHTML);
    }

    // Update location status
    updateLocationStatus(message, type = 'warning') {
        const statusElement = document.getElementById('location-status');
        if (statusElement) {
            const iconMap = {
                'warning': 'fa-satellite-dish',
                'success': 'fa-check-circle',
                'danger': 'fa-exclamation-triangle'
            };
            statusElement.className = `badge bg-${type}`;
            statusElement.innerHTML = `<i class="fas ${iconMap[type]} me-1"></i>${message}`;
        }
    }

    // Check if user is within college premises
    async getCurrentLocation() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Geolocation is not supported by this browser'));
                return;
            }

            const options = {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 60000
            };

            this.updateLocationStatus('Getting precise location...', 'warning');

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    this.userLocation = {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        accuracy: position.coords.accuracy
                    };
                    
                    const distance = this.calculateDistance(
                        this.userLocation.latitude,
                        this.userLocation.longitude,
                        this.collegeCoordinates.latitude,
                        this.collegeCoordinates.longitude
                    );

                    this.locationAllowed = distance <= this.allowedRadius;
                    
                    if (this.locationAllowed) {
                        this.updateLocationStatus(`Location verified - ${Math.round(distance)}m from college`, 'success');
                        setTimeout(() => resolve(true), 1000);
                    } else {
                        this.updateLocationStatus(`Outside college premises - ${Math.round(distance)}m away`, 'danger');
                        setTimeout(() => resolve(false), 2000);
                    }
                },
                (error) => {
                    let errorMessage = 'Location access denied';
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            errorMessage = 'Location access denied by user';
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMessage = 'Location information unavailable';
                            break;
                        case error.TIMEOUT:
                            errorMessage = 'Location request timeout';
                            break;
                    }
                    this.updateLocationStatus(errorMessage, 'danger');
                    setTimeout(() => reject(new Error(errorMessage)), 2000);
                },
                options
            );
        });
    }

    // Remove loading screen
    hideLocationLoading() {
        const loadingElement = document.getElementById('gps-loading');
        if (loadingElement) {
            loadingElement.style.transition = 'opacity 0.5s';
            loadingElement.style.opacity = '0';
            setTimeout(() => loadingElement.remove(), 500);
        }
    }

    // Show location error screen
    showLocationError(message) {
        this.hideLocationLoading();
        
        const errorHTML = `
            <div id="location-error" class="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center" 
                 style="background: rgba(220, 53, 69, 0.95); z-index: 9999;">
                <div class="text-center text-white p-4">
                    <div class="mb-4">
                        <i class="fas fa-map-marker-alt-slash" style="font-size: 4rem; opacity: 0.8;"></i>
                    </div>
                    <h3>Access Restricted</h3>
                    <p class="lead">${message}</p>
                    <div class="alert alert-light text-dark mt-4">
                        <h6><i class="fas fa-info-circle me-2"></i>Attendance Policy</h6>
                        <p class="mb-2">• Attendance can only be marked from within college premises</p>
                        <p class="mb-2">• Please ensure you are inside the college campus</p>
                        <p class="mb-0">• Contact IT support if you need assistance</p>
                    </div>
                    <button class="btn btn-light mt-3" onclick="location.reload()">
                        <i class="fas fa-sync me-2"></i>Try Again
                    </button>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', errorHTML);
    }

    // Main function to verify location before allowing access
    async verifyLocation() {
        try {
            this.showLocationLoading();
            
            const isAllowed = await this.getCurrentLocation();
            
            if (isAllowed) {
                this.hideLocationLoading();
                return true;
            } else {
                const distance = this.calculateDistance(
                    this.userLocation.latitude,
                    this.userLocation.longitude,
                    this.collegeCoordinates.latitude,
                    this.collegeCoordinates.longitude
                );
                
                this.showLocationError(`You are currently ${Math.round(distance)} meters away from ${this.collegeCoordinates.name}. Please come to the college campus to mark attendance.`);
                return false;
            }
        } catch (error) {
            this.showLocationError(`Location verification failed: ${error.message}. Please enable location services and try again.`);
            return false;
        }
    }

    // Get location info for debugging
    getLocationInfo() {
        if (!this.userLocation) return null;
        
        const distance = this.calculateDistance(
            this.userLocation.latitude,
            this.userLocation.longitude,
            this.collegeCoordinates.latitude,
            this.collegeCoordinates.longitude
        );
        
        return {
            userLocation: this.userLocation,
            collegeLocation: this.collegeCoordinates,
            distance: Math.round(distance),
            allowed: this.locationAllowed,
            accuracy: this.userLocation.accuracy
        };
    }
}

// Initialize location service
const locationService = new LocationService();

// Auto-verify location when page loads
document.addEventListener('DOMContentLoaded', async function() {
    // Only verify location on login and attendance pages
    const requiresLocation = window.location.pathname.includes('login') || 
                           window.location.pathname.includes('attendance') ||
                           window.location.pathname.includes('mark_attendance') ||
                           window.location.pathname === '/';
    
    if (requiresLocation) {
        const isAllowed = await locationService.verifyLocation();
        
        if (!isAllowed) {
            // Disable all form submissions if location is not allowed
            const forms = document.querySelectorAll('form');
            forms.forEach(form => {
                form.addEventListener('submit', function(e) {
                    e.preventDefault();
                    alert('Location verification required. Please ensure you are within college premises.');
                });
            });
        }
    }
});