# main.py

import tweepy
import schedule
import time
import os
import csv
from dotenv import load_dotenv
from datetime import datetime
import calendar
from content_generators.tweet_generation_agent import TweetGenerationAgent
from content_generators.comment_analysis_agent import CommentAnalysisAgent
from content_generators.story_phase_manager import StoryPhaseManager
from content_generators.story_summary import generate_story_summary

# Load environment variables
load_dotenv()

# Initialize Agents
openai_api_key = os.getenv("OPENAI_API_KEY")
tweet_agent = TweetGenerationAgent(openai_api_key)
comment_agent = CommentAnalysisAgent(openai_api_key)
phase_manager = StoryPhaseManager()

# Initialize Twitter Client
auth = tweepy.OAuth1UserHandler(
    os.getenv("TWITTER_API_KEY"),
    os.getenv("TWITTER_API_SECRET"),
    os.getenv("TWITTER_ACCESS_TOKEN"),
    os.getenv("TWITTER_ACCESS_SECRET")
)
twitter_client = tweepy.API(auth)

# Reward threshold for logging top examples
REWARD_THRESHOLD = 10  # Example threshold

def log_tweet(timestamp, tweet, likes, retweets, comments, reward):
    try:
        # Ensure the logs directory exists
        os.makedirs('logs', exist_ok=True)
        # Check if the CSV file exists; if not, write headers
        file_exists = os.path.isfile('logs/tweet_logs.csv')
        with open('logs/tweet_logs.csv', mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['Timestamp', 'Tweet', 'Likes', 'Retweets', 'Comments', 'Reward'])
            writer.writerow([timestamp, tweet, likes, retweets, comments, reward])
        print(f"Logged tweet: {tweet[:50]}... with Reward: {reward}")
    except Exception as e:
        print(f"Error logging tweet: {e}")

def update_top_examples(tweet, reward):
    if reward >= REWARD_THRESHOLD:
        try:
            os.makedirs('logs', exist_ok=True)
            with open('logs/top_examples.txt', 'a', encoding='utf-8') as f:
                f.write(f"{tweet}\n")
            print("Added tweet to top examples.")
        except Exception as e:
            print(f"Error updating top examples: {e}")

def is_content_safe(tweet):
    safety_prompt = (
        f"Is the following tweet appropriate for a general audience and free from offensive or controversial content? "
        f"Respond with 'Yes' or 'No'.\n\nTweet: \"{tweet}\""
    )
    try:
        response = tweet_agent.llm(prompt=safety_prompt, max_tokens=3, temperature=0)
        return response['choices'][0]['text'].strip().lower() == "yes"
    except Exception as e:
        print(f"Error checking content safety: {e}")
        return False

def analyze_comment(comment):
    return comment_agent.analyze_comment(comment)

def select_valid_comment(comments):
    if not comments:
        return None
    # Assuming comments are sorted by like count descending
    most_liked_comment = comments[0]
    if analyze_comment(most_liked_comment):
        return most_liked_comment
    return None

def get_last_tweet():
    # Fetch the most recent tweet from the bot
    try:
        tweets = twitter_client.user_timeline(count=1, tweet_mode='extended')
        if tweets:
            return tweets[0].id, tweets[0].full_text
        else:
            return None, None
    except Exception as e:
        print(f"Error fetching last tweet: {e}")
        return None, None

def fetch_comments(tweet_id):
    try:
        tweet = twitter_client.get_status(tweet_id, tweet_mode='extended')
        query = f'to:{tweet.user.screen_name}'
        comments = twitter_client.search_tweets(q=query, since_id=tweet_id, count=100, tweet_mode='extended')
        # Sort comments by like count descending
        sorted_comments = sorted(comments, key=lambda x: x.favorite_count, reverse=True)
        return [comment.full_text for comment in sorted_comments]
    except Exception as e:
        print(f"Error fetching comments: {e}")
        return []

def calculate_reward(likes, retweets, comments):
    return (likes * 1) + (retweets * 2) + (comments * 0.5)

def job():
    today = datetime.now()
    phase = phase_manager.get_current_phase()
    day = today.day
    month = today.month
    year = today.year
    total_days = calendar.monthrange(year, month)[1]

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
    elif phase == "resolution" and day == total_days:
        # Generate and post the final tweet of the month with summary
        summary = generate_story_summary()
        resolution_tweet = (
            f"And so concludes the story of {summary}. 🏁✨ "
            f"Thank you all for your incredible contributions and engagement throughout the month. "
            f"Stay tuned for next month's adventure! 📚🚀 #StoryConclusion"
        )
        tweets_to_post.append(resolution_tweet)
    else:
        # Continue the storyline based on engagement and phase
        last_tweet_id, last_tweet_content = get_last_tweet()
        if last_tweet_id is None:
            # If no previous tweet exists, start exposition
            next_tweet = tweet_agent.generate_tweet(last_tweet=None, user_comment=None)
            tweets_to_post.append(next_tweet)
        else:
            # Fetch comments on the last tweet
            comments = fetch_comments(last_tweet_id)
            # Select the most valid comment
            valid_comment = select_valid_comment(comments)
            if valid_comment:
                next_tweet = tweet_agent.generate_tweet(last_tweet=last_tweet_content, user_comment=valid_comment)
                tweets_to_post.append(next_tweet)
            else:
                next_tweet = tweet_agent.generate_tweet(last_tweet=last_tweet_content, user_comment=None)
                tweets_to_post.append(next_tweet)

    for tweet in tweets_to_post:
        # Ensure the tweet is safe
        safe = is_content_safe(tweet)
        if not safe:
            print("Generated tweet failed content safety check. Skipping.")
            continue

        # Post the tweet and collect metrics
        try:
            status = twitter_client.update_status(tweet)
            tweet_id = status.id
            print(f"Posted tweet with ID {tweet_id}")
        except Exception as e:
            print(f"Error posting tweet: {e}")
            continue

        # Wait for engagement to accumulate
        time.sleep(3600)  # Wait for 1 hour

        # Fetch updated tweet data
        try:
            tweet_data = twitter_client.get_status(tweet_id, tweet_mode='extended')
            likes = tweet_data.favorite_count
            retweets = tweet_data.retweet_count
            comments_fetched = fetch_comments(tweet_id)
        except Exception as e:
            print(f"Error fetching tweet metrics: {e}")
            likes, retweets, comments_fetched = 0, 0, 0

        # Calculate reward
        reward = calculate_reward(likes, retweets, len(comments_fetched))

        # Log the tweet
        timestamp = datetime.now().isoformat()
        log_tweet(timestamp, tweet, likes, retweets, len(comments_fetched), reward)

        # Update top examples if necessary
        update_top_examples(tweet, reward)

# Schedule the job every day at 09:00 AM
schedule.every().day.at("17:04").do(job)

print("Storyline bot is running and will post daily tweets at 5:00 PM.")

while True:
    schedule.run_pending()
    time.sleep(60)  # Wait one minute
