# content_generators/prompt_loader.py

import json
import os

class PromptLoader:
    def __init__(self, config_path='config/phase_prompts.json'):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as file:
            try:
                self.prompts = json.load(file)
            except json.JSONDecodeError as e:
                raise ValueError(f"Error decoding JSON from {config_path}: {e}")

    def get_prompt(self, phase):
        return self.prompts.get(phase, "Continue the ongoing story. Keep it engaging and suitable for a tweet.")
