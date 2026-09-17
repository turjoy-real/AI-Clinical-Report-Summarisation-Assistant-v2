from app.graph.workflow import build_graph


def test_build_graph_imports():
    graph = build_graph()
    assert graph is not None
