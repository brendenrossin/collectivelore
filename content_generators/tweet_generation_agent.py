# content_generators/tweet_generation_agent.py
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAI
from .story_phase_manager import StoryPhaseManager
from .prompt_loader import PromptLoader
from .story_summary import generate_story_summary

class TweetGenerationAgent:
    def __init__(self, openai_api_key, config_path='config/phase_prompts.json'):
        self.llm = OpenAI(api_key=openai_api_key)
        self.phase_manager = StoryPhaseManager()
        self.prompt_loader = PromptLoader(config_path)

    def generate_tweet(self, last_tweet=None, user_comment=None):
        phase = self.phase_manager.get_current_phase()

        if phase == "resolution":
            summary = generate_story_summary()
            prompt_text = (
                f"{self.prompt_loader.get_prompt(phase)}\n\n"
                f"Summary: {summary}"
            )
        elif phase == "exposition" and not last_tweet:
            prompt_text = self.prompt_loader.get_prompt(phase)
        else:
            if user_comment:
                # **Enhancement:** Include the phase prompt when user comments are present
                phase_prompt = self.prompt_loader.get_prompt(phase)
                prompt_text = (
                    f"{phase_prompt}\n\n"
                    "Continue the following story based on the provided context from the most liked comment. "
                    "Ensure continuity with previous tweets and integrate the new direction smoothly. "
                    "Maintain ethical storytelling, allowing for dramatic elements without promoting negativity or harm.\n\n"
                    f"Previous Tweet: \"{last_tweet}\"\n\n"
                    f"User Comment: \"{user_comment}\"\n\n"
                    "Generate the next tweet in the storyline."
                )
            else:
                # Autonomous continuation based on current phase
                prompt_text = self.prompt_loader.get_prompt(phase)

        # Define a simple prompt template
        prompt = PromptTemplate(
            input_variables=[],
            template=prompt_text
        )

        # Create the LLMChain
        chain = LLMChain(llm=self.llm, prompt=prompt)

        try:
            tweet = chain.run()
            return tweet.strip()
        except Exception as e:
            print(f"Error generating tweet: {e}")
            return "Oops! Something went wrong. Please try again later."
