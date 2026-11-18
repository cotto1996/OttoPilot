import math

import pyray as rl

from openpilot.common.constants import CV
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.control_colors import RGB, message_is_current
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget


CARD_WIDTH = 224
CARD_HEIGHT = 58
MIN_EGO_SPEED_FOR_GAP = 0.5  # m/s
UNAVAILABLE = "–"


def lead_readings(sm, started_frame: int) -> tuple[str, str, str]:
  if not message_is_current(sm, "radarState", started_frame):
    return UNAVAILABLE, UNAVAILABLE, UNAVAILABLE

  lead = sm["radarState"].leadOne
  if not lead.present or not math.isfinite(lead.dRel) or lead.dRel <= 0:
    return UNAVAILABLE, UNAVAILABLE, UNAVAILABLE

  distance = f"{lead.dRel * CV.METER_TO_FOOT:.0f} ft"
  speed = f"{max(0, lead.vLead) * CV.MS_TO_MPH:.0f} mph" if math.isfinite(lead.vLead) else UNAVAILABLE
  gap = UNAVAILABLE
  if message_is_current(sm, "carState", started_frame):
    ego_speed = sm["carState"].vEgo
    if math.isfinite(ego_speed) and ego_speed >= MIN_EGO_SPEED_FOR_GAP:
      gap = f"{lead.dRel / ego_speed:.1f} s"
  return distance, speed, gap


class LeadStats(Widget):
  def __init__(self, label_font: rl.Font, value_font: rl.Font):
    super().__init__()
    self._label_font = label_font
    self._value_font = value_font
    self.border_color: RGB | None = None

  def _render(self, rect: rl.Rectangle) -> None:
    width = min(CARD_WIDTH, rect.width - 32)
    if width < 180:
      return

    # Lift the card above the bottom HUD icons when navigation narrows the camera view.
    bottom_margin = 72 if rect.width < CARD_WIDTH + 160 else 14
    card = rl.Rectangle(rect.x + (rect.width - width) / 2, rect.y + rect.height - CARD_HEIGHT - bottom_margin, width, CARD_HEIGHT)
    rl.draw_rectangle_rounded(card, 0.34, 12, rl.Color(11, 17, 24, 235))
    border = rl.Color(*self.border_color, 255) if self.border_color is not None else rl.Color(86, 95, 108, 255)
    rl.draw_rectangle_rounded_lines_ex(card, 0.34, 12, 1.5, border)

    column_width = (width - 12) / 3
    readings = lead_readings(ui_state.sm, ui_state.started_frame)
    for i, (label, value) in enumerate(zip(("Distance", "Lead speed", "Time gap"), readings, strict=True)):
      center_x = card.x + 6 + (i + 0.5) * column_width
      self._draw_centered(self._label_font, label, 11, center_x, card.y + 8, rl.Color(174, 185, 199, 255))
      value_color = rl.Color(174, 185, 199, 255) if value == UNAVAILABLE else rl.WHITE
      font_size = 17
      while font_size > 11 and measure_text_cached(self._value_font, value, font_size).x > column_width - 6:
        font_size -= 1
      self._draw_centered(self._value_font, value, font_size, center_x, card.y + 26, value_color)

  @staticmethod
  def _draw_centered(font: rl.Font, text: str, size: int, x: float, y: float, color: rl.Color) -> None:
    width = measure_text_cached(font, text, size).x
    rl.draw_text_ex(font, text, rl.Vector2(x - width / 2, y), size, 0, color)
