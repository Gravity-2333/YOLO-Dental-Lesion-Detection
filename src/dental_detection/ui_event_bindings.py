from __future__ import annotations

import inspect
import re
import textwrap

from .ui_events import (
    bind_chat_events,
    bind_export_and_record_events,
    bind_model_and_storage_events,
    bind_workspace_events,
)


def event_binding_source(build_app) -> str:
    """Return binding source for structural tests across split modules."""
    source = "\n".join(
        (
            inspect.getsource(build_app),
            textwrap.indent(inspect.getsource(bind_workspace_events), "    "),
            textwrap.indent(inspect.getsource(bind_chat_events), "    "),
            textwrap.indent(inspect.getsource(bind_model_and_storage_events), "    "),
            textwrap.indent(inspect.getsource(bind_export_and_record_events), "    "),
        )
    )
    return re.sub(r"\b[hc]\.", "", source)
