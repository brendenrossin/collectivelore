# content_generators/comment_analysis_agent.py

from langchain_openai import OpenAI

class CommentAnalysisAgent:
    def __init__(self, openai_api_key):
        self.llm = OpenAI(api_key=openai_api_key)

    def analyze_comment(self, comment):
        try:
            # Check ethical and moral positivity
            ethical_prompt = (
                f"Analyze the following comment and determine if it is ethically and morally positive for guiding a story. "
                f"Allow for dark elements such as characters being in danger or killed off, but avoid any hate speech or morally negative connotations. "
                f"Respond with 'Yes' if appropriate, 'No' otherwise.\n\nComment: \"{comment}\""
            )
            ethical_response = self.llm(prompt=ethical_prompt, max_tokens=3, temperature=0)
            is_ethical = ethical_response['choices'][0]['text'].strip().lower() == "yes"

            # Check relevance to story guidance
            relevance_prompt = (
                f"Determine if the following comment is intended to guide the storyline of a serialized Twitter story. "
                f"Respond with 'Yes' if it provides a direction or plot point for the story, 'No' otherwise.\n\nComment: \"{comment}\""
            )
            relevance_response = self.llm(prompt=relevance_prompt, max_tokens=3, temperature=0)
            is_relevant = relevance_response['choices'][0]['text'].strip().lower() == "yes"

            return is_ethical and is_relevant
        except Exception as e:
            print(f"Error analyzing comment: {e}")
            return False
