import logging
import datetime
from config_and_env import read_config

def is_execution_day():
    Misc = read_config("Misc")
    executionday = int(Misc['weekday_end'])
    current_day = datetime.datetime.now().weekday()
    return current_day < executionday

def is_last_working_day_of_month():
    try:
        Misc = read_config("Misc")
        daysinmonth = int(Misc['days_in_month'])
        today = datetime.date.today()
        next_month = today.replace(day=daysinmonth) + datetime.timedelta(days=4)  # Jump to end of next month
        last_working_day = next_month - datetime.timedelta(days=next_month.day)  # Backtrack to last weekday

        logging.info(f"Today's date: {today}")
        logging.info(f"Next month's date: {next_month}")
        logging.info(f"Calculated last working day of the month: {last_working_day}")

        return today == last_working_day
    except Exception as e:
        logging.error(f"An error occurred during date calculations: {e}")
        return None