"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

from openpilot.selfdrive.ui.mici.onroad.hud_renderer import HudRenderer
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.control_colors import RGB, acceleration_wheel_color
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.lead_stats import LeadStats
from openpilot.selfdrive.ui.sunnypilot.onroad.blind_spot_indicators import BlindSpotIndicators
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app


class HudRendererSP(HudRenderer):
  def __init__(self):
    super().__init__()
    self.blind_spot_indicators = BlindSpotIndicators()
    self._sp_engaged: bool = False
    self._lead_stats = LeadStats(gui_app.font(FontWeight.DISPLAY_REGULAR), self._font_bold)

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
    if self.drawing_top_icons():
      return rect.x + rect.width - 46, rect.y + 53
    return rect.x + 46, rect.y + (116 if ui_state.driving_hud_settings.show_driver_monitoring_icon else 40)

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

    sp_engaged = ui_state.engaged
    if sp_engaged != self._sp_engaged:
      self._chestnut_fade_time = rl.get_time() if sp_engaged else 0
    self._sp_engaged = sp_engaged

  def _render(self, rect: rl.Rectangle) -> None:
    super()._render(rect)
    self.blind_spot_indicators.render(rect)

  def _has_blind_spot_detected(self) -> bool:

    return self.blind_spot_indicators.detected
