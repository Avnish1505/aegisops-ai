from sim.experiment_report import build_experiment_report
from sim.visualization import CHART_FILENAMES, write_visualization_report


def test_visualization_writes_phase_3_charts_and_markdown_index(tmp_path) -> None:
    charts = write_visualization_report(build_experiment_report([0]), tmp_path)

    assert set(charts) == set(CHART_FILENAMES)
    assert all(
        path.is_file() and path.read_bytes().startswith(b"\x89PNG")
        for path in charts.values()
    )
    summary = (tmp_path / "phase_3_visualization_summary.md").read_text()
    assert "phase_3_coverage.png" in summary
    assert "phase_3_provenance_coverage.png" in summary
