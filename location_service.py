import math
import logging

class LocationService:
    def __init__(self):
        # VEMU Institute of Technology boundary coordinates (Updated precise GPS coordinates from map)
        self.college_boundary = [
            (13.417390, 79.116548),    # Point 1 (northeast corner)
            (13.417455, 79.115000),    # Point 2 (northwest corner)
            (13.419012, 79.115183),    # Point 3 (southwest corner)
            (13.418937, 79.116615),    # Point 4 (southeast corner)
        ]
        
        # Calculate circle center and radius from boundary points
        self.college_center = self._calculate_center_point()
        self.college_radius = self._calculate_radius_from_boundary()
    
    def _calculate_center_point(self):
        """
        Calculate the center point of college boundary
        """
        avg_lat = sum(point[0] for point in self.college_boundary) / len(self.college_boundary)
        avg_lon = sum(point[1] for point in self.college_boundary) / len(self.college_boundary)
        return avg_lat, avg_lon
    
    def _calculate_radius_from_boundary(self):
        """
        Calculate the radius needed to encompass all boundary points
        """
        center_lat, center_lon = self.college_center
        max_distance = 0
        
        for point in self.college_boundary:
            distance = self.calculate_distance(center_lat, center_lon, point[0], point[1])
            max_distance = max(max_distance, distance)
        
        # Add 50m buffer to ensure all boundary points are included
        return max_distance + 50
        
    def is_point_in_polygon(self, latitude, longitude):
        """
        Ray-casting algorithm to check if point is inside polygon defined by A,B,C,D boundary points
        """
        x, y = longitude, latitude
        n = len(self.college_boundary)
        inside = False
        
        # Use proper ray-casting algorithm
        j = n - 1
        for i in range(n):
            xi, yi = self.college_boundary[i][1], self.college_boundary[i][0]  # lon, lat
            xj, yj = self.college_boundary[j][1], self.college_boundary[j][0]  # lon, lat
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate distance between two points in meters using Haversine formula
        """
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) * math.sin(delta_lon / 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def is_within_college_premises(self, latitude, longitude, buffer_meters=2500):
        """
        Check if user is within college premises using polygon boundary (A,B,C,D points)
        Uses larger buffer for GPS accuracy issues
        """
        try:
            # First check if point is inside the boundary polygon
            if self.is_point_in_polygon(latitude, longitude):
                logging.info(f"Location {latitude}, {longitude} is inside college polygon boundary")
                return True, "Inside college premises"
            
            # If not inside, check if within buffer distance from boundary (increased for GPS accuracy)
            min_distance = float('inf')
            for point in self.college_boundary:
                distance = self.calculate_distance(latitude, longitude, point[0], point[1])
                min_distance = min(min_distance, distance)
            
            # Allow larger buffer zone due to GPS accuracy issues
            if min_distance <= buffer_meters:
                logging.info(f"Location {latitude}, {longitude} is within {buffer_meters}m buffer zone (GPS accuracy adjustment)")
                return True, f"Within college area (GPS accuracy adjusted)"
            
            logging.warning(f"Location {latitude}, {longitude} is {min_distance:.0f}m from college boundary")
            return False, f"You are {min_distance:.0f}m away from college premises"
            
        except Exception as e:
            logging.error(f"Error validating location: {e}")
            return False, "Location validation failed"
    

    
    def is_within_college_circle(self, latitude, longitude):
        """
        Check if user is within the college circular boundary
        """
        try:
            center_lat, center_lon = self.college_center
            distance_from_center = self.calculate_distance(latitude, longitude, center_lat, center_lon)
            
            if distance_from_center <= self.college_radius:
                logging.info(f"Location {latitude}, {longitude} is {distance_from_center:.0f}m from college center (within {self.college_radius:.0f}m radius)")
                return True, f"Inside college premises ({distance_from_center:.0f}m from center)"
            else:
                logging.warning(f"Location {latitude}, {longitude} is {distance_from_center:.0f}m from college center (outside {self.college_radius:.0f}m radius)")
                return False, f"You are {distance_from_center:.0f}m from college center (allowed radius: {self.college_radius:.0f}m)"
                
        except Exception as e:
            logging.error(f"Error checking circle boundary: {e}")
            return False, "Location validation failed"
    
    def get_college_center(self):
        """
        Get the college center coordinates
        """
        return self.college_center
    
    def validate_attendance_location(self, latitude, longitude):
        """
        Main validation function for attendance marking
        """
        if not latitude or not longitude:
            return False, "Location coordinates are required"
        
        try:
            lat = float(latitude)
            lon = float(longitude)
            
            # Validate coordinate ranges
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return False, "Invalid GPS coordinates"
            
            return self.is_within_college_premises(lat, lon)
            
        except (ValueError, TypeError):
            return False, "Invalid location data format"

# Initialize location service
location_service = LocationService()