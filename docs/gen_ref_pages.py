"""Generate API reference pages for MkDocs."""

from pathlib import Path
import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

root = Path(__file__).parent.parent
src = root / "reactive_agents"

# Only document public-facing modules (excluding __init__ files for now)
INCLUDE_PATHS = [
    "reactive_agents/app/agents/base.py",
    "reactive_agents/app/agents/reactive_agent.py",
    "reactive_agents/app/builders/agent.py",
    "reactive_agents/core/tools/decorators.py",
    "reactive_agents/core/tools/base.py",
    "reactive_agents/core/types/reasoning_types.py",
    "reactive_agents/core/types/execution_types.py",
    "reactive_agents/core/types/agent_types.py",
    "reactive_agents/core/types/confirmation_types.py",
    "reactive_agents/core/types/status_types.py",
    "reactive_agents/core/types/session_types.py",
    "reactive_agents/core/types/event_types.py",
]

for include_path in INCLUDE_PATHS:
    path = root / include_path

    if not path.exists():
        continue

    module_path = path.relative_to(root).with_suffix("")
    doc_path = path.relative_to(root).with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    parts = tuple(module_path.parts)

    # Create the documentation page
    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        identifier = ".".join(parts)
        # Use a friendlier title
        title = parts[-1].replace("_", " ").title()
        fd.write(f"# {title}\n\n")
        fd.write(f"::: {identifier}\n")

    # Add to navigation
    mkdocs_gen_files.set_edit_path(full_doc_path, path)
    nav[parts] = doc_path.as_posix()

# Generate the navigation file
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
