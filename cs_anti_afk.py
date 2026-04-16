#!/usr/bin/env python3
"""
CS2 Anti-AFK Tool - Simple and memory safe
"""

import logging
import random
import time
import subprocess
import signal
import sys
import psutil
import atexit

# Hardcoded Configuration
WINDOW_TITLE = "cs2"
INTERVAL_MIN = 5
INTERVAL_MAX = 10
ACTIONS = ["mouse_move", "key_forward"]
MOUSE_MOVE_RANGE = 5
LOG_FILE = None
VERBOSE = True
AUTO_LAUNCH = True

KEY_MAP = {
    "key_forward": "w",
    "key_back": "s",
    "key_left": "a",
    "key_right": "d",
}

class AntiAFKManager:
    """Manages anti-AFK with proper resource cleanup."""
    
    def __init__(self):
        self.running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self.cleanup)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logging.info(f"Received signal {signum}, shutting down...")
        self.running = False
        sys.exit(0)
    
    def cleanup(self):
        """Clean up resources on exit."""
        logging.info("Cleaning up resources...")
        self.running = False
    
    def is_cs2_running(self):
        """Check if CS2 process is running."""
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info.get('name', '').lower()
                    if 'cs2' in name or 'csgo' in name:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            logging.warning(f"Error checking CS2 process: {e}")
        return False
    
    def send_key(self, key, hold_secs=0.1):
        """Send a key press with optional hold duration."""
        try:
            subprocess.run(
                ["xdotool", "keydown", key],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False
            )
            time.sleep(hold_secs)
            subprocess.run(
                ["xdotool", "keyup", key],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False
            )
            logging.debug(f"Sent key: {key} (held {hold_secs}s)")
        except subprocess.TimeoutExpired:
            logging.warning(f"Timeout sending key: {key}")
        except Exception as e:
            logging.error(f"Failed to send key: {e}")
    
    def move_mouse(self, move_range):
        """Send mouse movement."""
        dx = random.randint(-move_range, move_range)
        dy = random.randint(-move_range, move_range)
        try:
            subprocess.run(
                ["xdotool", "mousemove_relative", str(dx), str(dy)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False
            )
            logging.debug(f"Moved mouse by ({dx}, {dy})")
        except subprocess.TimeoutExpired:
            logging.warning("Timeout moving mouse")
        except Exception as e:
            logging.error(f"Failed to move mouse: {e}")
    
    def perform_action(self, action):
        """Perform an anti-AFK action."""
        try:
            if action in KEY_MAP:
                self.send_key(KEY_MAP[action])
            elif action == "mouse_move":
                self.move_mouse(MOUSE_MOVE_RANGE)
        except Exception as e:
            logging.error(f"Error performing action {action}: {e}")
    
    def run_anti_afk(self):
        """Main anti-AFK loop."""
        logging.info("CS2 Anti-AFK started")
        logging.info(f"Interval: {INTERVAL_MIN}-{INTERVAL_MAX}s | Actions: {', '.join(ACTIONS)}")
        
        try:
            while self.running:
                if not self.is_cs2_running():
                    logging.info("CS2 process ended, stopping anti-AFK")
                    break
                
                try:
                    for action in ACTIONS:
                        if not self.running:
                            break
                        self.perform_action(action)
                    
                    if not self.running:
                        break
                    
                    sleep_time = random.uniform(INTERVAL_MIN, INTERVAL_MAX)
                    logging.info(f"Actions performed. Next in {sleep_time:.1f}s")
                    time.sleep(sleep_time)
                except KeyboardInterrupt:
                    logging.info("Interrupted by user")
                    break
                except Exception as e:
                    logging.error(f"Error in main loop: {e}")
                    time.sleep(1)
        finally:
            logging.info("Anti-AFK stopped")
    
    def wait_for_cs2(self):
        """Wait for CS2 to launch."""
        if not AUTO_LAUNCH:
            self.run_anti_afk()
            return
        
        logging.info("Waiting for CS2 to launch...")
        timeout = 3600
        start_time = time.time()
        
        while not self.is_cs2_running():
            if not self.running or (time.time() - start_time) > timeout:
                logging.info("Timeout waiting for CS2")
                return
            time.sleep(5)
        
        logging.info("CS2 detected! Starting anti-AFK...")
        time.sleep(2)
        self.run_anti_afk()

def setup_logging():
    """Setup logging."""
    handlers = [logging.StreamHandler()]
    if LOG_FILE:
        try:
            handlers.append(logging.FileHandler(LOG_FILE))
        except Exception as e:
            logging.warning(f"Could not create log file: {e}")
    
    level = logging.DEBUG if VERBOSE else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )

def main():
    """Main entry point."""
    try:
        setup_logging()
        logging.info("CS2 Anti-AFK Tool started")
        
        manager = AntiAFKManager()
        manager.wait_for_cs2()
    
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
