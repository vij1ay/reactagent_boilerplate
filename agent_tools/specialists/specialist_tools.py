import os
import csv
import json
import random
import ast
from typing import List

import pandas as pd

from langchain_core.tools import tool
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import ensure_config

from llm_utils import get_custom_llm
from app_logger import logger
from utils import get_cwd

custom_llm = get_custom_llm()

with open(get_cwd() + os.sep + 'data' + os.sep + 'specialists.json', 'r') as f:
    specialists_data = json.load(f)


def llm_specialist_search(search_query: str, specialists: List[dict]) -> List[dict]:
    """
    Use LLM to intelligently match specialists based on search query and return 1 specialist json.

    Args:
        search_query (str): The user's search query.
        specialists (List[dict]): List of available specialists.

    Returns:
        List[dict]: List containing the best matched specialist, or empty list if no match.
    """
    try:
        # Prepare specialist information for LLM
        specialist_info = []
        for specialist in specialists:
            specialist_str = (
                f"ID: {specialist['specialist_id']}, Name: {specialist['name']}, "
                f"Title: {specialist['title']}, Product: {specialist['products']}, "
                f"Skills: {specialist['skills']}, Integrations: {specialist['integrations']}, "
                f"Domain: {specialist['industries']}"
            )
            specialist_info.append(specialist_str)

        specialist_list_text = "\n".join(specialist_info)

        # Create LLM prompt
        system_prompt = (
            "You are a technical specialist matching domain expert. Analyze the user query and match it with the most appropriate specialist based on their specialties, sub-specialties, and expertise. Return json dict of matched specialist with full json structure. If no match, return empty list []."
        )

        human_prompt = (
            f'Specialist Query: "{search_query}"\n\n'
            f"Available Specialists:\n{specialist_list_text}\n\n"
            "Analyze the user query and match with the most relevant specialists based on domain and expertise. Consider:\n"
            "1. Specialty alignment with domain, expertise and skills.\n\n"
            "Filter specialists and return 1 best match"
        )

        # Call LLM
        response = custom_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        json_resp = response.content.strip()
        if json_resp.startswith("```") and json_resp.endswith("```"):
            json_resp = json_resp[3:-3].strip()
        if json_resp.startswith("json"):
            json_resp = json_resp[4:].strip()

        # Parse LLM response
        return ast.literal_eval(json_resp)

    except Exception as e:
        print(f"LLM search error: {e}")
        # Fallback to simple keyword matching
        return [specialists[0]] if specialists else []


@tool
def get_specialist_availability(search_query: str) -> dict:
    """
    Use LLM to intelligently match specialists based on search query and return 1 specialist based on domain and expertise.

    Args:
        search_query (str): The user's search query.

    Returns:
        dict: Specialist selection result and details.
    """
    config = ensure_config()
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    logger.info(
        f"Tool Call: get_specialist_availability - thread: {thread_id}, search_query: {search_query}")
    try:
        specialist_data = llm_specialist_search(search_query, specialists_data)
        # specialist_data = random.choice(specialists_data)
        if "matched_specialist" in specialist_data:
            specialist_data = specialist_data["matched_specialist"]
        if not specialist_data:
            specialist_data = specialists_data[0]
        return {
            "success": True,
            "message": f"Specialist selected: {specialist_data.get('name', '')}, Title: {specialist_data.get('title', '')}",
            "specialist_id": specialist_data.get("specialist_id", ""),
            "specialist_name": specialist_data.get("name", ""),
            "specialist_details": json.dumps(specialist_data),
            "IMPORTANT_NEXT_STEP": f"MUST call store_conversation_data to save specialist_id '{specialist_data.get('specialist_id', '')}' and name '{specialist_data.get('name', '')}'"
        }
    except Exception as e:
        logger.exception(f"Error fetching specialist availability: {e}")
        return {
            "success": False,
            "message": "No specialists available at the moment. Please try again later.",
            "error": str(e)
        }
