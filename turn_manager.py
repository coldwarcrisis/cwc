from datetime import datetime, timedelta
import re

class TurnManager:
    def __init__(self, start_date='1955-05-04'):
        self.current_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.pacing = 'green'  # Options: 'green', 'yellow', 'red'

    def advance_time(self):
        if self.pacing == 'green':
            self.current_date += timedelta(days=2)
        elif self.pacing == 'yellow':
            self.current_date += timedelta(days=1)
        elif self.pacing == 'red':
            pass  # No time advance

    def get_date_str(self):
        return self.current_date.strftime('%Y-%m-%d')

    def update_from_ai(self, ai_response):
        # Detect embedded pacing switch from AI response
        match = re.search(r'\{switch pacing:\s*(green|yellow|red)\}', ai_response, re.IGNORECASE)
        if match:
            self.pacing = match.group(1).lower()

    def system_message(self):
        message = f"{{Turn started. Current date is {self.get_date_str()}. Pacing is {self.pacing.upper()}."
        if self.pacing == 'green':
            message += " You may override pacing by replying with {switch pacing: yellow} or {switch pacing: red} if the situation demands it."
        else:
            message += " Remember to return to {switch pacing: green} when the situation is resolved."
        message += "}"
        return message

    def next_turn_message(self, user_input):
        self.advance_time()
        return user_input.strip() + "\n\n" + self.system_message()
    def should_advance_turn(self, user_input):
    # You can refine this logic if needed (e.g. only if user hits a button or types specific keyword)
    return True  # For now, always advance the turn on each message