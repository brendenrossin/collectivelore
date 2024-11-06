# main.py

import os
import schedule
import time
import csv
from dotenv import load_dotenv
from datetime import datetime
from atproto.exceptions import AtProtocolError
import calendar
from content_generators.bluesky_generation_agent import TweetGenerationAgent
from content_generators.bluesky_comment_analysis_agent import CommentAnalysisAgent
from content_generators.story_phase_manager import StoryPhaseManager
from content_generators.story_summary import generate_story_summary
import logging

# Load environment variables
load_dotenv()

# Ensure the logs directory exists
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configure logging
logging.basicConfig(
    filename=os.path.join(log_dir, 'error.log'),
    level=logging.ERROR,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

# Initialize Agents
openai_api_key = os.getenv("OPENAI_API_KEY")
tweet_agent = TweetGenerationAgent(openai_api_key)
comment_agent = CommentAnalysisAgent(openai_api_key)
phase_manager = StoryPhaseManager()

# Reward threshold for logging top examples
REWARD_THRESHOLD = 10  # Example threshold

def log_tweet(timestamp, post_uri, tweet, likes, retweets, comments, reward):
    try:
        # Ensure the logs directory exists
        os.makedirs(log_dir, exist_ok=True)
        # Check if the CSV file exists; if not, write headers
        file_exists = os.path.isfile(os.path.join(log_dir, 'tweet_logs.csv'))
        with open(os.path.join(log_dir, 'tweet_logs.csv'), mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['Timestamp', 'URI', 'Tweet', 'Likes', 'Retweets', 'Comments', 'Reward'])
        # Log the tweet data
        writer.writerow([timestamp, post_uri, tweet, likes, retweets, comments, reward])
    except Exception as e:
        logging.error(f"Failed to log tweet: {e}")

def update_top_examples(tweet, reward):
    if reward >= REWARD_THRESHOLD:
        try:
            os.makedirs('logs', exist_ok=True)
            with open('logs/top_examples.txt', 'a', encoding='utf-8') as f:
                f.write(f"{tweet}\n")
            print("Added post to top examples.")
        except Exception as e:
            logging.error(f"Error updating top examples: {e}")
            print(f"Error updating top examples: {e}")

def is_content_safe(tweet):
    safety_prompt = (
        f"Is the following post appropriate for a general audience and free from offensive or controversial content? "
        f"Respond with 'Yes' or 'No'.\n\nPost: \"{tweet}\""
    )
    try:
        response = tweet_agent.llm(prompt=safety_prompt, max_tokens=3, temperature=0)
        return response.strip().lower() == "yes"
    except Exception as e:
        logging.error(f"Error checking content safety: {e}")
        print(f"Error checking content safety: {e}")
        return False

def analyze_comment(comment):
    return comment_agent.analyze_comment(comment)

def select_valid_comment(comments):
    if not comments:
        return None
    # Sort comments by like count descending
    sorted_comments = sorted(comments, key=lambda x: x['likes'], reverse=True)
    
    # Iterate through the sorted comments until a valid one is found
    for comment in sorted_comments:
        # print(
        #     f"Comment: {comment['text']}, "
        #     f"Likes: {comment['likes']}, "
        #     f"Retweets: {comment['retweets']}"
        # )
        if analyze_comment(comment['text']):
            return comment['text']
    
    # If no valid comment is found, return None
    return None

def post_tweet(tweet):
    return tweet_agent.post_tweet(tweet)

def fetch_metrics(post_uri):
    try:
        post = tweet_agent.client.get_post(post_uri)
        likes = post.get('like_count', 0)
        retweets = post.get('repost_count', 0)
        comments = comment_agent.fetch_comments(post_uri)
        return likes, retweets, comments
    except AtProtocolError as e:
        logging.error(f"Error fetching metrics for post {post_uri}: {e}")
        print(f"Error fetching metrics for post {post_uri}: {e}")
        return 0, 0, []

def job():
    today = datetime.now()
    phase = phase_manager.get_current_phase()
    day = today.day
    month = today.month
    year = today.year
    total_days = calendar.monthrange(year, month)[1]

    print(f"Today is day {day} of the month out of {total_days} days. Phase: {phase}")

    tweets_to_post = []

    if phase == "exposition" and day == 1:
        # Generate and post the first introduction tweet
        intro_tweet = (
            f"Welcome to a new month of our interactive story! 📖✨ "
            f"This month's tale is yet unwritten, and it's up to you to shape its journey. "
            f"For the next {total_days} days, your comments will help determine the plot twists and turns. "
            f"Let's embark on this adventure together! 🚀 #InteractiveStory"
        )
        tweets_to_post.append(intro_tweet)
        
        # Generate the first story tweet
        first_story_tweet = tweet_agent.generate_tweet(last_tweet=None, user_comment=None)
        tweets_to_post.append(first_story_tweet)
    else:
        # Continue the storyline based on engagement and phase
        recent_posts, last_post_id = tweet_agent.fetch_recent_posts()

        # Remove any string that starts with "Welcome to a new month"
        recent_posts = [post for post in recent_posts if not post.startswith("Welcome to a new month")]
        
        # Join the list of strings in recent_posts by a space
        all_posts = " ".join(recent_posts)

        if len(recent_posts) == 0:
            # If no previous post exists, start exposition
            # Generate and post the first introduction tweet
            days_remaining = total_days - day
            intro_tweet = (
                f"Welcome to a new month of our interactive story! 📖✨ "
                f"This month's tale is yet unwritten, and it's up to you to shape its journey. "
                f"For the next {days_remaining} days, your comments will help determine the plot twists and turns. "
                f"Let's embark on this adventure together! 🚀 #CollectiveLore"
            )
            tweets_to_post.append(intro_tweet)
            next_post = tweet_agent.generate_tweet(last_tweet=None, user_comment=None)
            tweets_to_post.append(next_post)
        else:
            try:
                # Fetch comments on the last post
                comments = comment_agent.fetch_comments(last_post_id)
                # Select the most valid comment
                valid_comment = select_valid_comment(comments)
                if valid_comment:
                    next_post = tweet_agent.generate_tweet(last_tweet=all_posts, user_comment=valid_comment)
                    tweets_to_post.append(next_post)
                else:
                    next_post = tweet_agent.generate_tweet(last_tweet=all_posts, user_comment=None)
                    tweets_to_post.append(next_post)
            except Exception as e:
                print(f"Error fetching comments: {e}")

    if phase == "resolution" and day == total_days:
        resolution_tweet = (
            f"And so concludes our story for {month}. 🏁✨ "
            f"Thank you all for your incredible contributions and engagement throughout the month. "
            f"Stay tuned for next month's adventure! 📚🚀 #CollectiveLore"
        )
        tweets_to_post.append(resolution_tweet)

    print('printing tweets to post')
    print(tweets_to_post)

    for post in tweets_to_post:
        # Ensure the post is safe
        safe = is_content_safe(post)
        if not safe:
            print("Generated post failed content safety check. Skipping.")
            continue

        # Post the tweet and collect metrics
        post_id, post_uri = post_tweet(post)
        if not post_uri:
            continue

        # Fetch metrics
        # likes, retweets, comments_fetched = fetch_metrics(post_id)

        # Calculate reward
        # reward = calculate_reward(likes, retweets, len(comments_fetched))

        # Log the post
        # timestamp = datetime.now().isoformat()
        # log_tweet(timestamp, post_uri, post, likes, retweets, len(comments_fetched), reward)

        # Update top examples if necessary
        # update_top_examples(post, reward)

if __name__ == "__main__":
    job()  # Run the job immediately

# Schedule the job every day at 09:00 AM
# schedule.every().day.at("11:40").do(job)

# print("Storyline bot is running and will post daily posts at 10:00 AM.")

# while True:
#     schedule.run_pending()
#     time.sleep(60)  # Wait one minute
