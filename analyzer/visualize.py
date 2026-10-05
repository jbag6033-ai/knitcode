"""Visualize KnitCode static-analysis graphs."""

from pathlib import Path

from pyvis.network import Network

from analyzer.graph import CodeGraph
from analyzer.resolver import CallResolver


def build_visualization(project_path, output_path="knitcode_graph.html"):
    """
    Analyze a Python project and generate an interactive HTML graph.
    """

    # ---------------------------------------------------------
    # 1. Static analysis
    # ---------------------------------------------------------

    resolver = CallResolver(project_path)
    resolver.analyze_project()

    resolved_calls = resolver.resolve_calls()

    # ---------------------------------------------------------
    # 2. Build KnitCode graph
    # ---------------------------------------------------------

    graph = CodeGraph()
    graph.build_from_resolved_calls(resolved_calls)

    graph_data = graph.to_dict()

    # ---------------------------------------------------------
    # 3. Create PyVis network
    # ---------------------------------------------------------

    network = Network(
        height="750px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#222222",
    )

    network.barnes_hut()

    # ---------------------------------------------------------
    # 4. Add nodes
    # ---------------------------------------------------------

    for node in graph_data["nodes"]:
        node_id = node["id"]
        node_type = node.get("type", "function")

        if node_type == "class":
            shape = "diamond"
            size = 30

        elif node_type == "method":
            shape = "box"
            size = 22

        elif node_type == "module":
            shape = "database"
            size = 25

        else:
            shape = "ellipse"
            size = 22

        label = node["name"]

        if node_type == "method" and node.get("class_name"):
            label = f'{node["class_name"]}.{node["name"]}'

        title = (
            f"Type: {node_type}<br>"
            f"File: {node['file']}"
        )

        if node.get("lineno") is not None:
            title += f"<br>Line: {node['lineno']}"

        network.add_node(
            node_id,
            label=label,
            title=title,
            shape=shape,
            size=size,
        )

    # ---------------------------------------------------------
    # 5. Add edges
    # ---------------------------------------------------------

    for edge in graph_data["edges"]:
        edge_type = edge.get("type", "calls")

        if edge_type == "instantiates":
            label = "instantiates"
            dashes = True
        else:
            label = "calls"
            dashes = False

        network.add_edge(
            edge["source"],
            edge["target"],
            label=label,
            title=f"Line: {edge.get('lineno', '?')}",
            arrows="to",
            dashes=dashes,
        )

    # ---------------------------------------------------------
    # 6. Configure interaction
    # ---------------------------------------------------------

    network.set_options(
        """
        {
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          },
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -6000,
              "springLength": 180,
              "springConstant": 0.04
            }
          },
          "edges": {
            "smooth": {
              "type": "dynamic"
            },
            "font": {
              "size": 11,
              "align": "middle"
            }
          }
        }
        """
    )

    # ---------------------------------------------------------
    # 7. Save HTML
    # ---------------------------------------------------------

    output_path = Path(output_path)

    network.write_html(str(output_path))

    print(f"KnitCode graph generated: {output_path.resolve()}")


if __name__ == "__main__":
    build_visualization(
        "benchmark/PyAnalyzer/Data/RQ3/macro-benchmark C/projects/Sublist3r",
        "sublist3r_graph.html",
    )