import os
import csv
from typing import List

import pandas as pd

from langchain_core.tools import tool
from langchain_core.runnables import ensure_config

from app_logger import logger
from utils import get_cwd


@tool
def onboard_customer(
    company_name: str,
    name: str,
    domain: str,
    email: str,
    phone: str,
    request_date: str,
    request_summary: str
) -> List[dict]:
    """
    Onboard New Customer by creating a profile and identifying issues.
    Phone is optional.

    Args:
        company_name (str): Name of the company.
        name (str): Customer's name.
        domain (str): Customer's domain.
        email (str): Customer's email address.
        phone (str): Customer's phone number (optional).
        request_date (str): Date of the request.
        request_summary (str): Summary of the request.

    Returns:
        List[dict]: Result of onboarding with success status, message, and customer_id.
    """
    # create a csv with customer profile, match with email address. If already exists, do nothing
    config = ensure_config()
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(
        f"Tool Call: onboard_customer - thread: {thread_id}, company_name: {company_name}, email: {email}")
    try:
        profiles_path = get_cwd() + os.sep + 'data' + os.sep + 'customer_profiles.csv'
        columns = [
            'customer_id', 'company_name', 'name', 'domain',
            'email', 'phone', 'thread_id', 'request_date', 'request_summary'
        ]
        logger.info(
            f"onboard_customer called with: {company_name}, {name}, {domain}, {email}, {phone}, {thread_id}, {request_date}, {request_summary}")
        create_profile = False
        profiles_df = None
        if os.path.exists(profiles_path):
            profiles_df = pd.read_csv(profiles_path)
            if profiles_df[profiles_df['email'] == email].empty:
                create_profile = True
        else:
            create_profile = True
        if create_profile:
            try:
                profiles_suffix = f"{profiles_df.shape[0] + 1:03}"
            except Exception as e:
                profiles_suffix = "001"
            row_data = {
                'customer_id': f"CUST-{profiles_suffix}",
                'company_name': company_name,
                'name': name,
                'domain': domain,
                'email': email,
                'phone': phone if phone else '',
                'thread_id': thread_id,
                'request_date': request_date,
                'request_summary': request_summary
            }

            # CSV file path
            csv_file = profiles_path

            # Convert the dictionary to a single-row dictionary (take the first element from each list)
            single_row = {col: "%s" % row_data.get(col) for col in columns}

            # Check if file exists to write header only once
            file_exists = os.path.isfile(csv_file)

            # Append to CSV
            with open(csv_file, mode='a', newline='\n', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)

                if not file_exists:
                    writer.writeheader()  # Write header if file does not exist

                writer.writerow(single_row)

                logger.info("Customer profile created for %s", name)

                # In the success case:
                return {
                    "success": True,
                    "message": f"Customer profile created for {row_data['name']}",
                    "customer_id": row_data['customer_id'],
                    "IMPORTANT_NEXT_STEP": f"MUST call store_conversation_data to save customer_id '{row_data['customer_id']}'"
                }
        else:
            cdf = profiles_df[profiles_df['email'] == email]
            logger.info("Customer profile already exists for %s--%s--" %
                  (cdf.name.values[0], cdf.customer_id.values[0]))
            return {
                "success": True,
                "message": f"Customer profile already exists for {cdf.name.values[0]}",
                "customer_id": cdf.customer_id.values[0],
                "IMPORTANT_NEXT_STEP": f"MUST call store_conversation_data to save customer_id '{cdf.customer_id.values[0]}'"
            }
    except Exception as e:
        logger.exception(f"Error onboarding customer: {e}")
        return {
            "success": False,
            "message": "Error onboarding customer. Please try again later.",
            "error": str(e)
        }
