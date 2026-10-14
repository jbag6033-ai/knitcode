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
        """
        Build a graph from resolved static-analysis results.

        Supported target types:

            function
            method
            class

        Class targets represent constructor calls and use an
        'instantiates' edge instead of a normal 'calls' edge.
        """

        # Register known definitions before fallback caller nodes so metadata
        # does not depend on the order of call expressions. Materialize once
        # to support iterators as well as lists.
        resolved_calls = list(resolved_calls)
        for result in resolved_calls:
            for definition in (
                result.get("caller_definition"), result["target"],
            ):
                if definition is None:
                    continue
                name = definition["name"]
                if definition.get("class") is not None:
                    name = f"{definition['class']}.{name}"
                self.add_node(
                    f"{definition['file']}::{name}",
                    name=definition["name"],
                    file=definition["file"],
                    lineno=definition["lineno"],
                    type=definition.get("type", "function"),
                    class_name=definition.get("class"),
                )

        for result in resolved_calls:
            caller_file = result["caller_file"]
            caller_name = result["caller"]
            target = result["target"]

            # -----------------------------------------------------
            # Caller node
            # -----------------------------------------------------

            caller_id = f"{caller_file}::{caller_name}"

            caller_type = (
                "module"
                if caller_name == "<module>"
                else "function"
            )

            self.add_node(
                caller_id,
                name=caller_name,
                file=caller_file,
                type=caller_type,
            )

            # -----------------------------------------------------
            # Skip unresolved calls
            #
            # Examples:
            #   print()
            #   third-party/external calls
            # -----------------------------------------------------

            if target is None:
                continue

            # -----------------------------------------------------
            # Target node
            # -----------------------------------------------------

            target_type = target.get("type", "function")

            # Methods need the class name in their node ID.
            #
            # Without this:
            #
            #   service.py::create_order
            #
            # With this:
            #
            #   service.py::OrderService.create_order
            #
            if (
                target_type == "method"
                and target.get("class") is not None
            ):
                target_name = (
                    f"{target['class']}.{target['name']}"
                )
            else:
                target_name = target["name"]

            target_id = f"{target['file']}::{target_name}"

            self.add_node(
                target_id,
                name=target["name"],
                file=target["file"],
                lineno=target["lineno"],
                type=target_type,
                class_name=target.get("class"),
            )

            # -----------------------------------------------------
            # Edge type
            # -----------------------------------------------------

            if target_type == "class":
                edge_type = "instantiates"
            else:
                edge_type = "calls"

            self.add_edge(
                caller_id,
                target_id,
                type=edge_type,
                lineno=result["lineno"],
            )

        return self

    def to_dict(self):
        """Return graph data in a JSON-serializable format."""

        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
        }
