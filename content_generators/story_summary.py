# content_generators/story_summary.py

import csv

def generate_story_summary(all_posts):
    try:
        with open(log_file, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            tweets = [row[1] for row in reader if len(row) > 1]  # Ensure tweet content exists
        # Create a brief summary (e.g., first two and last two tweets)
        if len(tweets) >= 4:
            summary = " ".join(tweets[:2] + tweets[-2:])
        elif len(tweets) >= 2:
            summary = " ".join(tweets)
        else:
            summary = "an amazing journey filled with unexpected twists and turns."
        # Truncate if too long
        if len(summary) > 200:
            summary = summary[:197] + "..."
        return summary
    except Exception as e:
        print(f"Error generating summary: {e}")
        return "an amazing journey filled with unexpected twists and turns."
