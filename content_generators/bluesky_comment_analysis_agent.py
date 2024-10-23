# content_generators/comment_analysis_agent.py

from atproto import Client
from atproto.exceptions import AtProtocolError
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAI
from langchain_core.runnables import RunnableSequence, RunnableMap
import os
import logging

class CommentAnalysisAgent:
    def __init__(self, openai_api_key):
        self.llm = OpenAI(api_key=openai_api_key)
        self.client = Client()
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

    def analyze_comment(self, comment_text):
        try:
            # Check ethical and moral positivity
            ethical_prompt = (
            f"Analyze the following comment and determine if it is ethically and morally suitable for guiding a story. "
            f"Allow for creative freedom, including romance and dark story elements such as danger or characters being killed off, "
            f"but ensure the content avoids hate speech, explicit material, or anything that would be considered R-rated. "
            f"Only respond with 'No' if the comment contains hate speech, explicit content, or promotes violence. "
            f"Otherwise, respond with 'Yes' to allow the comment.\n\nComment: \"{comment_text}\""
            )

            ethical_template = PromptTemplate(
                input_variables=[],
                template=ethical_prompt
            )

            # Initialize the LLMChain
            chain = LLMChain(llm=self.llm, prompt=ethical_template, verbose=True)
            
            # Run the chain to generate the tweet
            ethical_response = chain.invoke(input={})
            logging.debug(f"Generated to see if response is ethical: {ethical_response}")
            if isinstance(ethical_response, dict) and 'text' in ethical_response:
                is_ethical = ethical_response['text'].strip().lower() == 'yes'

            # Check relevance to story guidance
            relevance_prompt = (
            f"Determine if the following comment is intended to guide the storyline of a serialized Bluesky story. "
            f"Respond with 'Yes' if the comment introduces a new direction, new characters, or new plot developments, including imaginative or unconventional ideas like fantasy, scifi, romance or other book genre elements. "
            f"Respond with 'No' if the comment is a general reaction (e.g., praise, feedback) or does not contribute to advancing the storyline.\n\n"
            f"Comment: \"{comment_text}\""
            )
            relevance_template = PromptTemplate(
                input_variables=[],
                template=relevance_prompt
            )

            # Initialize the LLMChain
            chain = LLMChain(llm=self.llm, prompt=relevance_template, verbose=True)

            
            # Run the chain to generate the tweet
            relevance_response = chain.invoke(input={})
            logging.debug(f"Generated to see if response is relevant: {relevance_response}")
            if isinstance(relevance_response, dict) and 'text' in relevance_response:
                is_relevant = relevance_response['text'].strip().lower() == 'yes'

            return is_ethical and is_relevant
        
        except Exception as e:
            logging.error(f"Error analyzing comment: {e}")
            print(f"Error analyzing comment: {e}")
            return False

    def fetch_comments(self, post_uri):
        """
        Fetch comments on a post using the post_uri.
        """
        try:
            # Fetch the thread of the post using the post_uri
            response = self.client.get_post_thread(uri=post_uri)

            # Extract comments and their metrics from the response
            comments = []
            if response:
                thread = response['thread']
                if hasattr(thread, 'replies'):
                    for reply in thread.replies:
                        if hasattr(reply.post.record, 'text'):
                            comment_text = reply.post.record.text
                            like_count = getattr(reply.post, 'like_count', 0)
                            repost_count = getattr(reply.post, 'repost_count', 0)
                            comments.append({
                                'text': comment_text,
                                'likes': like_count,
                                'retweets': repost_count
                            })
                                # # Check for nested replies
                                # if hasattr(reply, 'replies'):
                                #     print('replies in reply')
                                #     for nested_reply in reply.replies:
                                #         if hasattr(nested_reply.post.record, 'text'):
                                #             print('record in nested reply')
                                #             nested_comment_text = nested_reply.post.record.text
                                #             print('nested_comment_text:', nested_comment_text)
                                #             nested_like_count = getattr(nested_reply.post, 'like_count', 0)
                                #             nested_repost_count = getattr(nested_reply.post, 'repost_count', 0)
                                #             comments.append({
                                #                 'text': nested_comment_text,
                                #                 'likes': nested_like_count,
                                #                 'retweets': nested_repost_count
                                #             })

            return comments
        except AtProtocolError as e:
            logging.error(f"AT Protocol Error fetching comments: {e}")
            print(f"AT Protocol Error fetching comments: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error fetching comments: {e}")
            print(f"Unexpected error fetching comments: {e}")
            return []
