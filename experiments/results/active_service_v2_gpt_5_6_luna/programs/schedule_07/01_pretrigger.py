from datetime import date

STATE = {
    "people": {
        "jake": {
            "relationship": "best friend",
            "event": {
                "type": "wedding",
                "date": "2024-10-26",
                "role": "groomsman",
                "attendance_commitment": "whole weekend",
                "schedule": [
                    {
                        "name": "rehearsal dinner",
                        "date": "2024-10-25",
                        "time_of_day": "Friday night"
                    },
                    {
                        "name": "wedding",
                        "date": "2024-10-26",
                        "time_of_day": "Saturday"
                    },
                    {
                        "name": "brunch",
                        "date": "2024-10-27",
                        "time_of_day": "Sunday"
                    }
                ]
            }
        }
    }
}

def check_constraints(current_time):
    date.fromisoformat(current_time)
    return []
