import os
import ast
import json

from langchain_core.tools import tool
from langchain.schema import SystemMessage
from langchain_core.runnables import ensure_config

from conversations.thread_manager import ConversationManager
from llm_utils import get_custom_llm
from utils import get_redis_instance, get_current_datetime_str
from app_logger import logger

conversation_mgr = ConversationManager()
redis_client = get_redis_instance()
custom_llm = get_custom_llm()


@tool
def summarize_conversation() -> None:
    """
    Summarize the conversation in the thread and extract key details in structured json format.
    Store summary in Redis with key as customer_company_name_with_appointment_datetime_with_specialist_name if available.
    Return None.
    """
    config = ensure_config()
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")

    try:
        print("\n\n")
        print("In Summarize Conversation Tool -- " * 34)
        print("\n\n")
        messages = conversation_mgr.get_history(thread_id)
        if not messages:
            logger.warning(
                f"No messages found for thread_id: {thread_id}. Cannot summarize.")
            return None

        # Construct a prompt for summarization
        prompt = (
            "Please summarize the following conversation and provide a json format of summary, "
            "customer_info (strictly json with case sensitive keys - ['name', 'company', 'domain', 'email', 'topic']), "
            "specialist_info (strictly json with case sensitive keys - ['name', 'designation', 'expertise']), "
            "customer_sentiment, minutes_of_meeting (Elaborate as much as possible. Try to keep in chronological order), "
            "customer_company_name_with_appointment_datetime_with_specialist_name "
            "Eg {\"summary\": \"\", \"customer_info\": \"\", \"specialist_info\": \"\", \"customer_sentiment\": \"\", "
            "\"minutes_of_meeting\": \"\", \"customer_company_name_with_appointment_datetime_with_specialist_name\": \"\"}:\nMessages:\n"
        )
        for message in messages:
            prompt += f"Role: {message['role']}, Content: {message['content']}\n"

        # Generate the summary using the language model
        response = custom_llm.invoke([SystemMessage(content=prompt)])
        json_resp = response.content.strip()
        if json_resp.startswith("```") and json_resp.endswith("```"):
            json_resp = json_resp[3:-3].strip()
        if json_resp.startswith("json"):
            json_resp = json_resp[4:].strip()

        # Parse LLM response
        summary = ast.literal_eval(json_resp)

        if not summary or "error" in summary:
            summary = "No summary available."
        else:
            summary["thread_id"] = thread_id
            summary["conversation_time"] = get_current_datetime_str()
            redis_client.hset(
                f"leads_generated",
                summary.get(
                    "customer_company_name_with_appointment_datetime_with_specialist_name",
                    thread_id,
                ),
                json.dumps(summary),
            )

    except Exception as e:
        logger.error(f"Error in summarize_conversation: {e}")
    return None


# what to include in summary for future reference
"""
### What to Include in Summary:
The `summarize_conversation` tool should capture:
- **Customer profile**: Role, company, industry, team size
- **Pain points & challenges**: What problems they're facing
- **Goals & objectives**: What they want to achieve
- **Requirements**: Technical needs, budget range, timeline
- **Interest areas**: Which services they showed interest in (migration, modernization, cost optimization, etc.)
- **Current state**: Their existing infrastructure/setup if mentioned
- **Sentiment**: Their engagement level (highly interested, exploring, skeptical, etc.)
- **Next steps**: What was discussed as follow-up (consultation booked, materials to review, etc.)
- **Key quotes**: Any particularly important statements from the customer
- **Decision factors**: Budget, timeline, stakeholders mentioned

### Summary Flow:
1. Call `summarize_conversation` with structured data
2. Store any returned summary_id: `store_conversation_data("summary_id", summary_id)`
3. Continue conversation naturally (don't mention summarization to customer)
4. Update summary when new significant information appears

### Example Triggers for Re-summarization:
- Customer: "Our budget is around $50k and we need this done in Q2"
  - You: [Call summarize_conversation to update with budget and timeline]
  
- Customer: "We're currently on AWS but struggling with costs"
  - You: [Call summarize_conversation to update with current state and pain point]

- Customer: "I'm the CTO and will need to involve our CFO in this decision"
  - You: [Call summarize_conversation to update with role and stakeholders]

"""
