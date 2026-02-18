from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

SMART_LOCATOR_VERSION = 1
MATCH_CONFIDENCE = 0.9
MATCH_DEDUP_TOLERANCE_PX = 8
CLUSTER_TOLERANCE_PX = 14
EXPECTED_DISTANCE_PENALTY_PX = 220
MIN_SCORE = 1.15
MIN_MARGIN = 0.16


@dataclass(frozen=True, slots=True)
class AnchorSpec:
    anchor_id: str
    dx: int
    dy: int
    half_size: int
    weight: float


@dataclass(frozen=True, slots=True)
class ClickProposal:
    point: tuple[int, int]
    weight: float
    anchor_id: str


ANCHOR_SPECS: tuple[AnchorSpec, ...] = (
    AnchorSpec(anchor_id="target", dx=0, dy=0, half_size=20, weight=1.0),
    AnchorSpec(anchor_id="top", dx=0, dy=-30, half_size=24, weight=0.65),
    AnchorSpec(anchor_id="left", dx=-30, dy=0, half_size=24, weight=0.65),
    AnchorSpec(anchor_id="right", dx=30, dy=0, half_size=24, weight=0.65),
    AnchorSpec(anchor_id="bottom", dx=0, dy=30, half_size=24, weight=0.65),
)


def _distance_sq(left: tuple[int, int], right: tuple[int, int]) -> int:
    return (left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2


def _safe_region(*, left: int, top: int, width: int, height: int) -> tuple[int, int, int, int] | None:
    if width <= 0 or height <= 0:
        return None
    return max(0, left), max(0, top), width, height


def _region_around_point(center: tuple[int, int], radius: int) -> tuple[int, int, int, int] | None:
    return _safe_region(
        left=center[0] - radius,
        top=center[1] - radius,
        width=radius * 2,
        height=radius * 2,
    )


def _window_region_from_payload(payload: dict[str, Any]) -> tuple[int, int, int, int] | None:
    window_context = payload.get("window_context")
    if not isinstance(window_context, dict):
        return None
    left = window_context.get("left")
    top = window_context.get("top")
    width = window_context.get("width")
    height = window_context.get("height")
    if not all(isinstance(value, int) for value in (left, top, width, height)):
        return None
    return _safe_region(left=left, top=top, width=width, height=height)


def _search_regions(payload: dict[str, Any], expected_anchor_center: tuple[int, int] | None) -> list[tuple[int, int, int, int]]:
    regions: list[tuple[int, int, int, int]] = []
    if expected_anchor_center is not None:
        local_region = _region_around_point(expected_anchor_center, radius=170)
        if local_region is not None:
            regions.append(local_region)
    window_region = _window_region_from_payload(payload)
    if window_region is not None and window_region not in regions:
        regions.append(window_region)
    return regions


def _dedupe_points(points: list[tuple[int, int]], *, tolerance_px: int) -> list[tuple[int, int]]:
    deduped: list[tuple[int, int]] = []
    for point in points:
        if any(_distance_sq(point, existing) <= tolerance_px * tolerance_px for existing in deduped):
            continue
        deduped.append(point)
    return deduped


def _locate_anchor_centers(
    anchor_path: str,
    *,
    region: tuple[int, int, int, int] | None,
    confidence: float = MATCH_CONFIDENCE,
) -> list[tuple[int, int]]:
    path = Path(anchor_path)
    if not path.exists():
        return []

    try:
        import pyautogui  # pylint: disable=import-outside-toplevel
    except Exception:  # pragma: no cover - dependency/platform dependent
        return []

    kwargs: dict[str, Any] = {"grayscale": True}
    if region is not None:
        kwargs["region"] = region

    try:
        try:
            boxes = list(pyautogui.locateAllOnScreen(str(path), confidence=confidence, **kwargs))
        except TypeError:
            boxes = list(pyautogui.locateAllOnScreen(str(path), **kwargs))
    except Exception:  # pragma: no cover - screen/env dependent
        return []

    points: list[tuple[int, int]] = []
    for box in boxes:
        center = pyautogui.center(box)
        points.append((int(center.x), int(center.y)))
    return _dedupe_points(points, tolerance_px=MATCH_DEDUP_TOLERANCE_PX)


def _cluster_click_proposals(proposals: list[ClickProposal], *, tolerance_px: int = CLUSTER_TOLERANCE_PX) -> list[list[ClickProposal]]:
    clusters: list[list[ClickProposal]] = []
    tolerance_sq = tolerance_px * tolerance_px
    for proposal in proposals:
        assigned = False
        for cluster in clusters:
            representative = cluster[0].point
            if _distance_sq(proposal.point, representative) <= tolerance_sq:
                cluster.append(proposal)
                assigned = True
                break
        if not assigned:
            clusters.append([proposal])
    return clusters


def _cluster_center(cluster: list[ClickProposal]) -> tuple[int, int]:
    total_x = sum(item.point[0] for item in cluster)
    total_y = sum(item.point[1] for item in cluster)
    return round(total_x / len(cluster)), round(total_y / len(cluster))


def _cluster_weight(cluster: list[ClickProposal]) -> float:
    per_anchor: dict[str, float] = {}
    for item in cluster:
        previous = per_anchor.get(item.anchor_id, 0.0)
        if item.weight > previous:
            per_anchor[item.anchor_id] = item.weight
    return sum(per_anchor.values())


def _cluster_anchor_count(cluster: list[ClickProposal]) -> int:
    return len({item.anchor_id for item in cluster})


def _select_best_click_point(
    proposals: list[ClickProposal],
    *,
    expected_point: tuple[int, int] | None,
) -> tuple[int, int] | None:
    if not proposals:
        return None

    ranked: list[tuple[float, tuple[int, int], int]] = []
    for cluster in _cluster_click_proposals(proposals):
        center = _cluster_center(cluster)
        raw_score = _cluster_weight(cluster)
        anchor_count = _cluster_anchor_count(cluster)

        if expected_point is None:
            distance_penalty = 0.0
        else:
            distance = _distance_sq(center, expected_point) ** 0.5
            distance_penalty = min(distance / EXPECTED_DISTANCE_PENALTY_PX, 1.0) * 0.35
        score = raw_score - distance_penalty
        ranked.append((score, center, anchor_count))

    ranked.sort(key=lambda item: (item[0], item[2]), reverse=True)
    top_score, top_center, top_anchor_count = ranked[0]
    if top_score < MIN_SCORE:
        return None
    if top_anchor_count < 2:
        return None

    if len(ranked) > 1:
        second_score = ranked[1][0]
        if top_score - second_score < MIN_MARGIN:
            return None
    return top_center


def resolve_smart_click_position(payload: dict[str, Any]) -> tuple[int, int] | None:
    smart_locator = payload.get("smart_locator")
    if not isinstance(smart_locator, dict):
        return None

    anchors_raw = smart_locator.get("anchors")
    if not isinstance(anchors_raw, list):
        return None

    raw_x = payload.get("x")
    raw_y = payload.get("y")
    expected_click: tuple[int, int] | None = None
    if isinstance(raw_x, int) and isinstance(raw_y, int):
        expected_click = (raw_x, raw_y)

    proposals: list[ClickProposal] = []
    for index, anchor in enumerate(anchors_raw):
        if not isinstance(anchor, dict):
            continue

        path = anchor.get("path")
        dx = anchor.get("dx")
        dy = anchor.get("dy")
        weight = anchor.get("weight")
        if not isinstance(path, str) or not path:
            continue
        if not isinstance(dx, int) or not isinstance(dy, int):
            continue
        if not isinstance(weight, (int, float)):
            continue

        expected_anchor: tuple[int, int] | None = None
        if expected_click is not None:
            expected_anchor = (expected_click[0] + dx, expected_click[1] + dy)
        search_regions = _search_regions(payload, expected_anchor_center=expected_anchor)
        regions_with_fallback: list[tuple[int, int, int, int] | None] = list(search_regions)
        if not regions_with_fallback:
            regions_with_fallback = [None]

        matched_centers: list[tuple[int, int]] = []
        for region in regions_with_fallback:
            matched_centers = _locate_anchor_centers(path, region=region)
            if matched_centers:
                break
        for center in matched_centers:
            proposals.append(
                ClickProposal(
                    point=(center[0] - dx, center[1] - dy),
                    weight=float(weight),
                    anchor_id=str(anchor.get("anchor_id", f"a{index}")),
                )
            )

    return _select_best_click_point(proposals, expected_point=expected_click)


def capture_click_anchors(
    *,
    artifacts_dir: Path,
    session_id: str,
    event_id: str,
    x: int,
    y: int,
) -> dict[str, Any] | None:
    try:
        from PIL import ImageGrab  # pylint: disable=import-outside-toplevel
    except Exception:  # pragma: no cover - dependency/platform dependent
        return None

    output_dir = artifacts_dir / "click_anchors" / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    anchors: list[dict[str, Any]] = []
    for index, spec in enumerate(ANCHOR_SPECS):
        anchor_x = x + spec.dx
        anchor_y = y + spec.dy

        left = max(0, anchor_x - spec.half_size)
        top = max(0, anchor_y - spec.half_size)
        right = max(left + 1, anchor_x + spec.half_size)
        bottom = max(top + 1, anchor_y + spec.half_size)

        try:
            image = ImageGrab.grab(bbox=(left, top, right, bottom))
        except Exception:  # pragma: no cover - OS/screen dependent
            continue

        anchor_path = output_dir / f"{event_id}_{index}.png"
        try:
            image.save(anchor_path)
        except Exception:  # pragma: no cover - filesystem dependent
            continue

        anchors.append(
            {
                "anchor_id": spec.anchor_id,
                "path": str(anchor_path),
                "dx": spec.dx,
                "dy": spec.dy,
                "weight": spec.weight,
            }
        )

    if not anchors:
        return None
    return {"version": SMART_LOCATOR_VERSION, "anchors": anchors}
