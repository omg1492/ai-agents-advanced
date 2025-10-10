"""Mock data layer for Chef Services MCP server.

This module provides in-memory mock data for chefs, services, and availability.
Chef availability is dynamically generated on module import based on current date.
"""

from datetime import datetime, date, timedelta
from typing import Dict, List
import random


# ============================================================================
# Mock Chefs
# ============================================================================

MOCK_CHEFS = [
    {
        "chef_id": "chef_001",
        "name": "Alessandro Rossi",
        "specialties": ["Italian", "Mediterranean", "Pasta"],
        "experience_years": 15,
        "rate_per_hour": 120,
        "bio": "Award-winning chef specializing in authentic regional Italian cuisine with 15 years of experience in Michelin-starred restaurants.",
        "certifications": ["Michelin-trained", "ServSafe", "Master Sommelier Level 1"]
    },
    {
        "chef_id": "chef_002",
        "name": "Marcus Johnson",
        "specialties": ["BBQ", "Southern", "Grilling"],
        "experience_years": 12,
        "rate_per_hour": 100,
        "bio": "BBQ pit master and competition winner specializing in slow-smoked meats and Southern comfort food.",
        "certifications": ["ServSafe", "Kansas City BBQ Society Judge"]
    },
    {
        "chef_id": "chef_003",
        "name": "Yuki Tanaka",
        "specialties": ["Japanese", "Sushi", "Asian Fusion"],
        "experience_years": 18,
        "rate_per_hour": 150,
        "bio": "Master sushi chef trained in Tokyo with expertise in traditional Japanese cuisine and modern fusion techniques.",
        "certifications": ["Tokyo Sushi Academy", "ServSafe", "Sake Sommelier"]
    },
    {
        "chef_id": "chef_004",
        "name": "Marie Dubois",
        "specialties": ["French", "Pastry", "Desserts"],
        "experience_years": 14,
        "rate_per_hour": 130,
        "bio": "Classically trained pastry chef from Le Cordon Bleu Paris, specializing in elegant French desserts and pastries.",
        "certifications": ["Le Cordon Bleu", "ServSafe", "Master Pâtissier"]
    },
    {
        "chef_id": "chef_005",
        "name": "Carlos Rodriguez",
        "specialties": ["Mexican", "Latin American", "Tex-Mex"],
        "experience_years": 10,
        "rate_per_hour": 95,
        "bio": "Contemporary Mexican chef bringing authentic flavors and modern techniques to traditional Latin American dishes.",
        "certifications": ["ServSafe", "Culinary Institute of Mexico"]
    },
    {
        "chef_id": "chef_006",
        "name": "Priya Sharma",
        "specialties": ["Indian", "Vegetarian", "Vegan"],
        "experience_years": 11,
        "rate_per_hour": 105,
        "bio": "Plant-based chef specializing in Indian vegetarian and vegan cuisine with focus on health and authentic spices.",
        "certifications": ["ServSafe", "Plant-Based Culinary Institute", "Ayurvedic Nutrition"]
    },
    {
        "chef_id": "chef_007",
        "name": "Thomas Weber",
        "specialties": ["German", "European", "Fine Dining"],
        "experience_years": 16,
        "rate_per_hour": 140,
        "bio": "Fine dining specialist with expertise in modern European cuisine and classical German cooking techniques.",
        "certifications": ["Michelin-trained", "ServSafe", "Master Chef Germany"]
    },
    {
        "chef_id": "chef_008",
        "name": "Sophia Chen",
        "specialties": ["Chinese", "Asian", "Dim Sum"],
        "experience_years": 13,
        "rate_per_hour": 110,
        "bio": "Expert in regional Chinese cuisines, particularly Cantonese dim sum and Szechuan spicy dishes.",
        "certifications": ["ServSafe", "Hong Kong Culinary Academy"]
    },
    {
        "chef_id": "chef_009",
        "name": "Emma Thompson",
        "specialties": ["British", "Farm-to-Table", "Organic"],
        "experience_years": 9,
        "rate_per_hour": 90,
        "bio": "Farm-to-table chef passionate about locally sourced ingredients and modern British cuisine.",
        "certifications": ["ServSafe", "Organic Certification", "Farm-to-Table Specialist"]
    },
    {
        "chef_id": "chef_010",
        "name": "Ahmed Al-Mansour",
        "specialties": ["Middle Eastern", "Mediterranean", "Halal"],
        "experience_years": 14,
        "rate_per_hour": 115,
        "bio": "Middle Eastern cuisine expert specializing in authentic Mediterranean and halal-certified cooking.",
        "certifications": ["ServSafe", "Halal Certification", "Mediterranean Culinary Institute"]
    }
]


# ============================================================================
# Mock Services
# ============================================================================

