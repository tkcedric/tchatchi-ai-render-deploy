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

# Dans database.py
def increment_stat(key):
    """Increment a statistic counter using an RPC call."""
    if not supabase:
        return
    
    try:
        # On appelle la fonction 'increment_stat_value' directement dans la base de données.
        supabase.rpc('increment_stat_value', {'key_to_increment': key}).execute()
    except Exception as e:
        logger.error(f"Error calling RPC to increment stat '{key}': {e}")

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