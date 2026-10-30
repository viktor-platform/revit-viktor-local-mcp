import viktor as vkt
from agent.context import AgentContext
from agent.runner import run_agent
from state.results import clear_results
from state.tables import clear_table, read_table, storage_prefix

EMPTY_TABLE_MESSAGE = (
    "No results yet. Ask the agent about the Revit model, for example: "
    "'List the categories in the model'."
)


def is_first_user_turn(conversation) -> bool:
    """True when the conversation holds exactly one user message."""
    if not conversation:
        return False
    return sum(m["role"] == "user" for m in conversation.get_messages()) == 1


class Parametrization(vkt.Parametrization):
    introduction = vkt.Text(
        "# Revit MCP agent\n\n"
        "Chat with the Revit model that is open on the computer running the local "
        "Revit MCP services. The agent reads the model and shows full results in the "
        "**Revit results** table.\n\n"
        "**Try**\n\n"
        "- What is the name of the open model?\n"
        "- List the categories in the model.\n"
        "- Which three categories have the most elements?\n\n"
        "The agent can only read the model; it never changes Revit."
    )
    chat = vkt.Chat(
        "Revit agent",
        method="call_agent",
        flex=100,
        first_message="Hi! Ask me about the Revit model that is currently open.",
        placeholder="List the categories in the model",
    )


class Controller(vkt.Controller):
    label = "Revit Agent"
    parametrization = Parametrization(width=34)

    def call_agent(self, params, entity_id=None, workspace_id=None, **kwargs):
        """Called by VIKTOR every time the user sends a chat message."""
        conversation = params.chat
        if not conversation:
            return None
        messages = [
            {"role": message["role"], "content": message["content"]}
            for message in conversation.get_messages()
        ]
        if not messages:
            return None

        prefix = storage_prefix(entity_id, workspace_id)
        if is_first_user_turn(conversation):
            # a new conversation starts clean
            clear_table(prefix)
            clear_results(prefix)

        stream = run_agent(messages, AgentContext(storage_prefix=prefix))
        return vkt.ChatResult(conversation, stream)

    @vkt.TableView("Revit results", duration_guess=1, update_label="Refresh table")
    def results_table(self, params, entity_id=None, workspace_id=None, **kwargs):
        """Shows the table saved by the latest agent tool call."""
        table = read_table(storage_prefix(entity_id, workspace_id))
        if table is None:
            return vkt.TableResult(
                [[EMPTY_TABLE_MESSAGE]],
                column_headers=["Revit results"],
                enable_sorting_and_filtering=False,
            )
        return vkt.TableResult(
            table["rows"],
            column_headers=table["columns"],
            enable_sorting_and_filtering=True,
        )
