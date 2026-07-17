"""Chamber / pot / port / arrow meshes and actors for the twin view."""

from __future__ import annotations

from typing import Any

from .hud import FONT_COLOR
from .plotter import safe_remove
from .scene import TwinSnapshot, pot_layout_positions, pot_radius_height, vent_port_centers

# In-chamber labels (INLET / OUTLET / pots) — larger than HUD tables
SCENE_LABEL_FONT_SIZE = 22

_WIRE = "#e8e8e8"
_POT = "#6b5b4b"
_INLET = "#5cb85c"
_OUTLET = "#5b9bd5"
_ARROW = "#c8e6f5"


def clean_mesh(mesh: Any) -> Any:
    """Strip all point/cell arrays so VTK never applies a colormap (purple wash)."""
    out = mesh.copy(deep=True)
    try:
        out.clear_data()
    except Exception:
        pass
    try:
        out.set_active_scalars(None)
    except Exception:
        pass
    return out


def add_solid(
    pl: Any,
    mesh: Any,
    *,
    color: str,
    name: str,
    style: str = "surface",
    line_width: float = 1.0,
    lighting: bool = False,
) -> Any:
    """Add mesh with forced flat RGB — never scalars, never edges-as-second-outline."""
    actor = pl.add_mesh(
        clean_mesh(mesh),
        style=style,
        color=color,
        line_width=line_width,
        name=name,
        lighting=lighting,
        smooth_shading=False,
        show_edges=False,
        show_scalar_bar=False,
        ambient=1.0 if not lighting else 0.45,
        diffuse=0.0 if not lighting else 0.55,
        specular=0.0,
        render_lines_as_tubes=False,
    )
    try:
        mapper = actor.GetMapper() if hasattr(actor, "GetMapper") else actor.mapper
        if mapper is not None:
            mapper.ScalarVisibilityOff()
    except Exception:
        pass
    try:
        prop = actor.GetProperty() if hasattr(actor, "GetProperty") else actor.prop
        if prop is not None and hasattr(prop, "EdgeVisibilityOff"):
            prop.EdgeVisibilityOff()
    except Exception:
        pass
    return actor


def pot_label_text(index: int, moisture_pct: float) -> str:
    return f"P{index + 1} θ={moisture_pct:.0f}%"


def add_scene_label(
    pl: Any,
    pos: tuple[float, float, float],
    label: str,
    *,
    name: str,
) -> None:
    """In-chamber point label (larger than HUD tables)."""
    pl.add_point_labels(
        [pos],
        [label],
        font_size=SCENE_LABEL_FONT_SIZE,
        text_color=FONT_COLOR,
        point_size=0,
        shape=None,
        always_visible=True,
        name=name,
    )


def set_pot_labels(
    pl: Any,
    pot_labels: list[tuple[tuple[float, float, float], str]],
    *,
    cache: dict[str, Any] | None = None,
) -> None:
    """Update pot moisture labels; skip rebuild when text unchanged (no flicker)."""
    texts = tuple(label for _pos, label in pot_labels)
    if cache is not None and cache.get("pot_label_texts") == texts:
        return
    for i in range(4):
        safe_remove(pl, f"pot_label_{i}")
    for i, (pos, label) in enumerate(pot_labels):
        add_scene_label(pl, pos, label, name=f"pot_label_{i}")
    if cache is not None:
        cache["pot_label_texts"] = texts


