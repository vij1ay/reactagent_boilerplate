from datetime import datetime
from typing import Annotated, Dict, List, Any, Literal, Optional
from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage
from langgraph.prebuilt import create_react_agent
from langgraph.graph.message import add_messages

from pydantic import BaseModel, Field, SecretStr

from agent_tools.state.state_tools import (
    store_conversation_data,
    get_conversation_data,
    clear_conversation_data,
)
from agent_tools.appointment.appointment_tools import (
    book_appointment,
    check_appointment_availability,
)
from agent_tools.case_studies.case_studies_tools import case_studies_tool
from agent_tools.summarize.summarize_tools import summarize_conversation
from agent_tools.testimonials.testimonials_tools import testimonials_tool
from agent_tools.customers.customer_tools import onboard_customer
from agent_tools.specialists.specialist_tools import get_specialist_availability

from prompts.planner_prompts import PLANNER_SYSTEM_PROMPT, PLANNER_OUTPUT_INSTRUCTIONS
from app_logger import logger
from llm_utils import environment, get_llm
from utils import get_current_datetime_str

# The following commented classes are for future schema expansion and structured responses.
# They are left here intentionally for reference and documentation purposes.

# class ToolAData(BaseModel):
#     id: Optional[str] = Field(None, description="Unique identifier")
#     name: Optional[str] = Field(description="Name Field")
#     description: Optional[str] = Field(description="Description Field")

# class ToolADetail(BaseModel):
#     data: Optional[ToolAData] = Field(
#         default_factory=lambda: ToolAData(
#             id=None,
#             name=None,
#             description=None,
#         ),
#         description="Tool A data"
#     )

# class ToolSelections(BaseModel):
#     """Structured selections from different tools."""
#     toolA_data: Optional[ToolADetail] = Field(
#         None, description="Ranked Data"
#     )

# class PlannerResponse(BaseModel):
#     """Schema for the holiday planner structured response."""
#     response_type: Literal["conversation", "toolResults"] = Field(
#         ..., description="Type of response: 'conversation' or 'toolResults'"
#     )
#     conversation_message: str = Field(
#         ..., description="Message to display to the user"
#     )
#     detail: Optional[ToolSelections] = Field(
#         None, description="Structured selections from tools (null for conversation type)"
#     )

# class PlannerState(TypedDict):
#     messages: Annotated[List[AnyMessage], add_messages]


# Add all available tools here
tools = [
    case_studies_tool,
    testimonials_tool,
    onboard_customer,
    summarize_conversation,
    get_specialist_availability,
    book_appointment,
    check_appointment_availability,
    store_conversation_data,
    get_conversation_data,
    clear_conversation_data,
]


def create_planner_graph(checkpointer=None):
    """
    Create the planner agent graph with the specified tools and model.

    Returns:
        planner_graph: The configured planner agent graph.
    """
    # Define SIMPLIFIED response format instructions for the final structured output call.
    # Focuses on schema population based on prior analysis (guided by main system prompt).

    # Create the response_format tuple as per LangGraph documentation
    # (simplified_prompt_for_final_call, schema_class)

    # response_format_config = (PLANNER_OUTPUT_INSTRUCTIONS, PlannerResponse)

    model = get_llm()

    planner_graph = create_react_agent(
        model,
        tools=tools,
        prompt=PLANNER_SYSTEM_PROMPT,  # Main system prompt for ReAct loop
        # response_format=response_format_config  # Tuple for customized final structured output call
        checkpointer=checkpointer,
    )
    return planner_graph
