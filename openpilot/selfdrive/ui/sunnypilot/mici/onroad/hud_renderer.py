"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import math

import pyray as rl

from openpilot.common.constants import CV
from openpilot.selfdrive.ui.mici.onroad import SIDE_PANEL_WIDTH
from openpilot.selfdrive.ui.mici.onroad.hud_renderer import CRUISE_DISABLED_CHAR, HudRenderer
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.control_colors import RGB, acceleration_wheel_color, message_is_current
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.lead_stats import LeadStats
from openpilot.selfdrive.ui.sunnypilot.onroad.blind_spot_indicators import BlindSpotIndicators
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.modeld_v2.blendful import LOOKAHEAD_TIME, MIN_LOOKAHEAD, MIN_SPEED
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached


BLENDFUL_CHEVRON_COLOR = rl.Color(38, 143, 255, 255)
# Entry and release thresholds in meters of equivalent lateral pull at Blendful's lookahead.
BLENDFUL_PULL_LEVELS = ((0.05, 0.035), (0.15, 0.12), (0.30, 0.25))


def actual_speed_mph(sm, started_frame: int) -> int | None:
  if not message_is_current(sm, "carState", started_frame):
    return None
  speed = sm["carState"].vEgo
  return round(max(0.0, speed) * CV.MS_TO_MPH) if math.isfinite(speed) else None


def blendful_correction_level(sm, started_frame: int, previous: int) -> int:
  if not all(message_is_current(sm, service, started_frame) for service in ("carState", "carControl", "modelDataV2SP")):
    return 0

  speed = sm["carState"].vEgo
  curvature = sm["modelDataV2SP"].blendfulCurvature
  if not sm["carControl"].latActive or not math.isfinite(speed) or speed < MIN_SPEED or not math.isfinite(curvature):
    return 0

  # The published curvature is the signed addition to the model path. Model +y points right.
  lookahead = max(speed * LOOKAHEAD_TIME, MIN_LOOKAHEAD)
  magnitude = abs(curvature) * lookahead ** 2 / 2
  direction = -1 if curvature < 0.0 else 1
  level = 0
  for entry, release in BLENDFUL_PULL_LEVELS:
    threshold = release if direction * previous > level else entry
    if magnitude < threshold:
      break
    level += 1
  return direction * level


def posted_speed_limit(sm, started_frame: int, is_metric: bool) -> int | None:
  if not message_is_current(sm, "longitudinalPlanSP", started_frame):
    return None
  resolver = sm["longitudinalPlanSP"].speedLimit.resolver
  if not resolver.speedLimitValid or not math.isfinite(resolver.speedLimit):
    return None
  limit = round(resolver.speedLimit * (CV.MS_TO_KPH if is_metric else CV.MS_TO_MPH))
  return limit if 0 < limit < 1000 else None


