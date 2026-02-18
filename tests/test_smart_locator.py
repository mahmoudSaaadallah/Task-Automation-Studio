from task_automation_studio.services import smart_locator as sl
from task_automation_studio.services.smart_locator import ClickProposal


def test_cluster_click_proposals() -> None:
    proposals = [
        ClickProposal(point=(100, 100), weight=1.0, anchor_id="a"),
        ClickProposal(point=(107, 104), weight=0.6, anchor_id="b"),
        ClickProposal(point=(220, 220), weight=1.0, anchor_id="c"),
    ]
    clusters = sl._cluster_click_proposals(proposals, tolerance_px=14)  # type: ignore[attr-defined]
    assert len(clusters) == 2
    assert len(clusters[0]) == 2


def test_select_best_click_point_prefers_consensus() -> None:
    proposals = [
        ClickProposal(point=(201, 151), weight=1.0, anchor_id="target"),
        ClickProposal(point=(199, 150), weight=0.65, anchor_id="left"),
        ClickProposal(point=(260, 180), weight=1.0, anchor_id="wrong"),
    ]
    selected = sl._select_best_click_point(  # type: ignore[attr-defined]
        proposals,
        expected_point=(200, 150),
    )
    assert selected == (200, 150)


def test_select_best_click_point_rejects_ambiguous() -> None:
    proposals = [
        ClickProposal(point=(100, 100), weight=1.0, anchor_id="a"),
        ClickProposal(point=(102, 101), weight=0.65, anchor_id="b"),
        ClickProposal(point=(240, 100), weight=1.0, anchor_id="c"),
        ClickProposal(point=(242, 100), weight=0.65, anchor_id="d"),
    ]
    selected = sl._select_best_click_point(  # type: ignore[attr-defined]
        proposals,
        expected_point=None,
    )
    assert selected is None


def test_resolve_smart_click_position_with_anchors() -> None:
    payload = {
        "x": 200,
        "y": 150,
        "smart_locator": {
            "version": 1,
            "anchors": [
                {"anchor_id": "target", "path": "target.png", "dx": 0, "dy": 0, "weight": 1.0},
                {"anchor_id": "top", "path": "top.png", "dx": 0, "dy": -30, "weight": 0.65},
            ],
        },
    }

    original = sl._locate_anchor_centers
    sl._locate_anchor_centers = lambda path, region=None, confidence=0.9: [  # type: ignore[assignment]
        (200, 150) if path == "target.png" else (200, 120)
    ]
    try:
        resolved = sl.resolve_smart_click_position(payload)
    finally:
        sl._locate_anchor_centers = original  # type: ignore[assignment]

    assert resolved == (200, 150)
