import os
import datetime
from typing import List, Optional

import pandas as pd
import numpy as np

from langchain_core.tools import tool
from langchain_core.runnables import ensure_config

from app_logger import logger
from utils import get_cwd

# Load appointment data
appointments_df = pd.read_csv(
    get_cwd() + os.sep + 'data' + os.sep + 'appointments.csv')
appointments_df['datetime'] = pd.to_datetime(appointments_df['datetime'])


def generate_available_slots(specialist_id: str, start_date: str, end_date: str) -> List[dict]:
    """
    Generate available time slots for a specialist based on the new logic.

    Args:
        specialist_id (str): The specialist's ID.
        start_date (str): Start date in YYYY-MM-DD format.
        end_date (str): End date in YYYY-MM-DD format.

    Returns:
        List[dict]: List of available slots.
    """
    logger.info(f"Generating available slots for specialist_id: {specialist_id}, start_date: {start_date}, end_date: {end_date}")
    try:
        # Convert string dates to datetime objects
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        available_slots = []
        current_date = start_dt

        # Generate slots for each day in the range
        while current_date <= end_dt:
            # Skip weekends (Saturday=5, Sunday=6)
            if current_date.weekday() < 5:
                # Generate time slots for the day (11:00 to 18:00)
                # Skip 14:00-15:00 (lunch)
                for hour in [11, 12, 13, 15, 16, 17]:
                    for minute in [0, 30]:  # 30-minute intervals
                        slot_time = current_date.replace(
                            hour=hour, minute=minute, second=0)

                        # Check if this slot is already booked in appointments.csv
                        is_booked = not appointments_df[
                            (appointments_df['specialist_id'] == specialist_id) &
                            (appointments_df['datetime'] == slot_time) &
                            (appointments_df['status'] == 'booked')
                        ].empty

                        if not is_booked:
                            available_slots.append({
                                'slot_id': f"SLOT-{specialist_id}-{slot_time.strftime('%Y%m%d%H%M')}",
                                'specialist_id': specialist_id,
                                'datetime': slot_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'duration_minutes': 30,
                                'status': 'available'
                            })
                            logger.debug(f"Available slot added: {available_slots[-1]}")

            current_date += datetime.timedelta(days=1)

        logger.info(f"Total available slots generated: {len(available_slots)} for specialist_id: {specialist_id}")
        return available_slots

    except Exception as e:
        logger.error(f"Error generating slots for specialist_id: {specialist_id} - {e}")
        return []


@tool
def check_appointment_availability(specialist_id: Optional[str] = None,
                                   start_date: Optional[str] = None,
                                   end_date: Optional[str] = None) -> List[dict]:
    """
    Check available appointments for specific specialists.
    Returns available slots between 11:00-18:00 (excluding 14:00-15:00 lunch break) on weekdays.
    Date format: YYYY-MM-DD. If no dates provided, defaults to next 7 days.

    Args:
        specialist_id (Optional[str]): Specialist ID.
        start_date (Optional[str]): Start date in YYYY-MM-DD format.
        end_date (Optional[str]): End date in YYYY-MM-DD format.

    Returns:
        List[dict]: List of available slots or error message.
    """
    config = ensure_config()
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(
        f"Tool Call: check_appointment_availability - thread: {thread_id}, specialist_id: {specialist_id}, start_date: {start_date}, end_date: {end_date}")
    try:
        # Set default date range (next 7 days)
        today = datetime.datetime.now(datetime.timezone.utc).date()
        if not start_date:
            start_date = today.strftime('%Y-%m-%d')
            logger.debug(f"No start_date provided. Defaulting to today: {start_date}")
        if not end_date:
            end_date = (today + datetime.timedelta(days=7)
                        ).strftime('%Y-%m-%d')
            logger.debug(f"No end_date provided. Defaulting to 7 days from today: {end_date}")

        # If no specialist_id specified, get all doctors from the data
        if not specialist_id:
            # You might want to load doctors here or get from another source
            specialist_ids = ['ps-301', 'ps-302']  # Example doctor IDs
            logger.debug(f"No specialist_id provided. Using default specialist_ids: {specialist_ids}")
        else:
            specialist_ids = [specialist_id]

        all_available_slots = []

        for doc_id in specialist_ids:
            logger.info(f"Checking available slots for specialist_id: {doc_id}")
            slots = generate_available_slots(doc_id, start_date, end_date)
            all_available_slots.extend(slots)

        # Sort slots by datetime
        all_available_slots.sort(key=lambda x: x['datetime'])

        logger.info(f"Total available slots found: {len(all_available_slots)}")
        if all_available_slots:
            logger.debug(f"Available slots: {all_available_slots}")
        else:
            logger.warning("No available appointments found in the requested period")

        return all_available_slots if all_available_slots else [{"message": "No available appointments found in the requested period"}]

    except Exception as e:
        logger.error(f"Error checking appointment availability: {e}")
        return [{"error": f"Error checking appointment availability: {str(e)}"}]


@tool
def book_appointment(specialist_id: str, slot_datetime: str, customer_id: str, reason: str) -> dict:
    """
    Book an appointment for a specific specialist for a customer at a specific time.

    Args:
        specialist_id (str): Specialist ID.
        slot_datetime (str): Appointment datetime in YYYY-MM-DD HH:MM:SS format.
        customer_id (str): Customer ID.
        reason (str): Reason for appointment.

    Returns:
        dict: Appointment booking result or error message.
    """
    config = ensure_config()
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(
        f"Tool Call: book_appointment - thread: {thread_id}, specialist_id: {specialist_id}, slot_datetime: {slot_datetime}, customer_id: {customer_id}, reason: {reason}")
    try:
        slot_dt = pd.to_datetime(slot_datetime)
        logger.debug(f"Parsed slot_datetime: {slot_dt}")

        # Check if the slot is actually available (not during lunch, not weekend, etc.)
        if slot_dt.weekday() >= 5:  # Weekend
            logger.warning("Attempted to book appointment on weekend")
            return {"error": "Cannot book appointments on weekends"}

        if 14 <= slot_dt.hour < 15:  # Lunch break
            logger.warning("Attempted to book appointment during lunch break")
            return {"error": "Cannot book appointments during lunch break (14:00-15:00)"}

        if not (11 <= slot_dt.hour < 18):  # Outside working hours
            logger.warning("Attempted to book appointment outside working hours")
            return {"error": "Outside of working hours (11:00-18:00)"}

        # Check if slot is already booked
        existing_booking = appointments_df[
            (appointments_df['specialist_id'] == specialist_id) &
            (appointments_df['datetime'] == slot_dt) &
            (appointments_df['status'] == 'booked')
        ]

        if not existing_booking.empty:
            logger.warning(f"Slot already booked for specialist_id: {specialist_id} at {slot_dt}")
            return {"error": "This time slot is already booked"}

        # Create new appointment
        new_appointment = {
            'appointment_id': f"APT-{len(appointments_df) + 1000}",
            'specialist_id': specialist_id,
            'customer_id': customer_id,
            'datetime': slot_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_minutes': 30,
            'status': 'booked',
            'reason': reason,
            'thread_id': thread_id
        }

        # Add to dataframe
        appointments_df.loc[len(appointments_df)] = new_appointment
        logger.info(f"New appointment created: {new_appointment}")

        # Save back to CSV
        appointments_df.to_csv('data/appointments.csv', index=False)
        logger.info("Appointments CSV updated successfully.")

        return {
            "message": "Appointment booked successfully",
            "appointment_details": new_appointment
        }

    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        return {"error": f"Error booking appointment: {str(e)}"}
