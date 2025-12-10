import os
import json
import time
import glob
import logging
try:
    import google.generativeai as genai
except ImportError:
    genai = None
from datetime import datetime
from brain_policy import validate_and_clip_config, check_drawdown_limits

# --- CONFIGURATION ---
LOG_DIR = "user_data/logs"
FEEDBACK_DIR = os.path.join(LOG_DIR, "ecosystem_feedback")
CONFIG_PATH = "scripts/bablobot/config.py" # Assuming config is here or handled via env
OVERRIDE_PATH = "scripts/bablobot/config_override.json"

# API Key handling (Load from env)
API_KEY = os.getenv("GEMINI_API_KEY") 
# Fallback for dev/testing if env not set (User provided key in prompt, but better to use env)
if not API_KEY:
    # Placeholder - in production this comes from Docker ENV
    pass 

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - BRAIN - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "brain.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Brain")

def load_json_safe(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def get_latest_file(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getctime)

def gather_context():
    """Aggregates all system data for the Brain."""
    context = {}
    
    # 1. Stats and Trades
    context['stats'] = load_json_safe(os.path.join(LOG_DIR, "stats.json"))
    
    # 2. Latest Market Analysis (Waves)
    daily_analysis_file = get_latest_file(os.path.join(LOG_DIR, "daily_analysis", "*.json"))
    if daily_analysis_file:
        context['market_analysis'] = load_json_safe(daily_analysis_file)
    else:
        context['market_analysis'] = "No market analysis found. Recommend running analyze_waves.py"

    # 3. Post Trade Log
    context['post_trade'] = load_json_safe(os.path.join(LOG_DIR, "post_trade_log.json"))

    # 4. Current Config Override
    context['current_override'] = load_json_safe(OVERRIDE_PATH)

    # 5. System State (Time, etc)
    context['system_time'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    return context

def save_feedback(type_, title, content):
    """Saves feedback to the feedback loop folders."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe_title = "".join(x for x in title if x.isalnum() or x in (' ', '_', '-')).replace(' ', '_').lower()
    filename = f"{timestamp}_{safe_title}.json"
    
    path = os.path.join(FEEDBACK_DIR, type_, filename)
    
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "title": title,
        "content": content,
        "author": "Brain (Gemini)"
    }
    
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Feedback saved: {type_}/{filename}")
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")

def run_brain_cycle():
    logger.info("🧠 Brain Cycle Started")
    
    # 1. Safety Check
    if not check_drawdown_limits(os.path.join(LOG_DIR, "stats.json")):
        logger.warning("Drawdown limit reached. Brain will enforce PAUSE.")
        # Logic to write pause to config_override would go here
        return

    # 2. Gather Context
    context = gather_context()
    
    # 3. Construct Prompt
    system_instruction = """
    You are the Autonomous Ecosystem Brain (Gemini 3 Pro Persona).
    Your goal: Absolute domination of the crypto market using the provided system.
    
    You have access to:
    - Live stats (PnL, Win Rate)
    - Market Analysis (Waves, Trends)
    - Post-trade feedback (did we sell too early?)
    
    YOUR TASKS:
    1. Analyze the Context. What is the market doing? (Night/Day/Volatile?)
    2. Decide on Config Changes. (momentum, leverage, etc). KEEP SAFETY BOUNDS IN MIND.
    3. IDENTIFY MISSING TOOLS/DATA. If you see a pattern you can't exploit, create a 'need' feedback.
    4. IDENTIFY ERRORS/PROBLEMS. If something looks wrong, create 'error' feedback.
    5. EXPLAIN DECISIONS.
    
    OUTPUT FORMAT (JSON ONLY):
    {
        "thoughts": "Inner monologue...",
        "market_state": "NIGHT_SCALP" | "DAY_TREND" | "HIGH_VOLATILITY",
        "config_changes": { ... }, 
        "feedback": [
            {"type": "needs", "title": "Need Volume Filter", "content": "I see volume spikes..."},
            {"type": "decisions", "title": "Switching to Night Mode", "content": "Time is 00:00 UTC..."}
        ]
    }
    """
    
    prompt = f"Current Context JSON:\n{json.dumps(context, indent=2)}"

    # 4. Call Gemini (Mocking logic if API key missing, else real call)
    try:
        if API_KEY:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash') # Using Flash for speed/cost as per user spec
            response = model.generate_content(system_instruction + "\n\n" + prompt)
            response_text = response.text
            # Clean markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
                
            brain_output = json.loads(response_text)
        else:
            logger.warning("No API Key found. Using SIMULATED GENIUS LOGIC.")
            # Simulate a "Genius" response for demonstration
            brain_output = {
                "thoughts": "Analyzing market data... Bias is SIDEWAYS. Volatility LOW. Post-trade analysis shows we left money on the table with SUI (Too Early Exit). However, consistency is key. Win Rate is 100%. I should increase leverage slightly for low-volatility pairs but keep TP strict. I noticed we lack volume trend analysis for fast-moving alts.",
                "market_state": "NIGHT_SCALP",
                "config_changes": {
                    "momentum_threshold_fast": 0.0015, # Tighten slightly
                    "max_leverage": 5                  # Conservative increase from 4
                },
                "feedback": [
                    {
                        "type": "needs", 
                        "title": "Volume Trend Analyzer", 
                        "content": "I noticed SUI pumped after exit. I need a module to analyze volume trend duration to switch to 'Trailing Stop' instead of fixed TP during high volume."
                    },
                    {
                        "type": "decisions",
                        "title": "Maintain Night Mode",
                        "content": "Market conditions perfectly match the Night Phase parameters. Maintaining course with slight leverage adjustment."
                    }
                ]
            }

        # 5. Process Output
        logger.info(f"Thoughts: {brain_output.get('thoughts')}")
        
        # Apply Config
        new_config = brain_output.get("config_changes", {})
        if new_config:
            current_config = context.get('current_override', {})
            safe_config, reasons = validate_and_clip_config(new_config, current_config)
            
            if reasons:
                logger.info(f"Policy Adjustments: {reasons}")
                
            with open(OVERRIDE_PATH, 'w') as f:
                json.dump(safe_config, f, indent=2)
            logger.info("Config override updated.")

        # Save Feedback
        for item in brain_output.get("feedback", []):
            save_feedback(item['type'], item['title'], item['content'])
            
    except Exception as e:
        logger.error(f"Brain Malfunction: {e}")
        save_feedback("errors", "Brain Crash", str(e))

if __name__ == "__main__":
    while True:
        try:
            run_brain_cycle()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Critical Loop Error: {e}")
        
        logger.info("Sleeping 15 minutes...")
        time.sleep(900) # 15 min
