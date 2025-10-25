from datetime import datetime

cached_simplified_data = []
last_cache_update = None
sent_messages = {}          # "user_id:code" -> datetime
user_query_counts = {}      # user_id -> {"count": int, "start": datetime}
total_queries = 0
