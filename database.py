# database.py - Updated for Supabase
import os
from supabase import create_client, Client
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get Supabase credentials from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        supabase = None
else:
    logger.warning("Supabase credentials not found. Statistics will not be saved.")

def init_db():
    """Initialize the database - For Supabase, tables should be created manually"""
    if not supabase:
        logger.warning("Supabase not configured. Skipping database initialization.")
        return
    
    try:
        # Check if table exists, create if it doesn't
        result = supabase.table("stats").select("count", count="exact").execute()
        logger.info("Stats table verified successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

def increment_stat(key):
    """Increment a statistic counter"""
    if not supabase:
        return
    
    try:
        # Try to update existing record
        result = supabase.table("stats") \
            .select("*") \
            .eq("stat_key", key) \
            .execute()
        
        if result.data:
            # Update existing record
            current_value = result.data[0].get("stat_value", 0)
            supabase.table("stats") \
                .update({"stat_value": current_value + 1}) \
                .eq("stat_key", key) \
                .execute()
        else:
            # Insert new record
            supabase.table("stats") \
                .insert({"stat_key": key, "stat_value": 1}) \
                .execute()
                
    except Exception as e:
        logger.error(f"Error incrementing stat '{key}': {e}")

def get_all_stats():
    """Get all statistics"""
    if not supabase:
        return {
            "lessons": 0,
            "integrations": 0,
            "evaluations": 0,
            "total_documents": 0
        }
    
    try:
        result = supabase.table("stats").select("*").execute()
        stats = {item["stat_key"]: item["stat_value"] for item in result.data}
        
        # Ensure all expected keys exist
        return {
            "lessons": stats.get("lessons_generated", 0),
            "integrations": stats.get("integrations_generated", 0),
            "evaluations": stats.get("evaluations_generated", 0),
            "total_documents": stats.get("total_documents", 0)
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {
            "lessons": 0,
            "integrations": 0,
            "evaluations": 0,
            "total_documents": 0
        }