from teshq.utils.formater import print_query_table, print_simple_table


def test_print_query_table(capsys):
    """Test that print_query_table prints something to stdout."""
    request = "test request"
    query = "SELECT * FROM test_table"
    params = {"id": 1}
    results = [{"col1": "value1", "col2": 123}]

    print_query_table(request, query, params, results)
    captured = capsys.readouterr()

    # Basic check if any output was produced
    assert len(captured.out) > 0
    # You could add more specific checks here, e.g., checking for keywords
    # assert "REQUEST: test request" in captured.out
    # assert "QUERY: SELECT * FROM test_table" in captured.out


def test_print_simple_table(capsys):
    """Test that print_simple_table prints something to stdout."""
    results = [{"col1": "value1", "col2": 123}]
    title = "Test Results"

    print_simple_table(results, title)
    captured = capsys.readouterr()

    # Basic check if any output was produced
    assert len(captured.out) > 0
    # assert "Test Results" in captured.out
