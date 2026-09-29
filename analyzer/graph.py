"""Build graph representations from static-analysis results."""


class CodeGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = []

    def add_node(self, node_id, **attributes):
        """Add a node if it does not already exist."""
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "id": node_id,
                **attributes,
            }

    def add_edge(self, source, target, **attributes):
        """Add a directed edge between two nodes."""
        self.edges.append({
            "source": source,
            "target": target,
            **attributes,
        })

    def build_from_resolved_calls(self, resolved_calls):
        """Build a function-call graph from resolver results."""

        for result in resolved_calls:
            caller_file = result["caller_file"]
            caller_name = result["caller"]
            target = result["target"]

            # Caller node
            caller_id = f"{caller_file}::{caller_name}"

            self.add_node(
                caller_id,
                name=caller_name,
                file=caller_file,
                type="function" if caller_name != "<module>" else "module",
            )

            # Skip unresolved external/built-in calls for now.
            if target is None:
                continue

            target_id = f"{target['file']}::{target['name']}"

            self.add_node(
                target_id,
                name=target["name"],
                file=target["file"],
                lineno=target["lineno"],
                type="function",
            )

            self.add_edge(
                caller_id,
                target_id,
                type="calls",
                lineno=result["lineno"],
            )

        return self

    def to_dict(self):
        """Return graph data in a JSON-serializable format."""
        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
        }