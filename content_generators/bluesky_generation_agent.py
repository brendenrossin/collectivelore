# content_generators/tweet_generation_agent.py

from atproto import Client
from atproto.exceptions import AtProtocolError
from datetime import datetime, timezone
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableSequence, RunnableMap
from langchain_core.output_parsers import StrOutputParser
from .story_phase_manager import StoryPhaseManager
from .prompt_loader import PromptLoader
from .story_summary import generate_story_summary
import os
import re
import logging

class TweetGenerationAgent:
    def __init__(self, openai_api_key, anthropic_api_key, config_path='config/phase_prompts.json'):
        # Initialize the OpenAI LLM
        self.llm = ChatOpenAI(api_key=openai_api_key,
                          model_name="gpt-4",
                          max_tokens=60,
                          temperature=0.9,
                          frequency_penalty=0.5,
                          presence_penalty=0.5)

        self.claude = ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            api_key=anthropic_api_key,
            max_tokens=60,
            temperature=0.9
        )

        self.reviewer = ChatOpenAI(
            model="gpt-4",
            api_key=openai_api_key,
            max_tokens=60,
            temperature=0.2
        )
        
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
            logging.info("Successfully authenticated with Bluesky.")
        except AtProtocolError as e:
            logging.error(f"AT Protocol Error during authentication: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during authentication: {e}")

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
    
    def evaluate_output(self, output, user_feedback):
        issues = []
        if user_feedback:
            if not user_comment_included(output, user_feedback):
                issues.append("- The draft does not adequately incorporate the user comment.")
        # Common checks for all scenarios
        if not advances_plot(output):
            issues.append("- The draft does not effectively advance the plot.")
        if not maintains_tone(output):
            issues.append("- The draft does not maintain the consistent tone and style.")
        if repeats_content(output):
            issues.append("- The draft repeats content unnecessarily.")
        return "\n".join(issues) if issues else None


    def generate_tweet(self, last_tweet=None, user_comment=None):
        phase = self.phase_manager.get_current_phase()

        # If length of the last tweet is equal to zero, set temp phase to exposition
        if not last_tweet or len(last_tweet) == 0:
            temp_phase = "exposition"
            prompt_text = self.prompt_loader.get_prompt(temp_phase)
        elif phase == "exposition" and not last_tweet:
            prompt_text = self.prompt_loader.get_prompt(phase)
        else:
            if (last_tweet or len(last_tweet) > 0):
                context = f"Previous Posts: \"{last_tweet}\"\n\n"
                if user_comment:
                    context += f"User Comment: \"{user_comment}\"\n\n"
                    emphasis_instructions = (
                                "1. **Focus** on the user comment, making it the central element of the next part of the story.\n"
                                "2. **Integrate** elements from previous posts to maintain continuity.\n"
                                )
                else:
                    emphasis_instructions = (
                                "1. **Advance** the story by introducing new developments or escalating tension based on the previous posts.\n"
                                "2. **Build upon the most recent section of the story, ensuring a cohesive continuation.**\n"
                                )
            else:
                context = ""
            if (last_tweet or len(last_tweet) > 0) and not user_comment:
                # **Enhancement:** Include the phase prompt when previous posts are present
                phase_prompt = self.prompt_loader.get_prompt(phase)
                prompt_text = (
                    "Continue the following story based on the context below. "
                    f"{context}"
                    "Write the next part of the story in the style of a top short story author in this genre. "
                    f"**{phase_prompt}**\n\n"
                    "Instructions:\n"
                    f"{emphasis_instructions}"
                    "3. **Maintain** continuity with previous posts, incorporating necessary elements to keep the story cohesive.\n"
                    "4. **Advance** the plot meaningfully, introducing new developments.\n"
                    "5. **Do not** repeat any sentences or phrases verbatim from previous posts unless they serve a specific narrative purpose, such as emphasizing an important detail.\n"
                    "6. **Add** dialogue where appropriate, as long as it advances the plot.\n"
                    "7. **Keep** the tone, style, and pacing consistent with the story so far.\n"
                    "8. **Do not** include the instructions or any meta-commentary in your output.\n"
                    "9. **Provide only** the next part of the story.\n\n"
                    "Now, generate the next post in the storyline."
                )
            elif (last_tweet or len(last_tweet) > 0) and user_comment:
                # **Enhancement:** Include the phase prompt when user comments are present
                phase_prompt = self.prompt_loader.get_prompt(phase)
                prompt_text = (
                    "Continue the following story based on the context below. "
                    f"{context}"
                    "Write the next part of the story in the style of a top short story author in this genre. "
                    f"**{phase_prompt}**\n\n"
                    "Instructions:\n"
                    f"{emphasis_instructions}"
                    "3. **Maintain** continuity with previous posts, incorporating necessary elements to keep the story cohesive.\n"
                    "4. **Advance** the plot meaningfully, introducing new developments.\n"
                    "5. **Keep** the tone, style, and pacing consistent with the story so far.\n"
                    "6. **Do not** include the instructions or any meta-commentary in your output.\n"
                    "7. **Provide only** the next part of the story.\n\n"
                    "Now, generate the next post in the storyline."
                )
            else:
                # Autonomous continuation based on current phase
                prompt_text = self.prompt_loader.get_prompt(phase)

        prompt_text += "**Ensure the response does not exceed 300 characters and ends at a natural stopping point or a complete sentence!**"
        logging.info(f'prompt text: {prompt_text}')

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

            # Post-processing: Remove incomplete sentence if needed
            tweet = self.remove_incomplete_sentence(tweet)
            logging.debug(f"Generated Tweet After Post-Processing: {tweet}")

            return tweet.strip()
        except Exception as e:
            logging.error(f"Error generating post: {e}")
            return "Oops! Something went wrong. Please try again later."
        
    async def generate_competing_tweets(self, last_tweet=None, user_comment=None):
        phase = self.phase_manager.get_current_phase()

        # If length of the last tweet is equal to zero, set temp phase to exposition
        if not last_tweet or len(last_tweet) == 0:
            temp_phase = "exposition"
            prompt_text = self.prompt_loader.get_prompt(temp_phase)
        elif phase == "exposition" and not last_tweet:
            prompt_text = self.prompt_loader.get_prompt(phase)
        else:
            if (last_tweet or len(last_tweet) > 0):
                context = f"Previous Posts: \"{last_tweet}\"\n\n"
                if user_comment:
                    context += f"User Comment: \"{user_comment}\"\n\n"
                    emphasis_instructions = (
                                "1. **Focus** on the user comment, making it the central element of the next part of the story.\n"
                                "2. **Integrate** elements from previous posts to maintain continuity.\n"
                                )
                else:
                    emphasis_instructions = (
                                "1. **Advance** the story by introducing new developments or escalating tension based on the previous posts.\n"
                                "2. **Build upon the most recent section of the story, ensuring a cohesive continuation.**\n"
                                )
            else:
                context = ""
            if (last_tweet or len(last_tweet) > 0) and not user_comment:
                # **Enhancement:** Include the phase prompt when previous posts are present
                phase_prompt = self.prompt_loader.get_prompt(phase)
                prompt_text = (
                    "Continue the following story based on the context below. "
                    f"{context}"
                    "Write the next part of the story in the style of a top short story author in this genre. "
                    f"**{phase_prompt}**\n\n"
                    "Instructions:\n"
                    f"{emphasis_instructions}"
                    "3. **Maintain** continuity with previous posts, incorporating necessary elements to keep the story cohesive.\n"
                    "4. **Advance** the plot meaningfully, introducing new developments.\n"
                    "5. **Do not** repeat any sentences or phrases verbatim from previous posts unless they serve a specific narrative purpose, such as emphasizing an important detail.\n"
                    "6. **Add** dialogue where appropriate, as long as it advances the plot.\n"
                    "7. **Keep** the tone, style, and pacing consistent with the story so far.\n"
                    "8. **Do not** include the instructions or any meta-commentary in your output.\n"
                    "9. **Provide only** the next part of the story.\n\n"
                    "Now, generate the next post in the storyline."
                )
            elif (last_tweet or len(last_tweet) > 0) and user_comment:
                # **Enhancement:** Include the phase prompt when user comments are present
                phase_prompt = self.prompt_loader.get_prompt(phase)
                prompt_text = (
                    "Continue the following story based on the context below. "
                    f"{context}"
                    "Write the next part of the story in the style of a top short story author in this genre. "
                    f"**{phase_prompt}**\n\n"
                    "Instructions:\n"
                    f"{emphasis_instructions}"
                    "3. **Maintain** continuity with previous posts, incorporating necessary elements to keep the story cohesive.\n"
                    "4. **Advance** the plot meaningfully, introducing new developments.\n"
                    "5. **Keep** the tone, style, and pacing consistent with the story so far.\n"
                    "6. **Do not** include the instructions or any meta-commentary in your output.\n"
                    "7. **Provide only** the next part of the story.\n\n"
                    "Now, generate the next post in the storyline."
                    
                    # "Ensure language is fluid, engaging, and varied in sentence structure, avoiding repetitive openings or phrasing. "
                    # "Each post should clearly advance the plot to add new details, escalate tension, or introduce fresh elements to keep the story dynamic and avoid stalling. "
                    # "**Do not repeat any sentences or phrases verbatim from previous posts** unless they serve a specific narrative purpose, such as emphasizing an important detail. "
                    # "Keep the pacing brisk to fit a short story format of around 9,000 characters total, making each post concise yet impactful. "
                    # "Blend imaginative ideas smoothly with prior events for continuity. "
                    # "Follow the prompt below as the primary guide for the story’s direction, tone, and pacing. This should strongly influence each scene and ensure progression toward the story's goals:\n\n"
                    # "Write in the style of a top short story author within the genre of this story, ensuring the language is fluid, engaging, and dynamically varied in sentence structure. "
                    # "**Do not repeat any sentences or phrases verbatim from previous posts** unless they serve a specific narrative purpose, such as emphasizing an important detail. "
                    # "Ensure the story advances in a way that builds upon past events while introducing new elements or developments. "
                    # "Use varied sentence structures and openers to maintain freshness and keep the reader engaged. "
                    # "Remember that this is a short story with a total length of around 9,000 characters by the end; space the story elements accordingly, making each post concise yet impactful. "
                    # "Move the plot forward decisively, revealing new details, advancing the storyline, or escalating tension to prevent the narrative from stalling. "
                    # "Keep the pacing brisk to fit the daily format while allowing room for character depth and story-building elements. "
                    # "Incorporate imaginative or unconventional ideas to enhance the storyline while ensuring continuity with previous posts and smoothly integrating the new direction. "
                    # "Create engaging character development, build tension or excitement, and use dynamic language to move the plot forward.\n\n**"
                    # "Generate the next post in the storyline."
                )
            else:
                # Autonomous continuation based on current phase
                prompt_text = self.prompt_loader.get_prompt(phase)

        prompt_text += "**Ensure the response does not exceed 300 characters and ends at a natural stopping point or a complete sentence!**"
        logging.info(f'prompt text: {prompt_text}')

        # Define the prompt template
        prompt = PromptTemplate(
            input_variables=[],  # No variables expected
            template=prompt_text
        )

        # Initialize the LLMChain
        chatgpt_chain = prompt | self.llm | StrOutputParser()
        claude_chain = prompt | self.claude | StrOutputParser()

        try:
            # Run the chains to generate tweets asynchronously
            try:
                chatgpt_tweet = await chatgpt_chain.ainvoke(input={})  # Fixed await syntax
                logging.debug(f"Generated chatgpt tweet: {chatgpt_tweet}")
            except Exception as e:
                logging.error(f"Error generating chatgpt tweet: {e}")

            try:
                claude_tweet = await claude_chain.ainvoke(input={})
                logging.debug(f"Generated claude tweet: {claude_tweet}")
            except Exception as e:
                logging.error(f"Error generating claude tweet: {e}")

            # Only proceed if at least one tweet was generated
            if not chatgpt_tweet and not claude_tweet:
                raise Exception("Both tweet generations failed")

            # Use the non-empty tweet if one failed
            if not chatgpt_tweet:
                return claude_tweet.strip()
            if not claude_tweet:
                return chatgpt_tweet.strip()

            # Post-processing
            chatgpt_tweet = self.remove_incomplete_sentence(chatgpt_tweet)
            claude_tweet = self.remove_incomplete_sentence(claude_tweet)

            # print("\n=== Generated Competing Tweets ===")
            # print(f"ChatGPT: {chatgpt_tweet}")
            # print(f"Claude: {claude_tweet}")
            logging.info(f"Generated tweets - ChatGPT: {chatgpt_tweet}, Claude: {claude_tweet}")

            # Review and select best tweet
            review_prompt = f"""
            You are a creative storyteller and social media manager,
            evaluating story continuations for an ongoing narrative.

            Story Context:
            {context}

            Current Story Phase: {phase}
            Phase Guidelines: {phase_prompt}

            Compare these two generated story continuations and select the better one based on:
            1. Coherence with previous story elements
            2. Alignment with current story phase
            3. Writing quality and likelihood of engagement
            4. Character and plot development
            
            Tweet 1: {chatgpt_tweet}
            Tweet 2: {claude_tweet}
            
            Provide your choice (1 or 2) and a brief explanation.
            """
            
            review_result = await self.reviewer.ainvoke([{"role": "user", "content": review_prompt}])
            # print("\n=== Reviewer's Analysis ===")
            # print(review_result.content)
            logging.info(f"Reviewer's analysis: {review_result.content}")

            return chatgpt_tweet.strip() if "1" in review_result.content else claude_tweet.strip()

        except Exception as e:
            logging.error(f"Error generating competing posts: {e}")
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

            return post_id, post_uri

        except AtProtocolError as e:
            logging.error(f"AT Protocol Error posting update: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error posting update: {e}")
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
            return None, None
        except Exception as e:
            logging.error(f"Unexpected error fetching last post: {e}")
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
                # Extract the text content of each post
                recent_posts = [post.post.record.text for post in posts if hasattr(post.post.record, 'text') and post.reply is None]
                post_uris = [post.post.uri for post in posts if hasattr(post.post, 'uri') and hasattr(post.post.record, 'text') and post.reply is None]
            except Exception as e:
                logging.error(f"Error fetching recent posts last try: {e}")

            if recent_posts:
                # Find the index of the first occurrence of a string that starts with "Welcome to a new month"
                first_index = next((i for i in range(len(recent_posts)) if recent_posts[i].startswith("Welcome to a new month")), -1)

                # Use everything in recent_posts after that index
                if first_index != 0:
                    recent_posts = recent_posts[:first_index]
                    relevant_post_uris = post_uris[:first_index]
                
                # Reverse the order of recent_posts to get the in order of when sent
                recent_posts.reverse()
                most_recent_post_uri = relevant_post_uris[0]

                return recent_posts, most_recent_post_uri
            else:
                logging.error("No posts found.")
                return []
        except Exception as e:
            logging.error(f"Error fetching recent posts: {e}")
            return []