MOCK_SERVICES = [
    {
        "service_id": "svc_001",
        "type": "catering",
        "name": "Corporate Lunch Catering",
        "base_price_per_person": 25,
        "min_guests": 10,
        "max_guests": 200,
        "includes": ["Setup", "Buffet service", "Cleanup", "Standard tableware"],
        "description": "Professional catering for business events with a variety of menu options suitable for corporate settings."
    },
    {
        "service_id": "svc_002",
        "type": "catering",
        "name": "Wedding Catering Premium",
        "base_price_per_person": 75,
        "min_guests": 50,
        "max_guests": 300,
        "includes": ["Setup", "Plated service", "Cleanup", "Premium china", "Wait staff", "Wine service"],
        "description": "Elegant wedding catering with premium ingredients, plated service, and dedicated staff for your special day."
    },
    {
        "service_id": "svc_003",
        "type": "private_chef",
        "name": "Private Dinner Service",
        "base_price_per_person": 95,
        "min_guests": 2,
        "max_guests": 12,
        "includes": ["Menu planning", "Shopping", "Cooking on-site", "Plated service", "Cleanup"],
        "description": "Intimate private dining experience with a professional chef cooking in your home."
    },
    {
        "service_id": "svc_004",
        "type": "meal_prep",
        "name": "Weekly Meal Prep",
        "base_price_per_person": 120,
        "min_guests": 1,
        "max_guests": 6,
        "includes": ["Menu planning", "Shopping", "5 dinners prepared", "Storage containers", "Reheating instructions"],
        "description": "Weekly meal preparation service providing 5 healthy dinners ready to heat and serve."
    },
    {
        "service_id": "svc_005",
        "type": "catering",
        "name": "Cocktail Party Catering",
        "base_price_per_person": 45,
        "min_guests": 20,
        "max_guests": 150,
        "includes": ["Setup", "Passed hors d'oeuvres", "Cleanup", "Serving staff"],
        "description": "Sophisticated cocktail party service with a variety of passed appetizers and professional presentation."
    },
    {
        "service_id": "svc_006",
        "type": "delivery",
        "name": "Event Delivery Service",
        "base_price_per_person": 15,
        "min_guests": 10,
        "max_guests": 100,
        "includes": ["Food delivery", "Disposable tableware", "Setup assistance"],
        "description": "Convenient delivery of prepared meals with optional setup assistance for your event."
    },
    {
        "service_id": "svc_007",
        "type": "private_chef",
        "name": "Cooking Class Experience",
        "base_price_per_person": 85,
        "min_guests": 4,
        "max_guests": 10,
        "includes": ["Interactive cooking instruction", "All ingredients", "Recipe cards", "Meal service"],
        "description": "Hands-on cooking class in your home with a professional chef teaching and guiding participants."
    },
    {
        "service_id": "svc_008",
        "type": "catering",
        "name": "BBQ Outdoor Catering",
        "base_price_per_person": 35,
        "min_guests": 25,
        "max_guests": 200,
        "includes": ["Setup", "On-site grilling", "Buffet service", "Cleanup"],
        "description": "Outdoor BBQ catering with fresh-grilled meats and sides, perfect for casual gatherings."
    }
]


# ============================================================================
# Dynamic Mock Availability
# ============================================================================

def _generate_chef_availability() -> Dict[str, List[str]]:
    """Generate random blocked dates for each chef for the next 2 months.
    
    Each chef will have 3-8 randomly blocked dates within the next 60 days.
    Uses deterministic seeding based on chef_id for consistency during server lifetime.
    
    Returns:
        Dict mapping chef_id to list of blocked date strings (YYYY-MM-DD format)
    """
    availability = {}
    today = date.today()
    
    for chef in MOCK_CHEFS:
        chef_id = chef["chef_id"]
        
        # Use chef_id for deterministic randomness (consistent per server session)
        # Extract numeric part: "chef_001" -> 1
        chef_num = int(chef_id.split("_")[1])
        rng = random.Random(chef_num)
        
        # Each chef has 3-8 blocked dates
        num_blocked = rng.randint(3, 8)
        
        # Generate random dates within next 60 days
        blocked_dates = set()
        for _ in range(num_blocked):
            days_offset = rng.randint(1, 60)
            blocked_date = today + timedelta(days=days_offset)
            blocked_dates.add(blocked_date.strftime("%Y-%m-%d"))
        
        availability[chef_id] = sorted(list(blocked_dates))
    
    return availability


# Generate availability on module import
MOCK_AVAILABILITY: Dict[str, List[str]] = _generate_chef_availability()


# ============================================================================
# Session State
# ============================================================================

# Session-level order counter (resets on server restart)
_order_counter = 0


def get_next_order_id() -> str:
    """Generate next sequential order ID.
    
    Returns:
        Order ID in format "order_NNNN" (e.g., "order_0001")
    """
    global _order_counter
    _order_counter += 1
    return f"order_{_order_counter:04d}"


# ============================================================================
# Helper Functions
# ============================================================================

def parse_date(date_str: str) -> date | None:
    """Parse YYYY-MM-DD string to date object.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        
    Returns:
        date object or None if parsing fails
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def is_date_available(chef_id: str, date_str: str) -> bool:
    """Check if a chef is available on a given date.
    
    Args:
        chef_id: Chef identifier (e.g., "chef_001")
        date_str: Date string in YYYY-MM-DD format
        
    Returns:
        True if chef is available, False if blocked
    """
    blocked = MOCK_AVAILABILITY.get(chef_id, [])
    return date_str not in blocked


def get_next_available_date(chef_id: str, from_date: date) -> str:
    """Find next available date for a chef (within 90 days).
    
    Args:
        chef_id: Chef identifier (e.g., "chef_001")
        from_date: Starting date to search from
        
    Returns:
        Next available date in YYYY-MM-DD format, or empty string if none found
    """
    blocked = MOCK_AVAILABILITY.get(chef_id, [])
    for i in range(1, 91):
        next_date = from_date + timedelta(days=i)
        if next_date.strftime("%Y-%m-%d") not in blocked:
            return next_date.strftime("%Y-%m-%d")
    return ""


# ============================================================================
# Module Initialization Logging
# ============================================================================

if __name__ != "__main__":
    # Log availability generation on import (not when running this file directly)
    print(f"Generated chef availability for next 60 days from {date.today()}")
    for chef_id, dates in MOCK_AVAILABILITY.items():
        print(f"  {chef_id}: {len(dates)} blocked dates")
