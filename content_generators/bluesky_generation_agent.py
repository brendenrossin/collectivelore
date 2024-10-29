# content_generators/tweet_generation_agent.py

from atproto import Client
from atproto.exceptions import AtProtocolError
from datetime import datetime, timezone
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAI
from langchain_core.runnables import RunnableSequence, RunnableMap
from langchain_core.output_parsers import StrOutputParser
from .story_phase_manager import StoryPhaseManager
from .prompt_loader import PromptLoader
from .story_summary import generate_story_summary
import os
import re
import logging

class TweetGenerationAgent:
    def __init__(self, openai_api_key, config_path='config/phase_prompts.json'):
        # Initialize the OpenAI LLM
        self.llm = OpenAI(api_key=openai_api_key, max_tokens=60)
        
        # Initialize other components
        self.phase_manager = StoryPhaseManager()
        self.prompt_loader = PromptLoader(config_path)
        self.client = Client()
        
        # Load Bluesky credentials from environment variables
        self.handle = os.getenv("BLUESKY_HANDLE")
        self.password = os.getenv("BLUESKY_PASSWORD")
        self.base_url = "https://bsky.app"  # Replace with actual Bluesky base URL if different

        try:
            # Authenticate with Bluesky
            self.client.login(self.handle, self.password)
            print("Successfully authenticated with Bluesky.")
        except AtProtocolError as e:
            logging.error(f"AT Protocol Error during authentication: {e}")
            print(f"AT Protocol Error during authentication: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during authentication: {e}")
            print(f"Unexpected error during authentication: {e}")

    def remove_incomplete_sentence(self, text):
        """
        Removes incomplete sentence at the end of the text.
        Tries to stop the text at the last complete sentence.
        """
        # Use regex to find all sentences ending with a period, exclamation mark, or question mark
        sentences = re.findall(r'[^.!?]*[.!?]', text)
        
        # Join the sentences together until the total length is within the limit
        output = ''
        for sentence in sentences:
            if len(output) + len(sentence) <= 300:  # Respect character limit
                output += sentence
            else:
                break

        # If no complete sentence is found, return the original text (safeguard)
        return output.strip() if output else text.strip()

    def generate_tweet(self, last_tweet=None, user_comment=None):
        # print('generate tweet with last tweet:', last_tweet, 'and user comment:', user_comment)
        phase = self.phase_manager.get_current_phase()

        # If length of the last tweet is equal to zero, set temp phase to exposition
        if not last_tweet or len(last_tweet) == 0:
            # print('generate tweet last tweet empty')
            temp_phase = "exposition"
            prompt_text = self.prompt_loader.get_prompt(temp_phase)
        elif phase == "resolution":
            # print('generate tweet resolution')
            summary = generate_story_summary()
            prompt_text = (
                f"{self.prompt_loader.get_prompt(phase)}\n\n"
                f"Summary: {summary}"
            )
        elif phase == "exposition" and not last_tweet:
            # print('generate tweet exposition and not last tweet')
            prompt_text = self.prompt_loader.get_prompt(phase)
        else:
            # print('generate tweet else')
            if (last_tweet or len(last_tweet) > 0) and not user_comment:
                # print('generate tweet last tweet and not user comment')
                # **Enhancement:** Include the phase prompt when previous posts are present
                phase_prompt = self.prompt_loader.get_prompt(phase)
                prompt_text = (
                    f"{phase_prompt}\n\n"
                    "Continue the following story based on the provided context from the previous post. "
                    f"Previous Posts: \"{last_tweet}\"\n\n"
                    "Write in the style of a top novelist within the genre of this story, ensuring the language is fluid, engaging, and dynamically varied in sentence structure. "
                    "**Actively avoid similar sentence opener styles from the previous posts and ensure that no two consecutive sentences follow the same structure.** "
                    "Use a mix of sentence types—varying lengths, opening styles, and narrative techniques—to create a natural flow and keep the reader engaged. "
                    "Incorporate imaginative or unconventional ideas to enhance the storyline while ensuring continuity with previous posts and smoothly integrating the new direction. "
                    "Focus on ethical storytelling, maintaining dramatic elements without promoting negativity or harm. "
                    "Create engaging character development, build tension or excitement, and use dynamic language to move the plot forward.\n\n**"
                    "Generate the next post in the storyline."
                )
            elif (last_tweet or len(last_tweet) > 0) and user_comment:
                # print('generate tweet last tweet and user comment')
                # **Enhancement:** Include the phase prompt when user comments are present
                phase_prompt = self.prompt_loader.get_prompt(phase)
                prompt_text = (
                    f"{phase_prompt}\n\n"
                    "Continue the following story based on the provided context from the most liked comment. "
                    f"Previous Posts: \"{last_tweet}\"\n\n"
                    f"User Comment: \"{user_comment}\"\n\n"
                    "Write in the style of a top novelist within the genre of this story, ensuring the language is fluid, engaging, and dynamically varied in sentence structure. "
                    "**Actively avoid similar sentence opener styles from the previous posts and ensure that no two consecutive sentences follow the same structure.** "
                    "Use a mix of sentence types—varying lengths, opening styles, and narrative techniques—to create a natural flow and keep the reader engaged. "
                    "Incorporate imaginative or unconventional ideas to enhance the storyline while ensuring continuity with previous posts and smoothly integrating the new direction. "
                    "Focus on ethical storytelling, maintaining dramatic elements without promoting negativity or harm. "
                    "Create engaging character development, build tension or excitement, and use dynamic language to move the plot forward.\n\n**"
                    "Generate the next post in the storyline."
                )
            else:
                # Autonomous continuation based on current phase
                prompt_text = self.prompt_loader.get_prompt(phase)

        prompt_text += "**Ensure the response does not exceed 300 characters and ends at a natural stopping point or a complete sentence!**"
        print(f'prompt text: {prompt_text}')

        # Define the prompt template
        prompt = PromptTemplate(
            input_variables=[],  # No variables expected
            template=prompt_text
        )

        # Initialize the LLMChain
        chain = prompt | self.llm | StrOutputParser()

        try:
            # Run the chain to generate the tweet
            tweet = chain.invoke(input={})
            logging.debug(f"Generated Tweet Before Post-Processing: {tweet}")
            # print((f"Generated Tweet Before Post-Processing: {tweet}"))

            # Post-processing: Remove incomplete sentence if needed
            tweet = self.remove_incomplete_sentence(tweet)
            logging.debug(f"Generated Tweet After Post-Processing: {tweet}")
            # print(f"Generated Tweet After Post-Processing: {tweet}")

            return tweet.strip()
        except Exception as e:
            logging.error(f"Error generating post: {e}")
            print(f"Error generating post: {e}")
            return "Oops! Something went wrong. Please try again later."

    def post_tweet(self, tweet):
        try:
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            # Define the record for a post
            post = {
                "$type": "app.bsky.feed.post",
                "text": tweet,  # The content of your tweet
                "createdAt": now  # The timestamp of the post
            }

            # Create the record in the 'app.bsky.feed.post' collection
            response = self.client.send_post(
                tweet
            )

            # Extract the post ID from the response
            # The exact key might vary based on the SDK version; adjust accordingly
            post_id = response.cid
            post_uri = response.uri

            # print(f"Posted update with ID {post_id}")
            return post_id, post_uri

        except AtProtocolError as e:
            logging.error(f"AT Protocol Error posting update: {e}")
            print(f"AT Protocol Error posting update: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error posting update: {e}")
            print(f"Unexpected error posting update: {e}")
            return None

    def fetch_last_post(self, post_uri):
        try:
            posts = self.client.get_posts(uris=[post_uri])  # Removed 'limit' parameter
            if posts:
                last_post = posts[0]  # Assuming the first post is the latest
                return last_post['id'], last_post['text']
            else:
                return None, None
        except AtProtocolError as e:
            logging.error(f"AT Protocol Error fetching last post: {e}")
            print(f"AT Protocol Error fetching last post: {e}")
            return None, None
        except Exception as e:
            logging.error(f"Unexpected error fetching last post: {e}")
            print(f"Unexpected error fetching last post: {e}")
            return None, None
        
    def fetch_recent_posts(self, limit=31):
        """
        Fetch the most recent posts from the author's feed (your own posts).
        Returns a list of recent posts.
        """
        try:
            # Fetch the author's feed with the specified limit
            response = self.client.get_author_feed(actor='collectivelore.bsky.social', limit=limit)

            try:
                posts = response['feed']
                # print('posts:', posts)
                # Extract the text content of each post
                recent_posts = [post.post.record.text for post in posts if hasattr(post.post.record, 'text') and post.reply is None]
                post_uris = [post.post.uri for post in posts if hasattr(post.post, 'uri') and hasattr(post.post.record, 'text') and post.reply is None]
                # print('recent posts', recent_posts)
                # print('post uris', post_uris)
            except Exception as e:
                print(f"Error fetching recent posts last try: {e}")

            if recent_posts:
                # Find the index of the last occurrence of a string that starts with "Welcome to a new month"
                last_index = next((i for i in reversed(range(len(recent_posts))) if recent_posts[i].startswith("Welcome to a new month")), -1)

                # Use everything in recent_posts after that index
                if last_index != -1:
                    recent_posts = recent_posts[:last_index]
                    relevant_post_uris = post_uris[:last_index]
                
                # Reverse the order of recent_posts to get the in order of when sent
                recent_posts.reverse()
                most_recent_post_uri = relevant_post_uris[0]

                return recent_posts, most_recent_post_uri
            else:
                print("No posts found.")
                return []
        except Exception as e:
            print(f"Error fetching recent posts: {e}")
            return []

