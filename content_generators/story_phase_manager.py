# content_generators/story_phase_manager.py

from datetime import datetime
import calendar

class StoryPhaseManager:
    def __init__(self):
        # Define the proportion of the month each phase should occupy
        self.phase_percentages = {
            "exposition": 0.2,      # 20% of the month
            "rising_action": 0.6,   # 60% of the month
            "climax": 0.13,         # 13% of the month
            "falling_action": 0.07, # 7% of the month
            "resolution": 0.0       # Last day(s)
        }

    def get_current_phase(self):
        today = datetime.now()
        day = today.day
        month = today.month
        year = today.year
        total_days = calendar.monthrange(year, month)[1]

        # Calculate day thresholds based on percentages
        exposition_end = int(total_days * self.phase_percentages["exposition"])
        rising_action_end = exposition_end + int(total_days * self.phase_percentages["rising_action"])
        climax_end = rising_action_end + int(total_days * self.phase_percentages["climax"])
        falling_action_end = climax_end + int(total_days * self.phase_percentages["falling_action"])

        if day <= exposition_end:
            return "exposition"
        elif day <= rising_action_end:
            return "rising_action"
        elif day <= climax_end:
            return "climax"
        elif day <= falling_action_end:
            return "falling_action"
        else:
            return "resolution"