def build_static_meshes(pv: Any, snap: TwinSnapshot) -> dict[str, Any]:
    """Geometry independent of fan command — no T/RH coloring."""
    sx, sy, sz = snap.box.size_xyz
    # Outline only (line cells). Cube surface + FaceIndex caused multi-color edges.
    solid = pv.Box(bounds=(-0.5 * sx, 0.5 * sx, -0.5 * sy, 0.5 * sy, 0.0, sz))
    chamber = solid.outline()

    pots: list[Any] = []
    pot_labels: list[tuple[tuple[float, float, float], str]] = []
    pot_label_indices: list[int] = []
    for index, cx, cy, cz in pot_layout_positions(snap.box, snap.pot_active):
        pot_vol = float(snap.pot_volume_l[index]) if index < len(snap.pot_volume_l) else 12.0
        radius, height = pot_radius_height(snap.box, pot_volume_l=pot_vol)
        pots.append(
            pv.Cylinder(
                center=(cx, cy, cz + 0.5 * height),
                direction=(0.0, 0.0, 1.0),
                radius=radius,
                height=height,
                resolution=24,
            )
        )
        pot_labels.append(
            (
                (cx, cy, cz + height + 0.05 * sz),
                pot_label_text(index, snap.pot_moisture[index]),
            )
        )
        pot_label_indices.append(index)

    inlet_c, outlet_c = vent_port_centers(snap.box)
    port_r = 0.14 * min(sx, sy)
    inlet = pv.Disc(
        center=inlet_c,
        inner=0.4 * port_r,
        outer=port_r,
        normal=(-1.0, 0.0, 0.0),
        r_res=16,
        c_res=16,
    )
    outlet = pv.Disc(
        center=outlet_c,
        inner=0.4 * port_r,
        outer=port_r,
        normal=(1.0, 0.0, 0.0),
        r_res=16,
        c_res=16,
    )
    port_labels = [
        ((inlet_c[0] - 0.06 * sx, inlet_c[1], inlet_c[2] + 0.14 * sz), "INLET"),
        ((outlet_c[0] + 0.06 * sx, outlet_c[1], outlet_c[2] + 0.14 * sz), "OUTLET"),
    ]
    return {
        "chamber": chamber,
        "pots": pots,
        "pot_labels": pot_labels,
        "pot_label_indices": pot_label_indices,
        "inlet": inlet,
        "outlet": outlet,
        "port_labels": port_labels,
        "box_len": sx,
        "inlet_c": inlet_c,
        "outlet_c": outlet_c,
    }


def add_static_scene(pl: Any, meshes: dict[str, Any]) -> None:
    """Wireframe outline chamber only — no solid fill, no scalar maps."""
    add_solid(
        pl,
        meshes["chamber"],
        color=_WIRE,
        name="chamber",
        style="wireframe",
        line_width=2.0,
        lighting=False,
    )
    for i, pot in enumerate(meshes["pots"]):
        add_solid(pl, pot, color=_POT, name=f"pot_{i}", lighting=True)
    set_pot_labels(pl, meshes["pot_labels"])
    add_solid(pl, meshes["inlet"], color=_INLET, name="inlet", lighting=False)
    add_solid(pl, meshes["outlet"], color=_OUTLET, name="outlet", lighting=False)
    for i, (pos, label) in enumerate(meshes["port_labels"]):
        add_scene_label(pl, pos, label, name=f"port_label_{i}")


def ensure_arrow_actors(
    pl: Any, pv: Any, snap: TwinSnapshot, box_len: float, cache: dict[str, Any]
) -> None:
    """Create arrow actors once (hidden); fan toggle only flips visibility.

    remove_actor/add_mesh on every keypress is what produced purple wash +
    double red/blue outlines on macOS/VTK in interactive sessions.
    """
    if cache.get("arrow_ready"):
        return
    # Build from a synthetic fan-on snapshot geometry using current port points
    # if fan is off, still place arrows at vent centers from static meshes.
    inlet_c = cache.get("inlet_c")
    outlet_c = cache.get("outlet_c")
    length = max(0.04, 0.08 * box_len)
    origins: list[tuple[float, float, float]]
    if snap.exchange.points.shape[0] >= 2:
        origins = [tuple(float(v) for v in p) for p in snap.exchange.points[:2]]
    elif inlet_c is not None and outlet_c is not None:
        hx = 0.5 * box_len
        origins = [
            (float(inlet_c[0]) + 0.02 * hx, float(inlet_c[1]), float(inlet_c[2])),
            (float(outlet_c[0]) - 0.02 * hx, float(outlet_c[1]), float(outlet_c[2])),
        ]
    else:
        origins = []

    for i, origin in enumerate(origins[:2]):
        mesh = pv.Arrow(
            start=origin,
            direction=(1.0, 0.0, 0.0),
            tip_length=0.35,
            tip_radius=0.1,
            tip_resolution=12,
            shaft_radius=0.04,
            shaft_resolution=12,
            scale=length,
        )
        actor = add_solid(pl, mesh, color=_ARROW, name=f"arrow_{i}", lighting=False)
        try:
            actor.SetVisibility(False)
        except Exception:
            try:
                actor.visibility = False
            except Exception:
                pass
    cache["arrow_ready"] = True
    cache["arrow_count"] = len(origins[:2])


def set_arrows_visible(pl: Any, visible: bool, cache: dict[str, Any]) -> None:
    n = int(cache.get("arrow_count", 2))
    for i in range(n):
        actor = None
        try:
            actor = pl.actors.get(f"arrow_{i}")
        except Exception:
            actor = None
        if actor is None:
            continue
        try:
            actor.SetVisibility(bool(visible))
        except Exception:
            try:
                actor.visibility = bool(visible)
            except Exception:
                pass
