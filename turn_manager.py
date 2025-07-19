from datetime import datetime, timedelta
import re

class TurnManager:
    def __init__(self, start_date='1955-05-04'):
        self.current_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.pacing = 'green'  # Options: 'green', 'yellow', 'red'
        self.turn_advanced = False  # Track if turn advanced this request

    def advance_time(self):
        if self.pacing == 'green':
            self.current_date += timedelta(days=2)
        elif self.pacing == 'yellow':
            self.current_date += timedelta(days=1)
        elif self.pacing == 'red':
            pass  # No time advance
        self.turn_advanced = True

    def get_date_str(self):
        return self.current_date.strftime('%Y-%m-%d')

    def update_from_ai(self, ai_response):
        # Detect embedded pacing switch from AI response
        match = re.search(r'\{switch pacing:\s*(green|yellow|red)\}', ai_response, re.IGNORECASE)
        if match:
            self.pacing = match.group(1).lower()

    def get_system_message(self):
        if self.turn_advanced:
            message = f"Turn started. Current date is {self.get_date_str()}. Pacing is {self.pacing.upper()}."
            if self.pacing == 'green':
                message += " You may override pacing by replying with {switch pacing: yellow} or {switch pacing: red} if the situation demands it."
            else:
                message += " Remember to return to {switch pacing: green} when the situation is resolved."
            return message
        else:
            return ""

    def get_pacing_instruction(self):
        # Provide reminder about pacing override options, always present for AI
        if self.pacing == 'green':
            return "You may override pacing by replying with {switch pacing: yellow} or {switch pacing: red} if necessary."
        else:
            return "Remember to return to {switch pacing: green} when the situation is resolved."

    def next_turn(self):
        self.advance_time()
        self.turn_advanced = True

    def should_advance_turn(self, user_input):
        # For now, always advance on each user message; customize as needed
        return True

    def handle_ai_response(self, ai_response):
        # Process pacing overrides from AI
        self.update_from_ai(ai_response)
        # Reset turn_advanced flag after AI processes this turn
        self.turn_advanced = False