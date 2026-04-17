# -*- coding: utf-8 -*-

# ./src/utils/feedback.py
from __future__ import annotations

"""
Feedback overlay renderer for n-back.

Public API:
    show_feedback(screen, status)

- status:
    "correct"   -> show feedback_correct.png at the designated position
    "incorrect" -> show feedback_incorrect.png at the designated position
    "timeout"   -> show "Too Slow" in cfg.YELLOW_RGB at the designated position

Design notes:
- Keeps the existing UI layout concept: an overlay near the lower-middle area.
- Does NOT manage timing/delay. The caller controls when to clear/hide it.
- Draws on top of the current screen contents and flips immediately.
"""

from pathlib import Path
import pygame

from utils import config as cfg

# ----------------------- Module-level cache -----------------------

_ICON_CACHE: dict[str, pygame.Surface] = {}
_FEEDBACK_DIR = cfg.RESOURCES_DIR / "feedback"
_OK_NAME = "feedback_correct.png"
_BAD_NAME = "feedback_incorrect.png"


def _load_icon(name: str) -> pygame.Surface:
    """
    Load an icon surface from resources/feedback with per-pixel alpha.
    Caches the loaded surface to avoid disk I/O on repeated calls.
    """
    if name in _ICON_CACHE:
        return _ICON_CACHE[name]

    path = (_FEEDBACK_DIR / name)
    surf = pygame.image.load(str(path)).convert_alpha()
    _ICON_CACHE[name] = surf
    return surf


def _scale_to_feedback_size(surf: pygame.Surface) -> pygame.Surface:
    """
    Scale the icon to an appropriate on-screen size using:
      - FEEDBACK_ICON_RATIO (relative to min(screen_w, screen_h))
      - FEEDBACK_ICON_MAX_PX as an absolute cap
    Preserves aspect ratio.
    """
    sw, sh = surf.get_size()
    base = min(cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT)
    target = int(base * cfg.FEEDBACK_ICON_RATIO)
    target = min(target, int(cfg.FEEDBACK_ICON_MAX_PX))
    target = max(1, target)

    # keep aspect ratio
    if sw >= sh:
        new_w = target
        new_h = max(1, int(sh * (target / sw)))
    else:
        new_h = target
        new_w = max(1, int(sw * (target / sh)))

    if (new_w, new_h) == (sw, sh):
        return surf
    return pygame.transform.smoothscale(surf, (new_w, new_h))


def _feedback_anchor(size: tuple[int, int]) -> tuple[int, int]:
    """
    Compute the top-left position to place the feedback overlay.

    Positioning policy (kept consistent with the prior "lower middle" feel):
        - Centered horizontally.
        - Vertically around ~72% of the screen height (slightly below center).
    """
    w, h = size
    x = (cfg.SCREEN_WIDTH - w) // 2
    y = int(cfg.SCREEN_HEIGHT) * 0.85 - (h // 2)
    return x, y


def _draw_timeout_text(screen: pygame.Surface) -> None:
    """
    Render 'Too Slow' using cfg.YELLOW_RGB at the designated position.
    """
    # Use the default font at the configured size.
    font = pygame.font.Font(None, cfg.FONT_SIZE)
    text_surf = font.render("Too Slow", True, cfg.YELLOW_RGB)
    pos = _feedback_anchor(text_surf.get_size())
    screen.blit(text_surf, pos)


# ----------------------- Public API -----------------------

def show_feedback_timed(screen: pygame.Surface, status: str, max_duration_ms: int, background_surface: pygame.Surface = None) -> None:
    """
    Display feedback overlay for a controlled duration with optional background preservation.

    Args:
        screen: pygame display surface to draw onto.
        status: feedback type ("correct", "incorrect", "timeout").
        max_duration_ms: maximum duration to show feedback in milliseconds.
        background_surface: optional surface to maintain as background during feedback display.

    Behavior:
        - Renders feedback overlay on top of current screen contents or provided background.
        - Maintains display for exactly max_duration_ms with continuous event polling.
        - Returns immediately after duration expires, allowing precise timing control.
        - If background_surface is provided, redraws it periodically to maintain consistency.
    """
    # Prepare feedback icon or text surface
    feedback_surface = None
    if status.lower().strip() == "correct":
        icon = _scale_to_feedback_size(_load_icon(_OK_NAME))
        feedback_surface = icon
    elif status.lower().strip() == "incorrect":
        icon = _scale_to_feedback_size(_load_icon(_BAD_NAME))
        feedback_surface = icon
    elif status.lower().strip() == "timeout":
        font = pygame.font.Font(None, cfg.FONT_SIZE)
        feedback_surface = font.render("Too Slow", True, cfg.YELLOW_RGB)
    else:
        raise ValueError(f"Unknown feedback status: {status!r}")

    feedback_pos = _feedback_anchor(feedback_surface.get_size())
    start_time = pygame.time.get_ticks()
    
    # Display feedback with timing control
    while (pygame.time.get_ticks() - start_time) < max_duration_ms:
        # Redraw background if provided to maintain visual consistency
        if background_surface:
            screen.blit(background_surface, (0, 0))
        
        # Overlay feedback on current screen contents
        screen.blit(feedback_surface, feedback_pos)
        pygame.display.flip()
        
        # Handle any pending events to maintain system responsiveness
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise SystemExit
        
        # Brief delay to prevent excessive CPU usage
        pygame.time.delay(5)


def show_feedback(screen: pygame.Surface, status: str, duration_ms: int = None) -> None:
    """
    Draw feedback overlay, flip display, and keep it visible for specified duration.

    Args:
        screen: pygame display surface to draw onto.
        status: one of {"correct", "incorrect", "timeout"}.
        duration_ms: optional custom duration in ms. If None, uses cfg.FEEDBACK_DURATION.

    Behavior:
        - "correct":   show feedback_correct.png (scaled) at the designated position.
        - "incorrect": show feedback_incorrect.png (scaled) at the designated position.
        - "timeout":   show "Too Slow" text in cfg.YELLOW_RGB at the designated position.

    Note:
        - This function pauses for the specified duration before returning.
        - The caller should handle clearing the screen after this pause if needed.
    """
    s = status.lower().strip()
    if s == "correct":
        icon = _scale_to_feedback_size(_load_icon(_OK_NAME))
        screen.blit(icon, _feedback_anchor(icon.get_size()))
    elif s == "incorrect":
        icon = _scale_to_feedback_size(_load_icon(_BAD_NAME))
        screen.blit(icon, _feedback_anchor(icon.get_size()))
    elif s == "timeout":
        _draw_timeout_text(screen)
    else:
        raise ValueError(f"Unknown feedback status: {status!r}. "
                         f"Expected 'correct', 'incorrect', or 'timeout'.")

    pygame.display.flip()
    # Keep feedback visible for the specified duration (custom or default)
    feedback_duration = duration_ms if duration_ms is not None else cfg.FEEDBACK_DURATION
    pygame.time.delay(feedback_duration)

__all__ = ["show_feedback", "show_feedback_timed"]