class HudRendererSP(HudRenderer):
  def __init__(self):
    super().__init__()
    self.blind_spot_indicators = BlindSpotIndicators()
    self._sp_engaged: bool = False
    self._lead_stats = LeadStats(gui_app.font(FontWeight.DISPLAY_REGULAR), self._font_bold)
    self._actual_speed_mph: int | None = None
    self._blendful_level = 0

  def _draw_torque_slot(self, rect: rl.Rectangle) -> None:
    if not ui_state.driving_hud_settings.lead_stats:
      super()._draw_torque_slot(rect)
    elif self._show_lead_stats():
      self._lead_stats.border_color = self.lead_stats_border_color
      self._lead_stats.render(rect)

  def _steering_wheel_rgb(self) -> RGB:
    return acceleration_wheel_color(ui_state.sm, ui_state.started_frame)

  def _steering_wheel_position(self, rect: rl.Rectangle, wheel_width: int, wheel_height: int) -> tuple[float, float]:
    # Keep the original steering warning placement and leave the alert area clear.
    if self._show_wheel_critical or not self._can_draw_top_icons:
      return super()._steering_wheel_position(rect, wheel_width, wheel_height)
    return rect.x + 46, rect.y + (116 if ui_state.driving_hud_settings.show_driver_monitoring_icon else 40)

  def _draw_top_icons(self, rect: rl.Rectangle) -> None:
    if not self._can_draw_top_icons:
      self._set_speed_alpha_filter.x = 0.0
      return

    sm = ui_state.sm
    metric = ui_state.is_metric
    self._draw_actual_speed(rect)
    self._draw_set_speed(rect)
    limit = posted_speed_limit(sm, ui_state.started_frame, metric)
    if limit is not None:
      self._draw_speed_limit(rect.x + rect.width - 44, rect.y + 44, str(limit), metric)

  def _draw_actual_speed(self, rect: rl.Rectangle) -> None:
    # In split navigation the readout stays centered in the camera pane.
    narrow = rect.width < gui_app.width - SIDE_PANEL_WIDTH
    x = rect.x + (rect.width + (0 if narrow else SIDE_PANEL_WIDTH)) / 2
    y = rect.y + 40
    text = CRUISE_DISABLED_CHAR if self._actual_speed_mph is None else str(self._actual_speed_mph)
    size = (32 if len(text) >= 3 else 42) if narrow else (46 if len(text) >= 3 else 54)
    panel_width = 120 if narrow else 188
    rl.draw_rectangle_rounded(rl.Rectangle(x - panel_width / 2, rect.y + 10, panel_width, 75), 0.5, 12, rl.Color(0, 0, 0, 174))
    self._draw_speed_text(text, self._font_bold, size, x, y, rl.WHITE)
    self._draw_speed_text("mph", self._font_semi_bold, 16, x, y + 29, rl.WHITE)

    if self._blendful_level:
      direction = -1 if self._blendful_level < 0 else 1
      width, pitch, gap, half_height = (6, 9, 6, 7) if narrow else (9, 14, 10, 10)
      text_width = measure_text_cached(self._font_bold, text, size).x
      edge = x + direction * (text_width / 2 + gap)
      for index in range(abs(self._blendful_level)):
        tail_x = edge + direction * index * pitch
        tip = (tail_x + direction * width, y)
        rl.draw_line_ex((tail_x, y - half_height), tip, 2.5, BLENDFUL_CHEVRON_COLOR)
        rl.draw_line_ex(tip, (tail_x, y + half_height), 2.5, BLENDFUL_CHEVRON_COLOR)

  def _draw_set_speed(self, rect: rl.Rectangle) -> None:
    sm = ui_state.sm
    started = ui_state.started_frame
    has_speed = (self.is_cruise_set and message_is_current(sm, "carState", started) and
                 (sm["carState"].vCruiseCluster != 0 or message_is_current(sm, "controlsState", started)))
    alpha = self._set_speed_alpha_filter.update(has_speed and self._set_speed_recent())
    if not has_speed or alpha < 1e-2:
      return

    speed = str(round(self.set_speed if ui_state.is_metric else self.set_speed * CV.KPH_TO_MPH))
    x, y = rect.x + rect.width - 44, rect.y + 89
    rl.draw_rectangle_rounded(rl.Rectangle(x - 32, y - 10, 64, 20), 0.6, 8, rl.Color(0, 0, 0, int(185 * alpha)))
    tint = rl.Color(255, 255, 255, int(230 * alpha))
    self._draw_speed_text(tr("MAX"), self._font_semi_bold, 11, x - 16, y, tint)
    self._draw_speed_text(speed, self._font_display, 18, x + 12, y, tint)

  def _draw_speed_limit(self, x: float, y: float, text: str, metric: bool) -> None:
    if metric:
      rl.draw_circle_v(rl.Vector2(x, y), 31, rl.WHITE)
      rl.draw_ring(rl.Vector2(x, y), 25, 31, 0, 360, 32, rl.Color(215, 37, 45, 255))
      self._draw_speed_text(text, self._font_bold, 21 if len(text) == 3 else 27, x, y, rl.BLACK)
      return

    sign = rl.Rectangle(x - 32, y - 32, 64, 64)
    rl.draw_rectangle_rounded(sign, 0.18, 8, rl.WHITE)
    inner = rl.Rectangle(sign.x + 3, sign.y + 3, 58, 58)
    rl.draw_rectangle_rounded_lines_ex(inner, 0.13, 8, 1.5, rl.BLACK)
    self._draw_speed_text("SPEED LIMIT", self._font_semi_bold, 7, x, y - 18, rl.BLACK)
    self._draw_speed_text(text, self._font_bold, 24 if len(text) == 3 else 32, x, y + 9, rl.BLACK)

  @staticmethod
  def _draw_speed_text(text: str, font: rl.Font, size: int, x: float, y: float, color: rl.Color) -> None:
    bounds = measure_text_cached(font, text, size)
    rl.draw_text_ex(font, text, rl.Vector2(x - bounds.x / 2, y - bounds.y / 2), size, 0, color)

  def _model_source_y(self, rect: rl.Rectangle, icon_height: int) -> float:
    if ui_state.driving_hud_settings.lead_stats and self._show_lead_stats():
      card = LeadStats.card_bounds(rect)
      if card is not None:
        return card.y - icon_height - 8
    return super()._model_source_y(rect, icon_height)

  def _show_lead_stats(self) -> bool:
    return self._can_draw_top_icons and not self._has_blind_spot_detected()

  def _update_state(self) -> None:
    super()._update_state()
    self.blind_spot_indicators.update()
    sm, started = ui_state.sm, ui_state.started_frame
    self._actual_speed_mph = actual_speed_mph(sm, started)
    self._blendful_level = blendful_correction_level(sm, started, self._blendful_level)

    sp_engaged = ui_state.engaged
    if sp_engaged != self._sp_engaged:
      self._chestnut_fade_time = rl.get_time() if sp_engaged else 0
    self._sp_engaged = sp_engaged

  def _render(self, rect: rl.Rectangle) -> None:
    super()._render(rect)
    self.blind_spot_indicators.render(rect)

  def _has_blind_spot_detected(self) -> bool:

    return self.blind_spot_indicators.detected
