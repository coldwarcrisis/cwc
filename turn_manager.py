from datetime import datetime, timedelta
import re
import json
import os

class TurnManager:
    def __init__(self, turn_number=0, pacing='green', current_date_str='1955-05-04'):
        self.turn_number = turn_number
        self.pacing = pacing.lower()
        self.current_date = datetime.strptime(current_date_str, '%Y-%m-%d')
        self.turn_advanced = False

    @classmethod
    def from_dict(cls, state_dict):
        return cls(
            turn_number=state_dict.get("turn_number", 0),
            pacing=state_dict.get("pacing", "green"),
            current_date_str=state_dict.get("current_date", "1955-05-04")
        )

    def to_dict(self):
        return {
            "turn_number": self.turn_number,
            "pacing": self.pacing,
            "current_date": self.get_date_str()
        }

    def advance_time(self):
        if self.pacing == 'green':
            self.current_date += timedelta(days=2)
        elif self.pacing == 'yellow':
            self.current_date += timedelta(days=1)
        self.turn_number += 1
        self.turn_advanced = True

    def get_date_str(self):
        return self.current_date.strftime('%Y-%m-%d')

    def update_from_ai(self, ai_response):
        match = re.search(r'\{switch pacing:\s*(green|yellow|red)\}', ai_response, re.IGNORECASE)
        if match:
            self.pacing = match.group(1).lower()

    def get_system_message(self):
        if self.turn_advanced:
            msg = f"Turn {self.turn_number} started. Current date is {self.get_date_str()}. Pacing is {self.pacing.upper()}."
            if self.pacing == 'green':
                msg += " You may override pacing by replying with {switch pacing: yellow} or {switch pacing: red} if the situation demands it."
            else:
                msg += " Remember to return to {switch pacing: green} when the situation is resolved."
            return msg
        return ""

    def get_pacing_instruction(self):
        if self.pacing == 'green':
            return "You may override pacing by replying with {switch pacing: yellow} or {switch pacing: red} if necessary."
        else:
            return "Remember to return to {switch pacing: green} when the situation is resolved."

    def next_turn(self):
        self.advance_time()
        self.turn_advanced = True

    def should_advance_turn(self, user_input):
    keywords = ["report", "action", "briefing", "update"]
    return any(word in user_input.lower() for word in keywords)

    def handle_ai_response(self, ai_response):
        self.update_from_ai(ai_response)
        self.turn_advanced = False

    # Accessors
    def current_mode(self):
        return self.pacing

    def current_date_str(self):
        return self.get_date_str()

    def current_turn(self):
        return self.turn_number