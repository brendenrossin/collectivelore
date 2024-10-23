# Interactive Storyline Bot

This project is an interactive storyline bot that generates and posts tweets based on user engagement and predefined story phases. The bot uses OpenAI's API to generate tweets and analyze comments, and it logs metrics and top examples for further analysis.

## Project Structure
.env .gitignore bluesky_check.py bluesky_main.py config/ phase_prompts.json content_generators/ init.py pycache/ bluesky_comment_analysis_agent.py bluesky_generation_agent.py comment_analysis_agent.py prompt_loader.py story_phase_manager.py story_summary.py tweet_generation_agent.py logs/ error.log top_examples.txt tweet_logs.csv main.py requirements.txt


### Key Files and Directories

- `bluesky_main.py`: Main script to run the bot.
- `bluesky_check.py`: Similar to bluesky_main.py without posting to verify functionality.
- `content_generators/`: Directory containing modules for tweet generation, comment analysis, and story management.
- `logs/`: Directory for storing logs and metrics.
- `config/phase_prompts.json`: Configuration file for story phase prompts.
- `requirements.txt`: List of dependencies.

## Setup

1. **Clone the repository:**

    ```sh
    git clone https://github.com/brendenrossin/collectivelore.git
    cd collectivelore
    ```

2. **Create and activate a virtual environment:**

    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. **Install dependencies:**

    ```sh
    pip install -r requirements.txt
    ```

4. **Set up environment variables:**

    Create a `.env` file in the root directory and add your OpenAI API key:

    ```
    OPENAI_API_KEY=your_openai_api_key
    ```

## Scheduling the Bot
The bot can be scheduled to run daily at a specific time. Uncomment and adjust the scheduling lines in bluesky_main.py:

##### Schedule the job every day at 09:00 AM
```schedule.every().day.at("09:00").do(job)```

## Logging
Logs and metrics are stored in the logs/ directory
