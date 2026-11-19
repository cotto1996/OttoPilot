import math

import pyray as rl

from openpilot.common.constants import CV
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.control_colors import RGB, message_is_current
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FONT_SCALE, font_fallback
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget


CARD_EDGE_MARGIN = 12
CARD_BOTTOM_MARGIN = 14
MAX_CARD_HEIGHT = 72
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
  def __init__(self, unit_font: rl.Font, value_font: rl.Font):
    super().__init__()
    self._unit_font = unit_font
    self._value_font = value_font
    self.border_color: RGB | None = None

  @staticmethod
  def card_bounds(rect: rl.Rectangle):
    width = rect.width - 2 * CARD_EDGE_MARGIN
    height = min(MAX_CARD_HEIGHT, round(width * 0.23))
    if width < 156 or rect.height < height + CARD_BOTTOM_MARGIN:
      return None
    return rl.Rectangle(rect.x + CARD_EDGE_MARGIN, rect.y + rect.height - height - CARD_BOTTOM_MARGIN, width, height)

  def _render(self, rect: rl.Rectangle) -> None:
    card = self.card_bounds(rect)
    if card is None:
      return

    rl.draw_rectangle_rounded(card, 0.34, 12, rl.Color(11, 17, 24, 235))
    border = rl.Color(*self.border_color, 255) if self.border_color is not None else rl.Color(86, 95, 108, 255)
    rl.draw_rectangle_rounded_lines_ex(card, 0.34, 12, 1.5, border)

    inset = 8
    column_width = (card.width - 2 * inset) / 3
    content_x = card.x + inset
    center_y = card.y + card.height / 2
    divider_color = rl.Color(border.r, border.g, border.b, 191)
    divider_height = card.height - 20
    for boundary in (1, 2):
      x = content_x + boundary * column_width
      rl.draw_rectangle_rec(rl.Rectangle(x - 0.75, center_y - divider_height / 2, 1.5, divider_height), divider_color)

    icons = (self._draw_car_icon, self._draw_speedometer_icon, self._draw_timer_icon)
    readings = lead_readings(ui_state.sm, ui_state.started_frame)
    font_size = min(42, max(18, int(card.width / 9)))
    unit_size = min(16, max(10, font_size // 2 - 2))
    _, digit_height = self._digit_metrics(self._value_font, font_size)
    baseline_y = center_y + digit_height / 2
    for i, (draw_icon, reading) in enumerate(zip(icons, readings, strict=True)):
      center_x = content_x + (i + 0.5) * column_width
      self._draw_reading(draw_icon, reading, center_x, center_y, baseline_y, column_width, font_size, unit_size)

  @staticmethod
  def _digit_metrics(font: rl.Font, size: int) -> tuple[float, float]:
    font = font_fallback(font)
    zero = ord("0")
    glyph = rl.get_glyph_info(font, zero)
    height = rl.get_glyph_atlas_rec(font, zero).height
    scale = size * FONT_SCALE / font.baseSize
    return (glyph.offsetY + height) * scale, height * scale

  def _draw_reading(self, draw_icon, reading: str, center_x: float, center_y: float, baseline_y: float,
                    column_width: float, font_size: int, unit_size: int) -> None:
    value, _, unit = reading.partition(" ")
    muted = rl.Color(174, 185, 199, 255)
    unit_width = measure_text_cached(self._unit_font, unit, unit_size).x if unit else 0
    unit_gap = 3 if unit else 0
    icon_width = 13
    icon_gap = 5
    text_size = measure_text_cached(self._value_font, value, font_size)
    value_width = column_width - icon_width - icon_gap - unit_width - unit_gap - 6
    if text_size.x > value_width:
      value_width += 2 + min(1, unit_gap)
      icon_gap -= 2
      unit_gap = max(0, unit_gap - 1)
    if text_size.x > value_width:
      icon_width = 9
      value_width += 4
    if text_size.x > value_width:
      value_width += 2
    while font_size > 11 and text_size.x > value_width:
      font_size -= 1
      text_size = measure_text_cached(self._value_font, value, font_size)
    if text_size.x > value_width:
      value = UNAVAILABLE
      unit = ""
      unit_width = unit_gap = 0
      text_size = measure_text_cached(self._value_font, value, font_size)

    x = center_x - (icon_width + icon_gap + text_size.x + unit_width + unit_gap) / 2
    icon_scale = icon_width / 13
    rl.rl_push_matrix()
    rl.rl_translatef(x, center_y, 0)
    rl.rl_scalef(icon_scale, icon_scale, 1)
    draw_icon(0, 0, muted)
    rl.rl_pop_matrix()
    x += icon_width + icon_gap
    value_baseline, _ = self._digit_metrics(self._value_font, font_size)
    y = baseline_y - value_baseline if value != UNAVAILABLE else center_y - text_size.y / 2
    rl.draw_text_ex(self._value_font, value, rl.Vector2(x, y), font_size, 0, muted if value == UNAVAILABLE else rl.WHITE)
    if unit:
      unit_baseline, _ = self._digit_metrics(self._unit_font, unit_size)
      rl.draw_text_ex(self._unit_font, unit, rl.Vector2(x + text_size.x + unit_gap, baseline_y - unit_baseline), unit_size, 0, muted)

  @staticmethod
  def _draw_car_icon(x: float, y: float, color: rl.Color) -> None:
    rl.draw_line_ex(rl.Vector2(x + 2, y - 1), rl.Vector2(x + 4, y - 5), 1.3, color)
    rl.draw_line_ex(rl.Vector2(x + 4, y - 5), rl.Vector2(x + 9, y - 5), 1.3, color)
    rl.draw_line_ex(rl.Vector2(x + 9, y - 5), rl.Vector2(x + 11, y - 1), 1.3, color)
    rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(x + 1, y - 1, 11, 5), 0.45, 4, 1.2, color)
    for wheel_x in (x + 3, x + 10):
      rl.draw_line_ex(rl.Vector2(wheel_x, y + 4), rl.Vector2(wheel_x, y + 6), 1.5, color)

  @staticmethod
  def _draw_speedometer_icon(x: float, y: float, color: rl.Color) -> None:
    center = rl.Vector2(x + 6.5, y + 3)
    rl.draw_ring(center, 4.8, 6.2, 180, 360, 16, color)
    rl.draw_line_ex(center, rl.Vector2(x + 9, y - 1), 1.4, color)
    rl.draw_circle_v(center, 1, color)

  @staticmethod
  def _draw_timer_icon(x: float, y: float, color: rl.Color) -> None:
    center = rl.Vector2(x + 6.5, y + 1)
    rl.draw_ring(center, 4.5, 5.8, 0, 360, 24, color)
    rl.draw_line_ex(rl.Vector2(x + 4.5, y - 6.9), rl.Vector2(x + 8.5, y - 6.9), 1.3, color)
    rl.draw_line_ex(rl.Vector2(x + 6.5, y - 7), rl.Vector2(x + 6.5, y - 4.6), 1.3, color)
    rl.draw_line_ex(center, rl.Vector2(x + 6.5, y - 2), 1.3, color)
